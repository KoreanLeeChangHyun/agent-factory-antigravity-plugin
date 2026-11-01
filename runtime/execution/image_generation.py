"""Generate images through the installed Codex native tool and existing ChatGPT login.

Only provider imageGeneration events count as output. No API-key or command backend fallback.
"""
from __future__ import annotations

import base64
import binascii
import json
import math
import os
import subprocess
import queue
import shutil
import tempfile
import time
from pathlib import Path

from adapters.codex.transport import Rpc
from adapters.codex.capabilities import NativeError
from system.portable import native_executable

from execution.images import IMAGE_TYPES, _signature_matches
from storage.errors import ContractError

TIMEOUT_ENV = "AGENT_FACTORY_IMAGE_TIMEOUT"


def image_content(value):
    """Validate every returned image; never accept a filename, URL or success prose as image evidence."""
    images = value.get("images") if isinstance(value, dict) else None
    if not isinstance(images, list) or not images:
        raise ContractError("image_output_invalid", "The image backend returned no image bytes")
    content = []
    for image in images:
        if (not isinstance(image, dict) or not isinstance(image.get("mimeType"), str)
                or image["mimeType"] not in IMAGE_TYPES or not isinstance(image.get("data"), str)):
            raise ContractError("image_output_invalid", "Expected base64 image data and a supported mimeType")
        try:
            raw = base64.b64decode(image["data"], validate=True)
        except (ValueError, binascii.Error) as error:
            raise ContractError("image_output_invalid", "The image backend returned invalid base64") from error
        if not _signature_matches(raw, image["mimeType"]):
            raise ContractError("image_output_invalid", "Image bytes do not match their mimeType")
        content.append({"type": "image", "mimeType": image["mimeType"], "data": image["data"]})
    return content


# Disable local extensions/hooks and shell tools in the image-only child. Authentication still
# belongs to the user's Codex CLI; no token is read, copied or used as an API credential here.
NATIVE_CONFIG = {
    "forced_login_method": "chatgpt", "model_provider": "openai",
    "features.image_generation": True, "features.shell_tool": False,
    "features.plugins": False, "features.apps": False, "features.hooks": False,
    "features.multi_agent": False, "features.view_image": False,
    "project_doc_max_bytes": 0, "web_search": "disabled",
}
NATIVE_INSTRUCTIONS = (
    "You are an image generation backend. Use only the native image_gen tool exactly once for the "
    "supplied image description. Do not call shells, MCP, external APIs or other tools. Do not read "
    "skills or files. Never draw a substitute in code. Do not retry a failed generation. If the native "
    "tool is unavailable, say so and stop. Leave the original generated file unchanged."
)


def _image_event(item):
    if item.get("status") != "completed" or item.get("failure"):
        raise ContractError("image_native_failed", "The native image tool failed; no fallback or retry was made")
    encoded = item.get("result")
    try:
        raw = base64.b64decode(encoded, validate=True) if isinstance(encoded, str) else b""
    except (ValueError, binascii.Error) as error:
        raise ContractError("image_output_invalid", "The native image tool returned invalid image bytes") from error
    mime = next((mime for mime in IMAGE_TYPES if _signature_matches(raw, mime)), None)
    if not mime:
        raise ContractError("image_output_invalid", "The native image tool returned no supported image bytes")
    return {"mimeType": mime, "data": encoded}


