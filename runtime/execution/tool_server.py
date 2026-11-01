"""Local stdio tool server: the plugin's standard actions as native tools for Claude, Codex and Antigravity.

Each tool runs the same command-line script an agent would run, as that agent's run: the runtime binds the
project and the run, never the tool arguments. The calling run is taken from what the provider supplies and
the agent cannot forge: the parent run state in the server's environment (Claude, Antigravity) or the
session/thread id in the call metadata (Codex, whose app server is shared between runs). Every call checks
the caller's role and run policy against the catalog before anything runs.

This is part of the plugin, separate from the independent Agent Factory MCP service.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from execution import tool_catalog

SERVER_INFO = {"name": "agent-factory", "title": "Agent Factory", "version": "1"}
LEGACY_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26")
SUPPORTED_VERSIONS = ("2026-07-28", *LEGACY_VERSIONS)
PARENT_STATE_ENV = "AGENT_FACTORY_PARENT_STATE"
POLICY_ENV = "AGENT_FACTORY_EXECUTION_POLICY"
TERMINAL = {"completed", "needs-human-decision", "failed", "cancelled", "runtime-error"}
SESSION_KEYS = ("threadId", "sessionId", "antigravity.google/conversation_id")
INSTRUCTIONS = ("Agent Factory standard actions for the calling run: team messages and memory, Documents, lessons, run "
                "records, evidence and tests, and the conductor's dispatch and records. Each tool runs as this run; "
                "the project and run are bound automatically. Results are the command's JSON output.")


class ToolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class Server:
    def __init__(self, host: str, catalog: dict | None = None, environment: dict | None = None):
        self.host = host
        self.environment = dict(os.environ if environment is None else environment)
        self.catalog = catalog or tool_catalog.load()
        self.tools = {tool["name"]: tool for tool in self.catalog["tools"]}
        self.sessions: dict[str, Path] = {}

    # -- identity ---------------------------------------------------------------------------------
    def _home(self) -> Path:
        from storage import paths
        return paths.home_path(self.environment.get("AGENT_FACTORY_HOME") or None)

    def _agent_directories(self):
        home = self._home()
        try:
            registry = json.loads((home / "registry.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for project_id in (registry.get("projects") or {}):
            agents = home / "projects" / project_id / "agents"
            if agents.is_dir():
                yield from (path for path in agents.iterdir() if path.is_dir() and not path.is_symlink())

    @staticmethod
    def _latest_run(agent_directory: Path) -> Path | None:
        runs = agent_directory / "runs"
        if not runs.is_dir():
            return None
        for run in sorted(runs.iterdir(), key=lambda path: path.name, reverse=True):
            if (run / "state.json").is_file():
                return run / "state.json"
        return None

    def _by_session(self, session_id: str) -> Path | None:
        """The agent whose recorded session is this provider session (thread or conversation id)."""
        if session_id in self.sessions:
            return self.sessions[session_id]
        for directory in self._agent_directories():
            for record in (directory / "session.json", self._latest_run(directory)):
                try:
                    value = json.loads(record.read_text(encoding="utf-8")) if record else {}
                except (OSError, ValueError):
                    continue
                if value.get("sessionId") == session_id:
                    self.sessions[session_id] = directory
                    return directory
        return None

    def identify(self, meta: dict | None) -> dict[str, Any]:
        """The calling run's state: from the call's session id where the provider gives one, else the
        parent state the runtime set for this server. Codex shares one app server between runs, so its
        environment is never trusted for identity."""
        meta = meta if isinstance(meta, dict) else {}
        session_id = next((meta[key] for key in SESSION_KEYS if isinstance(meta.get(key), str) and meta[key]), None)
        state_path = None
        if session_id:
            directory = self._by_session(session_id)
            state_path = self._latest_run(directory) if directory else None
        if state_path is None and self.host != "codex":
            locator = self.environment.get(PARENT_STATE_ENV, "").strip()
            state_path = Path(locator) if locator else None
        if state_path is None or not state_path.is_file():
            raise ToolError("tool_caller_unknown", "This tool server serves Agent Factory runs only; no calling run was identified")
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ToolError("tool_caller_unknown", f"The calling run state is unreadable: {error}") from error
        if state.get("statePath") not in (None, str(state_path)):
            raise ToolError("tool_caller_unknown", "The calling run state does not match its location")
        if state.get("status") in TERMINAL:
            raise ToolError("tool_caller_inactive", "The calling run has already ended")
        state["statePath"] = str(state_path)
        return state

    @staticmethod
    def role(state: dict) -> str:
        if state.get("role") == "main":
            return tool_catalog.MAIN
        if state.get("role") == "verification":
            return tool_catalog.VERIFY
        return tool_catalog.EXPLORE if state.get("workProfile") == "explore" else tool_catalog.WORK

    # -- tools -------------------------------------------------------------------------------------
    def listed(self) -> list[dict]:
        # Antigravity starts plugin servers for every session on the machine; outside a run it lists nothing.
        if self.host == "antigravity" and not self.environment.get(PARENT_STATE_ENV):
            return []
        return [{"name": tool["name"], "description": tool["description"], "inputSchema": tool["inputSchema"],
                 "annotations": {"readOnlyHint": tool["effect"] == tool_catalog.READ,
                                 "destructiveHint": False, "openWorldHint": tool["script"] == "imagegen.py"}}
                for tool in self.catalog["tools"]]

    def authorize(self, tool: dict, state: dict, arguments: dict) -> None:
        role = self.role(state)
        if role not in tool["roles"]:
            raise ToolError("tool_role_denied", f"{tool['name']} is not available to a {role} run")
        sandbox = ((state.get("executionPolicy") or {}).get("sandboxPolicy") or {}).get("type")
        if tool["script"] == "imagegen.py" and (sandbox not in ("workspace-write", "danger-full-access")
                or (role == tool_catalog.MAIN and state.get("taskMode", "orchestrate") != "direct")):
            raise ToolError("tool_policy_denied", "Image generation requires a writable direct Main or Work run")
        if tool["effect"] == tool_catalog.PROJECT and role != tool_catalog.MAIN and (role == tool_catalog.EXPLORE or sandbox == "read-only"):
            raise ToolError("tool_policy_denied", f"{tool['name']} changes the project; this run is read-only")
        for key, limits in (tool.get("choiceLimits") or {}).items():
            allowed = limits.get(role)
            if key in arguments and allowed is not None and arguments[key] not in allowed:
                raise ToolError("tool_choice_denied", f"{tool['name']} {key} must be one of {', '.join(allowed)} for a {role} run")

    @staticmethod
    def argv(tool: dict, arguments: dict) -> list[str]:
        if not isinstance(arguments, dict):
            raise ToolError("tool_arguments_invalid", "Arguments must be an object")
        specs = {spec["key"]: spec for spec in tool["arguments"]}
        unknown = sorted(set(arguments) - set(specs))
        if unknown:
            raise ToolError("tool_arguments_invalid", f"Unknown arguments: {', '.join(unknown)}")
        missing = [key for key in tool["inputSchema"].get("required", []) if key not in arguments]
        if missing:
            raise ToolError("tool_arguments_invalid", f"Missing arguments: {', '.join(missing)}")
        # Exclusive argument groups are checked here; schemas stay plain objects every provider accepts.
        for group in tool.get("groups", []):
            given = [key for key in group["keys"] if arguments.get(key) not in (None, False)]
            if len(given) > 1 or (group["required"] and not given):
                raise ToolError("tool_arguments_invalid", ("Give exactly one of: " if group["required"] else "Give at most one of: ")
                                + ", ".join(group["keys"]))
        command = [tool["command"]] if tool["command"] else []
        for spec in tool["arguments"]:
            if spec["key"] not in arguments or arguments[spec["key"]] is None:
                continue
            value, flag = arguments[spec["key"]], spec["flag"]
            if spec["kind"] == "boolean":
                if not isinstance(value, bool):
                    raise ToolError("tool_arguments_invalid", f"{spec['key']} must be true or false")
                if spec["negatable"]:
                    command.append(flag if value else "--no-" + flag[2:])
                elif value != spec["storeFalse"]:
                    command.append(flag)
            elif spec["kind"] == "array":
                items = [str(item) for item in (value if isinstance(value, list) else [value])]
                if flag is None:
                    command += items
                elif spec["repeat"]:
                    for item in items:
                        command += [flag, item]
                else:
                    command += [flag, *items]
            else:
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                command += [str(value)] if flag is None else [flag, str(value)]
        return command

    def run(self, tool: dict, state: dict, arguments: dict) -> dict:
        binding = state.get("runtimeBinding") or {}
        project_root = binding.get("projectRoot")
        if not project_root:
            raise ToolError("tool_caller_unknown", "The calling run has no project binding")
        bound = {"--project-root": project_root, "--runtime-home": binding.get("home"), "--project-id": binding.get("projectId")}
        command = [sys.executable, str(tool_catalog.ROOT / "scripts" / tool["script"]), *self.argv(tool, arguments)]
        for flag in tool.get("bound", []):
            if bound.get(flag):
                command += [flag, str(bound[flag])]
        environment = {key: value for key, value in self.environment.items() if key not in (PARENT_STATE_ENV, POLICY_ENV)}
        environment[PARENT_STATE_ENV] = state["statePath"]
        if state.get("executionPolicy") is not None:
            environment[POLICY_ENV] = json.dumps(state["executionPolicy"], sort_keys=True)
        if binding.get("home"):
            environment["AGENT_FACTORY_HOME"] = str(binding["home"])
        working = state.get("workingDirectory") or project_root
        result = subprocess.run(command, cwd=working if Path(working).is_dir() else project_root, env=environment,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
        output = result.stdout.strip()
        try:
            value = json.loads(output) if output else {}
        except ValueError:
            value = {"output": output}
        failed = result.returncode != 0 or (isinstance(value, dict) and value.get("kind") == "error")
        if failed and not output:
            value = {"kind": "error", "error": {"code": "tool_failed", "message": result.stderr.strip()[-2000:] or f"exit {result.returncode}"}}
        if tool["script"] == "imagegen.py" and not failed:
            from execution.image_generation import image_content
            from storage.errors import ContractError
            try:
                images = image_content(value)
            except ContractError as error:
                raise ToolError(error.code, error.message) from error
            # Send images as MCP image blocks, not JSON text. Avoid duplicating base64 in structuredContent.
            metadata = {"kind": "generated-images", "count": len(images)}
            return {"content": [{"type": "text", "text": json.dumps(metadata)}, *images],
                    "structuredContent": metadata, "isError": False}
        text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        return {"content": [{"type": "text", "text": text}],
                "structuredContent": value if isinstance(value, dict) else {"value": value}, "isError": failed}

    def call(self, params: dict) -> dict:
        tool = self.tools.get(params.get("name"))
        if tool is None:
            raise ToolError("tool_unknown", f"No tool named {params.get('name')}")
        arguments = params.get("arguments") or {}
        state = self.identify(params.get("_meta"))
        self.authorize(tool, state, arguments)
        return self.run(tool, state, arguments)

    # -- protocol ----------------------------------------------------------------------------------
    def handle(self, message: dict) -> dict | None:
        method, request_id = message.get("method"), message.get("id")
        if request_id is None:
            return None  # Notifications need no answer.
        params = message.get("params") or {}
        try:
            if method == "initialize":
                requested = params.get("protocolVersion")
                result = {"protocolVersion": requested if requested in LEGACY_VERSIONS else LEGACY_VERSIONS[1],
                          "capabilities": {"tools": {"listChanged": False}}, "serverInfo": SERVER_INFO, "instructions": INSTRUCTIONS}
            elif method == "server/discover":
                result = {"supportedVersions": list(SUPPORTED_VERSIONS), "capabilities": {"tools": {"listChanged": False}},
                          "serverInfo": SERVER_INFO, "instructions": INSTRUCTIONS, "resultType": "complete"}
            elif method == "tools/list":
                result = {"tools": self.listed(), "resultType": "complete", "ttlMs": 3_600_000, "cacheScope": "private"}
            elif method == "tools/call":
                try:
                    result = {**self.call(params), "resultType": "complete"}
                except ToolError as error:
                    # A refused call is a tool result the agent can read and correct, not a protocol failure.
                    detail = {"kind": "error", "error": {"code": error.code, "message": str(error)}}
                    result = {"content": [{"type": "text", "text": json.dumps(detail)}], "structuredContent": detail,
                              "isError": True, "resultType": "complete"}
            elif method == "ping":
                result = {}
            else:
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Unknown method {method}"}}
        except Exception as error:  # noqa: BLE001 - a broken request never ends the server
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32603, "message": str(error)}}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def serve(self, reader=sys.stdin, writer=sys.stdout) -> None:
        for line in reader:
            try:
                message = json.loads(line)
            except ValueError:
                continue
            reply = self.handle(message) if isinstance(message, dict) else None
            if reply is not None:
                writer.write(json.dumps(reply, ensure_ascii=False) + "\n")
                writer.flush()