def _native_turn(rpc, prompt, cwd, deadline):
    def call(method, params):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ContractError("image_backend_timeout", "Native image generation timed out; no automatic retry was made")
        # Rpc's long-call progress output starts at 30s. Keep acknowledgements below it so the
        # imagegen CLI stdout remains exactly one result document; never replay an uncertain call.
        return rpc.call(method, params, timeout=min(20, remaining))

    call("initialize", {"clientInfo": {"name": "agent_factory_imagegen", "version": "1"},
                        "capabilities": {"experimentalApi": True}})
    rpc.write({"method": "initialized"})
    account = call("account/read", {"refreshToken": False}).get("account")
    if not isinstance(account, dict) or account.get("type") != "chatgpt":
        raise ContractError("image_chatgpt_login_required", "Sign in to the installed Codex CLI with ChatGPT; API-key authentication is not used")
    # An empty TOML table merges with configured servers; disable every effective server by name
    # before starting the thread so this tool cannot recursively call the local MCP imagegen tool.
    config = call("config/read", {"includeLayers": False}).get("config", {})
    servers = config.get("mcp_servers", {}) if isinstance(config, dict) else {}
    overrides = {"mcp_servers": {name: {"enabled": False} for name in servers}}
    thread = call("thread/start", {"cwd": str(cwd), "approvalPolicy": "never", "sandbox": "read-only",
                                   "modelProvider": "openai", "ephemeral": True, "config": overrides,
                                   "baseInstructions": NATIVE_INSTRUCTIONS})["thread"]["id"]
    turn = call("turn/start", {"threadId": thread, "input": [{"type": "text", "text": prompt}]})["turn"]["id"]
    images = {}
    while time.monotonic() < deadline:
        try:
            event = rpc.event()
        except queue.Empty:
            continue
        params = event.get("params") or {}
        if params.get("threadId") != thread:
            continue
        if event.get("method") == "item/completed" and params.get("turnId") == turn:
            item = params.get("item") or {}
            if item.get("type") == "imageGeneration":
                images[item["id"]] = _image_event(item)
        if event.get("method") == "turn/completed" and params.get("turn", {}).get("id") == turn:
            if params["turn"].get("status") != "completed":
                raise ContractError("image_native_failed", "The native image turn did not complete; no automatic retry was made")
            if not images:
                raise ContractError("image_native_no_output", "Codex returned no native imageGeneration output; text claims are not image evidence")
            return {"kind": "generated-images", "images": list(images.values())}
    raise ContractError("image_backend_timeout", "Native image generation timed out; no automatic retry was made")


def generate(prompt, *, environment=None):
    environment = dict(os.environ if environment is None else environment)
    if not isinstance(prompt, str) or not prompt.strip():
        raise ContractError("image_prompt_invalid", "Image prompt must not be empty")
    try:
        timeout = float(environment.get(TIMEOUT_ENV, "300"))
    except (ValueError, TypeError) as error:
        raise ContractError("image_backend_config_invalid", "Image timeout must be positive seconds") from error
    if not math.isfinite(timeout) or timeout <= 0:
        raise ContractError("image_backend_config_invalid", "Image timeout must be positive seconds")
    executable = shutil.which("codex", path=environment.get("PATH", os.defpath))
    if not executable:
        raise ContractError("image_codex_unavailable", "Install Codex CLI and sign in with ChatGPT to use native image generation")
    executable = native_executable(executable, "codex")
    command = [executable, "app-server", "--listen", "stdio://"]
    for key, value in NATIVE_CONFIG.items():
        command += ["-c", key + "=" + json.dumps(value)]
    for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL", "AGENT_FACTORY_PARENT_STATE", "AGENT_FACTORY_EXECUTION_POLICY"):
        environment.pop(key, None)
    # The native child works in runtime storage, not the caller's source checkout.
    cwd = Path(environment.get("CODEX_HOME") or Path.home() / ".codex")
    if not cwd.is_dir():
        raise ContractError("image_chatgpt_login_required", "The Codex login directory is unavailable; sign in to Codex first")
    deadline = time.monotonic() + timeout
    process = None
    with tempfile.TemporaryFile() as stderr:
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
                                       text=True, encoding="utf-8", env=environment, cwd=cwd)
            return _native_turn(Rpc(process), prompt, cwd, deadline)
        except (OSError, NativeError, ValueError, KeyError, TypeError) as error:
            # Do not leak provider output, account details or credentials into a tool error.
            raise ContractError("image_native_unavailable", "Native Codex image generation could not complete; check Codex login, version and availability. No API fallback or automatic retry was made") from error
        finally:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
                for stream in (process.stdin, process.stdout):
                    if stream:
                        stream.close()
