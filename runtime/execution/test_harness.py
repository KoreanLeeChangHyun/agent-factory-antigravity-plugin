"""Runtime-owned test sessions. The supervisor outlives each CLI invocation and the target Host.

Expected results are frozen before launch. Observations, failed operations, reset
generations and human reviews are retained independently from the final verdict.
"""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import queue
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from storage import paths
from storage.errors import ContractError
from storage.files import file_lock, now
from system.browser import playwright_module
from system.containment import process_identity, process_identity_status, terminate_verified_group

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "testing.py"
HERE = Path(__file__).parent
SESSION_ID = re.compile(r"test-[a-f0-9]{32}\Z")
ITEM_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
OPERATORS = ("equals", "contains", "exists", "count", "matches")
DRIVERS = {
    "browser": {"actions": ["click", "fill", "type", "press", "scroll", "navigate", "reload", "back", "select", "check", "tab"], "resetScope": "session browser profile and data; owned foreground process restarted",
                "observations": ["screenshot", "elements", "browser-log", "trace"],
                "review": "interactive live browser screenshot, mouse and keyboard in the same browser context"},
    "command": {"actions": ["exec"], "observations": ["process-log"], "review": "logs and per-scenario human verdicts", "resetScope": "session data; owned foreground process restarted"},
    "vscode": {"actions": ["send", "close", "reload", "click"], "observations": ["bridge-snapshot", "bridge-result"],
               "review": "open the designated native development Host; console records human verdicts",
               "limitations": ["Requires an explicit installed debug-chat bridge command and a development Host.",
                               "An attached pre-existing Host is not isolated or owned; reset is refused without an explicit foreground launcher.",
                               "Bridge capture is HTML replay, not a native-window screenshot.",
                               "Does not provide arbitrary Electron/desktop automation."]},
}


def obj(properties=None, required=()):
    return {"type": "object", "properties": properties or {}, "required": list(required), "additionalProperties": False}


STR = {"type": "string", "minLength": 1}
ARGV = {"type": "array", "items": STR, "minItems": 1}
PROBE = obj({"kind": {"enum": ["browser", "file", "http", "sqlite", "vscode"]},
             "path": STR, "url": STR, "query": STR, "parameters": {"type": "array"}, "jsonPointer": {"type": "string"},
             "selector": STR, "property": {"enum": ["text", "value", "visible", "count", "url", "title"]}}, ("kind",))
CHECK = obj({"id": STR, "probe": PROBE, "operator": {"enum": list(OPERATORS)}, "expected": {},
             "timeoutSec": {"type": "number", "minimum": 0}}, ("id", "probe", "operator", "expected"))
SCENARIO = obj({"id": STR, "title": STR, "checks": {"type": "array", "minItems": 1, "items": CHECK}}, ("id", "title", "checks"))
MANIFEST_SCHEMA = obj({
    "schemaVersion": {"const": 1}, "name": STR,
    "build": obj({"files": {"type": "array", "minItems": 1, "items": STR}}, ("files",)),
    "environment": obj({"kind": {"enum": list(DRIVERS)}, "url": STR, "argv": ARGV,
                        "cwd": STR, "env": {"type": "object", "additionalProperties": {"type": "string"}},
                        "readyUrl": STR, "readyFile": STR, "seed": STR, "timeoutSec": {"type": "number", "exclusiveMinimum": 0},
                        "headed": {"type": "boolean"}, "viewport": obj({"width": {"type": "integer", "minimum": 1}, "height": {"type": "integer", "minimum": 1}}, ("width", "height")),
                        "playwrightModule": STR, "bridgeCommand": ARGV, "chat": STR}, ("kind",)),
    "scenarios": {"type": "array", "minItems": 1, "items": SCENARIO},
}, ("schemaVersion", "name", "build", "environment", "scenarios"))
TOOLS = {
    "test.start": ("Launch an owned test environment; freeze build files, scenarios and expected results", MANIFEST_SCHEMA),
    "test.observe": ("Save screen/elements/logs from the current environment", obj()),
    "test.act": ("Operate a real entrypoint; a successful operation is not a feature pass", obj({
        "scenario": STR, "action": STR, "selector": STR, "text": {"type": "string"}, "key": STR, "url": STR,
        "x": {"type": "number"}, "y": {"type": "number"}, "value": {"type": ["string", "boolean"]},
        "index": {"type": "integer", "minimum": 0}, "argv": ARGV}, ("scenario", "action"))),
    "test.inspect": ("Read actual browser, file, HTTP, SQLite or development-Host state", obj({"probe": PROBE}, ("probe",))),
    "test.check": ("Evaluate a frozen check by ID; callers cannot supply actual or expected values", obj({"scenario": STR, "check": STR}, ("scenario", "check"))),
    "test.reset": ("Restart owned processes, clear browser state and restore session data; retain attempts", obj()),
    "test.review": ("Pause AI mutations and return the interactive review URL, or resume; no CLI human-pass flag", obj({"action": {"enum": ["open", "resume"]}})),
    "test.finish": ("Persist the final report and terminate owned processes without deleting evidence", obj()),
    "test.doctor": ("Detect Node.js, Playwright and an actual Chromium launch; no installation", obj()),
    "test.setup": ("Install missing per-user dependencies outside the checkout, then verify Chromium launch", obj()),
    "test.environments": ("List saved environment manifests and retained sessions for this project", obj()),
    "test.configure": ("Validate and save an environment manifest in project runtime storage", MANIFEST_SCHEMA),
}


def catalog(tool=None):
    selected = {tool: TOOLS[tool]} if tool else TOOLS
    return {"schemaVersion": 1, "kind": "test-tool-catalog", "transport": "python3 <plugin-root>/scripts/testing.py <command>",
            "tools": [{"name": name, "command": name.split(".")[1], "description": value[0], "inputSchema": value[1],
                       "invocation": {"argv": ["python3", "<plugin-root>/scripts/testing.py", name.split(".")[1], "--project-root", "<project-root>"],
                                      "sessionOption": "--session" if name in {"test.observe", "test.act", "test.inspect", "test.check", "test.reset", "test.review", "test.finish"} else None,
                                      "profileOption": "--profile" if name == "test.configure" else None,
                                      "inputOption": "--file" if name == "test.start" else "--input-json" if name in {"test.act", "test.inspect", "test.check", "test.review", "test.configure"} else None},
                       "output": {"session": "test-<32 hex>", "evidence": "private session-owned evidence paths", "verdicts": ["passed", "failed", "unverified"]}}
                      for name, value in selected.items()],
            "drivers": DRIVERS, "probeSchema": PROBE,
            "placeholders": ["${projectRoot}", "${sessionDir}", "${dataDir}", "${port}"],
            "preconditions": ["Registered Agent Factory project", "An installed Node.js and Playwright/browser for browser sessions",
                              "Build files identify the actual deployed executable/bundle; use setup explicitly for missing browser dependencies"],
            "limitations": ["A frozen expected result is still a specification, not proof that the product requirement is correct.",
                            "Local profiles/data isolate test state; target commands are not OS-sandboxed.",
                            "Managed commands must remain in the foreground; detached external services are not owned.",
                            "Review confirms the session build and reset generation only; human identity is not independently authenticated."]}


def validate(value, schema, label="input"):
    """Validate the same small JSON Schema vocabulary the catalog publishes."""
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        raise ContractError("invalid_input", f"{label}: expected {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise ContractError("invalid_input", f"{label}: expected one of {schema['enum']}")
    types = schema.get("type")
    if types:
        types = types if isinstance(types, list) else [types]
        predicates = {"object": lambda: isinstance(value, dict), "array": lambda: isinstance(value, list),
                      "string": lambda: isinstance(value, str), "number": lambda: type(value) in (int, float),
                      "integer": lambda: type(value) is int, "boolean": lambda: type(value) is bool}
        if not any(predicates[kind]() for kind in types):
            raise ContractError("invalid_input", f"{label}: expected {types}")
    if isinstance(value, dict):
        missing = set(schema.get("required", [])) - value.keys()
        extra = value.keys() - schema.get("properties", {}).keys()
        if missing or (extra and schema.get("additionalProperties") is False):
            raise ContractError("invalid_input", f"{label}: missing {sorted(missing)}, unexpected {sorted(extra)}")
        for key, item in value.items():
            field = schema.get("properties", {}).get(key, schema.get("additionalProperties", {}))
            if isinstance(field, dict):
                validate(item, field, f"{label}.{key}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ContractError("invalid_input", f"{label}: requires at least {schema['minItems']} items")
        for index, item in enumerate(value):
            validate(item, schema.get("items", {}), f"{label}[{index}]")
    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        raise ContractError("invalid_input", f"{label}: must not be empty")
    if type(value) in (int, float):
        if not math.isfinite(value) or value < schema.get("minimum", value) or value <= schema.get("exclusiveMinimum", value - 1):
            raise ContractError("invalid_input", f"{label}: outside permitted range")


def read(path):
    return paths.read(path)


def write(path, value):
    paths.write(path, value)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def root_binding(args):
    binding = paths.resolve(args.project_root, home=args.runtime_home, project_id=args.project_id)
    if not binding["registered"]:
        raise ContractError("project_uninitialized", "Initialize this project with exec.py init first")
    return binding


def directory(args):
    if not SESSION_ID.fullmatch(args.session):
        raise ContractError("invalid_session", "Invalid test session ID")
    path = Path(root_binding(args)["runtimeRoot"]) / "test-sessions" / args.session
    paths.inspect(path)
    return path


def within(root, value, *, exists=True):
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve(strict=exists)
    if not resolved.is_relative_to(root.resolve()):
        raise ContractError("path_outside_environment", f"Path must stay inside {root}")
    return resolved


def build_snapshot(root, manifest):
    files = {}
    for name in manifest["build"]["files"]:
        path = within(root, name)
        if not path.is_file():
            raise ContractError("invalid_build", f"Build entry is not a file: {name}")
        files[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"id": digest(files), "files": files}


def seed_snapshot(directory):
    paths.inspect(directory)
    if not directory.is_dir():
        raise ContractError("invalid_seed", "Frozen seed directory is missing")
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ContractError("invalid_seed", "Frozen seed contains a symlink")
        if path.is_file():
            files[str(path.relative_to(directory))] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.is_dir():
            files[str(path.relative_to(directory)) + "/"] = None
    return digest(files)


def freeze_manifest(root, manifest):
    validate(manifest, MANIFEST_SCHEMA, "manifest")
    ids = set()
    for scenario in manifest["scenarios"]:
        if not ITEM_ID.fullmatch(scenario["id"]) or scenario["id"] in ids:
            raise ContractError("invalid_manifest", "Scenario IDs must be unique safe identifiers")
        ids.add(scenario["id"])
        checks = set()
        for check in scenario["checks"]:
            if not ITEM_ID.fullmatch(check["id"]) or check["id"] in checks:
                raise ContractError("invalid_manifest", "Check IDs must be unique safe identifiers within a scenario")
            checks.add(check["id"])
            if check["operator"] == "matches":
                if not isinstance(check["expected"], str):
                    raise ContractError("invalid_manifest", "matches requires a regular expression string")
                try:
                    re.compile(check["expected"])
                except re.error as error:
                    raise ContractError("invalid_manifest", f"Invalid check regular expression: {error}") from error
            if check["operator"] == "exists" and type(check["expected"]) is not bool:
                raise ContractError("invalid_manifest", "exists requires a boolean expected value")
            if check["operator"] == "count" and (type(check["expected"]) is not int or check["expected"] < 0):
                raise ContractError("invalid_manifest", "count requires a nonnegative integer expected value")
            probe = check["probe"]
            required = {"file": ["path"], "http": ["url"], "sqlite": ["path", "query"], "browser": ["property"], "vscode": []}[probe["kind"]]
            if any(not probe.get(field) for field in required):
                raise ContractError("invalid_manifest", f"{probe['kind']} probe requires {required}")
    env = manifest["environment"]
    if env["kind"] == "browser" and not env.get("url"):
        raise ContractError("invalid_manifest", "Browser sessions require environment.url")
    if env["kind"] == "vscode" and not env.get("bridgeCommand"):
        raise ContractError("invalid_manifest", "VS Code sessions require an explicit debug-chat bridgeCommand")
    if env.get("seed"):
        seed = within(root, env["seed"])
        if not seed.is_dir() or seed.is_symlink() or any(p.is_symlink() for p in seed.rglob("*")):
            raise ContractError("invalid_manifest", "Seed must be a project directory without symlinks")
    return build_snapshot(root, manifest)


def start(args):
    if args.wait_sec <= 0:
        raise ContractError("invalid_wait", "wait-sec must be positive")
    binding = root_binding(args)
    root = Path(binding["projectRoot"])
    manifest = json.loads(args.file.read_text(encoding="utf-8"))
    build = freeze_manifest(root, manifest)
    session = "test-" + secrets.token_hex(16)
    target = Path(binding["runtimeRoot"]) / "test-sessions" / session
    paths.mkdir(target)
    write(target / "manifest.json", manifest)
    seed = manifest["environment"].get("seed")
    if seed:
        shutil.copytree(within(root, seed), target / "seed")
    state = {"schemaVersion": 1, "session": session, "projectRoot": str(root), "manifestHash": digest(manifest),
             "build": build, "driver": manifest["environment"]["kind"], "name": manifest["name"],
             "executionStatus": "starting", "outcome": "unverified", "generation": 0, "startedAt": now(),
             "automationVerdict": "unverified", "humanVerdict": "pending",
             "seedHash": seed_snapshot(target / "seed") if seed else None,
             "humanReview": {}, "checks": {}, "actions": [], "owned": [], "evidenceCount": 0}
    write(target / "state.json", state)
    with (target / "supervisor.log").open("a", encoding="utf-8") as log:
        from execution.test_environment import environment
        child = subprocess.Popen([sys.executable, str(SCRIPT), "_serve", "--directory", str(target)],
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=os.name != "nt",
                                 env=environment(binding["home"]))
    deadline = time.monotonic() + args.wait_sec
    while time.monotonic() < deadline:
        state = read(target / "state.json")
        if state["executionStatus"] != "starting":
            return public_state(target, state)
        if child.poll() is not None:
            raise ContractError("startup_failed", f"Supervisor exited; session={session}; log={target / 'supervisor.log'}")
        time.sleep(0.05)
    raise ContractError("startup_pending", f"Startup is still pending; session={session}. Use status or finish; do not retry start")


def public_state(target, state):
    return {**state, "directory": str(target), "manifest": str(target / "manifest.json"),
            "scenarios": read(target / "manifest.json")["scenarios"],
            "report": str(target / "report.json") if (target / "report.json").exists() else None,
            "events": str(target / "events.jsonl"), "driverCapabilities": DRIVERS[state["driver"]]}


def status(args):
    target = directory(args)
    state = read(target / "state.json")
    if state["executionStatus"] not in ("finished", "failed") and state.get("supervisor"):
        if process_identity_status(state["supervisor"]) != "match":
            state = {**state, "executionStatus": "interrupted", "outcome": "unverified"}
    return public_state(target, state)


def request(args, data):
    if args.wait_sec <= 0:
        raise ContractError("invalid_wait", "wait-sec must be positive")
    target = directory(args)
    state = read(target / "state.json")
    if args.command == "finish" and state["executionStatus"] == "finished":
        return read(target / "report.json")
    if not state.get("supervisor") or process_identity_status(state["supervisor"]) != "match":
        if args.command != "finish":
            raise ContractError("supervisor_unavailable", "Session supervisor is unavailable; use finish to recover owned processes")
        with file_lock(target / "recovery.lock"):
            for identity in reversed(state.get("owned", [])):
                terminate_verified_group(identity)
            state.update(executionStatus="finished", outcome="unverified", interrupted=True, finishedAt=now())
            write(target / "state.json", state)
            write(target / "report.json", public_state(target, state))
        return public_state(target, state)
    connection = read(target / "connection.json")
    operation = secrets.token_hex(16)
    body = json.dumps({"id": operation, "command": args.command, "input": data}).encode()
    req = Request(connection["url"] + "/command", data=body,
                  headers={"Authorization": "Bearer " + connection["token"], "Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=args.wait_sec) as response:
            reply = json.load(response)
    except (TimeoutError, URLError) as error:
        raise ContractError("operation_uncertain", f"Request {operation} may still be running; inspect status and {target / (operation + '.json')}; do not repeat a mutation blindly") from error
    if "error" in reply:
        raise ContractError(reply["error"]["code"], reply["error"]["message"])
    return reply


def pointer(value, path):
    if not path:
        return value
    if not path.startswith("/"):
        raise ContractError("invalid_pointer", "jsonPointer must be empty or begin with /")
    for component in path[1:].split("/"):
        key = component.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def compare(actual, operator, expected):
    if operator == "equals":
        return type(actual) is type(expected) and digest(actual) == digest(expected)
    if operator == "contains":
        return expected in actual
    if operator == "exists":
        return (actual is not None) == expected
    if operator == "count":
        return len(actual) == expected
    if operator == "matches":
        return isinstance(actual, str) and re.search(expected, actual) is not None
    raise ContractError("invalid_operator", "Unknown comparison operator")


class Browser:
    def __init__(self, session):
        env = session.manifest["environment"]
        module = env.get("playwrightModule") or playwright_module(session.root)
        self.log = (session.target / "browser-worker.log").open("a", encoding="utf-8")
        self.process = subprocess.Popen(["node", str(HERE / "test-browser.cjs")], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.log, text=True, bufsize=1, start_new_session=os.name != "nt")
        session.own(self.process)
        self.replies = queue.Queue()
        def consume():
            for line in self.process.stdout:
                try:
                    self.replies.put(json.loads(line))
                except ValueError:
                    self.replies.put({"ok": False, "error": "Browser worker emitted invalid JSON"})
            self.replies.put({"ok": False, "error": "Browser worker stopped; see browser-worker.log"})
        threading.Thread(target=consume, daemon=True).start()
        self.timeout = env.get("timeoutSec", 30)
        self.call("start", {"module": module, "url": session.expand(env["url"]), "directory": str(session.target),
                            "headed": env.get("headed", False), "viewport": env.get("viewport", {"width": 1280, "height": 800}),
                            "timeoutMs": self.timeout * 1000})

    def call(self, op, data=None):
        if self.process.poll() is not None:
            raise ContractError("browser_unavailable", "Browser worker is not running")
        self.process.stdin.write(json.dumps({"op": op, "input": data or {}}) + "\n")
        self.process.stdin.flush()
        try:
            reply = self.replies.get(timeout=self.timeout + 10)
        except queue.Empty as error:
            # Never reuse a stream where a late reply could be mistaken for the next operation.
            self.process.kill()
            raise ContractError("browser_timeout", "Browser worker timed out and was stopped; reset before continuing") from error
        if not reply.get("ok"):
            raise ContractError("browser_operation_failed", reply.get("error", "Unknown browser failure"))
        return reply.get("result")

    def close(self):
        try:
            if self.process.poll() is None:
                self.call("stop")
        finally:
            with contextlib.suppress(subprocess.TimeoutExpired):
                self.process.wait(timeout=5)
            self.log.close()


class Session:
    def __init__(self, target):
        self.target = target
        self.manifest = read(target / "manifest.json")
        self.state = read(target / "state.json")
        self.root = Path(self.state["projectRoot"])
        self.lock = threading.RLock()
        self.browser = None
        self.processes = []
        self.log_handles = []
        self.server = None
        self.review_token = secrets.token_urlsafe(32)
        self.token = secrets.token_urlsafe(32)
        self.operation = None
        with socket.socket() as available:
            available.bind(("127.0.0.1", 0))
            self.port = available.getsockname()[1]

    def save(self):
        self.state["updatedAt"] = now()
        write(self.target / "state.json", self.state)

    def event(self, event, **data):
        line = {"at": now(), "session": self.state["session"], "generation": self.state["generation"],
                "operation": self.operation, "event": event, **data}
        with (self.target / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(line, ensure_ascii=False) + "\n")

    def expand(self, value):
        for key, item in {"projectRoot": self.root, "sessionDir": self.target, "dataDir": self.target / "data", "port": self.port}.items():
            value = value.replace("${" + key + "}", str(item))
        return value

    def own(self, process):
        self.processes.append(process)
        self.state["owned"].append(process_identity(process.pid))
        self.save()

    def environment(self):
        env = {**os.environ, "AGENT_FACTORY_HOME": str(self.target / "target-runtime"), "AF_TEST_DATA_DIR": str(self.target / "data"),
               "AF_TEST_SESSION": self.state["session"], "AF_TEST_PORT": str(self.port)}
        env.update({key: self.expand(value) for key, value in self.manifest["environment"].get("env", {}).items()})
        return env

    def command(self, argv, *, background=False):
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
            raise ContractError("invalid_command", "argv must be a nonempty array of argument tokens")
        cwd = within(self.root, self.expand(self.manifest["environment"].get("cwd", ".")))
        log_path = self.target / f"process-{secrets.token_hex(8)}.log"
        log = log_path.open("w", encoding="utf-8")
        self.log_handles.append(log)
        process = subprocess.Popen([self.expand(x) for x in argv], cwd=cwd, env=self.environment(),
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=os.name != "nt")
        self.own(process)
        self.event("process.started", pid=process.pid, log=str(log_path))
        if background:
            return process
        try:
            code = process.wait(timeout=self.manifest["environment"].get("timeoutSec", 30))
        except subprocess.TimeoutExpired as error:
            terminate_verified_group(process_identity(process.pid), process)
            raise ContractError("command_timeout", f"Command timed out; log={log_path}") from error
        self.event("process.completed", pid=process.pid, exitCode=code, log=str(log_path))
        return {"exitCode": code, "log": str(log_path), "output": log_path.read_text(encoding="utf-8", errors="replace")}

    def setup(self):
        data = self.target / "data"
        paths.mkdir(data)
        seed = self.manifest["environment"].get("seed")
        if seed:
            shutil.copytree(self.target / "seed", data, dirs_exist_ok=True)
        env = self.manifest["environment"]
        self.state["environment"] = {"kind": env["kind"], "dataDirectory": str(data),
                                     "ownership": "attached" if env["kind"] == "vscode" and not env.get("argv") else "session-owned",
                                     "url": self.expand(env["url"]) if env.get("url") else None}
        process = self.command(env["argv"], background=True) if env.get("argv") else None
        deadline = time.monotonic() + env.get("timeoutSec", 30)
        while True:
            if process and process.poll() is not None:
                raise ContractError("target_stopped", "Target process stopped before the environment became ready; inspect process logs")
            ready = True
            if env.get("readyFile"):
                ready = Path(self.expand(env["readyFile"])).is_file()
            if ready and env.get("readyUrl"):
                try:
                    with urlopen(self.expand(env["readyUrl"]), timeout=1) as response:
                        ready = response.status < 400
                except (OSError, URLError):
                    ready = False
            if ready:
                break
            if time.monotonic() >= deadline:
                raise ContractError("environment_not_ready", "Target did not become ready; inspect process logs")
            time.sleep(0.1)
        if env["kind"] == "browser":
            self.browser = Browser(self)
        if env["kind"] == "vscode":
            self.bridge("status")
        self.event("environment.ready", environment=self.state["environment"], build=self.state["build"]["id"])

    def bridge(self, action, *tokens):
        env = self.manifest["environment"]
        result = self.command([*env["bridgeCommand"], action, "--json", *(["--chat", env["chat"]] if env.get("chat") else []), *tokens])
        if result["exitCode"]:
            raise ContractError("bridge_failed", f"VS Code bridge failed; log={result['log']}")
        output = result["output"]
        # The bridge CLI emits progress before its final JSON document.
        for match in re.finditer(r"(?m)^\{", output):
            try:
                return json.loads(output[match.start():])
            except ValueError:
                continue
        raise ContractError("bridge_invalid_response", f"Bridge returned no JSON; log={result['log']}")

    def current(self):
        try:
            manifest_changed = digest(read(self.target / "manifest.json")) != self.state["manifestHash"]
            build_changed = build_snapshot(self.root, self.manifest) != self.state["build"]
            seed_changed = bool(self.state.get("seedHash")) and seed_snapshot(self.target / "seed") != self.state["seedHash"]
        except (OSError, ValueError, ContractError) as error:
            self.state.update(executionStatus="stale", outcome="unverified", humanReview={})
            self.save()
            raise ContractError("build_unavailable", "Frozen manifest/build can no longer be inspected; start a new session") from error
        if manifest_changed or build_changed or seed_changed:
            self.state.update(executionStatus="stale", outcome="unverified", humanReview={})
            self.save()
            raise ContractError("manifest_changed" if manifest_changed else "seed_changed" if seed_changed else "build_changed", "Frozen manifest/build/seed changed; start a new session")

    def evidence(self, kind, value):
        self.state["evidenceCount"] += 1
        path = self.target / f"evidence-{self.state['evidenceCount']:06d}.json"
        write(path, {"at": now(), "kind": kind, "generation": self.state["generation"], "operation": self.operation,
                     "build": self.state["build"]["id"], "value": value})
        return str(path)

    def observe(self):
        if self.browser:
            shot = self.target / f"screen-{secrets.token_hex(8)}.png"
            value = self.browser.call("observe", {"path": str(shot)})
            value["screenshot"] = str(shot)
            value["captureKind"] = "live-browser-viewport"
        elif self.state["driver"] == "vscode":
            value = {"snapshot": self.bridge("snapshot"), "captureKind": "bridge-snapshot", "nativeWindowCaptured": False}
        else:
            value = {"logs": [{"path": str(path), "text": path.read_text(encoding="utf-8", errors="replace")}
                              for path in sorted(self.target.glob("process-*.log"))]}
        value["evidence"] = self.evidence("observation", value)
        return value

    def probe(self, probe):
        kind = probe["kind"]
        if kind == "browser":
            if not self.browser:
                raise ContractError("unsupported_probe", "Browser probe requires a browser session")
            value = self.browser.call("inspect", probe)
        elif kind == "vscode":
            if self.state["driver"] != "vscode":
                raise ContractError("unsupported_probe", "VS Code probe requires a VS Code session")
            value = self.bridge("snapshot")
        elif kind in ("file", "sqlite"):
            name = self.expand(probe["path"])
            base = self.target if Path(name).is_absolute() and Path(name).resolve().is_relative_to(self.target) else self.root
            path = within(base, name, exists=False)
            if kind == "file":
                value = path.read_text(encoding="utf-8") if path.is_file() else None
                if "jsonPointer" in probe and value is not None:
                    value = json.loads(value)
            else:
                with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as database:
                    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
                    database.set_authorizer(lambda op, *args: sqlite3.SQLITE_OK if op in allowed else sqlite3.SQLITE_DENY)
                    value = [list(row) for row in database.execute(probe["query"], probe.get("parameters", []))]
        elif kind == "http":
            url = self.expand(probe["url"])
            if urlsplit(url).scheme not in ("http", "https"):
                raise ContractError("invalid_url", "HTTP probes require http(s) URLs")
            try:
                response = urlopen(url, timeout=self.manifest["environment"].get("timeoutSec", 30))
            except HTTPError as error:
                response = error
            with response:
                body = response.read().decode("utf-8")
                try:
                    body = json.loads(body)
                except ValueError:
                    pass
                value = {"status": response.code, "body": body}
        else:
            raise ContractError("unsupported_probe", f"Unsupported probe: {kind}")
        return pointer(value, probe.get("jsonPointer", "")) if value is not None else None

    def act(self, data, *, human=False):
        if self.state["executionStatus"] == "reviewing" and not human:
            raise ContractError("human_review_active", "Automation is paused for human review; resume before acting")
        # A partially failed interaction can also change the application. Old
        # checks for that scenario must not certify the newly changed state.
        self.state["checks"] = {key: value for key, value in self.state["checks"].items()
                                if value["scenario"] != data.get("scenario")}
        self.state["humanReview"] = {}
        if self.browser:
            result = self.browser.call("act", {**data, **({"url": self.expand(data["url"])} if "url" in data else {})})
        elif self.state["driver"] == "command" and data["action"] == "exec":
            result = self.command(data["argv"])
        elif self.state["driver"] == "vscode" and data["action"] in DRIVERS["vscode"]["actions"]:
            action = data["action"]
            result = self.bridge("capture", "--click", data["selector"], "--keep") if action == "click" else self.bridge(action, *([data["text"]] if action == "send" else []))
        else:
            raise ContractError("unsupported_action", f"Action {data['action']} is unavailable for {self.state['driver']}")
        item = {"at": now(), "scenario": data.get("scenario"), "action": data["action"], "source": "human-review" if human else "automation",
                "generation": self.state["generation"], "evidence": self.evidence("action", {"input": data, "result": result})}
        self.state["actions"].append(item)
        self.state["humanReview"] = {}
        return {"performed": True, **item, "result": result}

    def scenario(self, identifier):
        found = next((s for s in self.manifest["scenarios"] if s["id"] == identifier), None)
        if found is None:
            raise ContractError("scenario_not_found", f"Unknown scenario: {identifier}")
        return found

    def check(self, data):
        scenario = self.scenario(data["scenario"])
        check = next((c for c in scenario["checks"] if c["id"] == data["check"]), None)
        if check is None:
            raise ContractError("check_not_found", "Check is not in the frozen manifest")
        executed = any(a["scenario"] == scenario["id"] and a["generation"] == self.state["generation"] for a in self.state["actions"])
        result = {"scenario": scenario["id"], "check": check["id"], "generation": self.state["generation"], "at": now(),
                  "expected": check["expected"], "operator": check["operator"], "verdict": "unverified"}
        if not executed:
            result["reason"] = "No scenario action has executed in this reset generation"
        else:
            deadline = time.monotonic() + check.get("timeoutSec", 0)
            while True:
                try:
                    actual = self.probe(check["probe"])
                    result.pop("reason", None)
                    if actual is None and check["operator"] != "exists":
                        result.update(actual=None, verdict="unverified", reason="Probe source is missing")
                    else:
                        result.update(actual=actual, verdict="passed" if compare(actual, check["operator"], check["expected"]) else "failed")
                except (ContractError, OSError, ValueError, KeyError, IndexError, TypeError, sqlite3.Error) as error:
                    result.update(verdict="unverified", reason=str(error))
                if result["verdict"] == "passed" or time.monotonic() >= deadline:
                    break
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        result["evidence"] = self.evidence("check", result)
        self.state["checks"][scenario["id"] + "/" + check["id"]] = result
        return result

    def automation_outcome(self):
        verdicts = [self.state["checks"].get(s["id"] + "/" + c["id"], {}).get("verdict", "unverified")
                    for s in self.manifest["scenarios"] for c in s["checks"]]
        if self.state.get("executionStatus") in ("stale", "failed") or self.state.get("interrupted"):
            return "unverified"
        return "failed" if "failed" in verdicts else "unverified" if "unverified" in verdicts else "passed"

    def outcome(self):
        automation = self.automation_outcome()
        reviews = [self.state["humanReview"].get(s["id"], {}).get("verdict", "pending") for s in self.manifest["scenarios"]]
        human = "failed" if "failed" in reviews else "pending" if "pending" in reviews else "passed"
        self.state.update(automationVerdict=automation, humanVerdict=human)
        return "failed" if "failed" in (automation, human) else "passed" if automation == human == "passed" else "unverified"

    def stop(self):
        if self.browser:
            try:
                self.browser.close()
            except (ContractError, OSError) as error:
                self.event("browser.close.error", error=str(error))
            self.browser = None
        for identity, process in reversed(list(zip(self.state["owned"], self.processes))):
            terminate_verified_group(identity, process)
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=1)
        self.processes.clear()
        self.state["owned"] = []
        for log in self.log_handles:
            log.close()
        self.log_handles.clear()

    def dispatch(self, command, data):
        if command == "finish":
            try:
                self.current()
            except (ContractError, OSError):
                self.state.update(executionStatus="stale", outcome="unverified", humanReview={})
            self.state["outcome"] = self.outcome()
            self.stop()
            self.state.update(executionStatus="finished", finishedAt=now())
            self.save()
            report = public_state(self.target, self.state)
            report["report"] = str(self.target / "report.json")
            report["scenarios"] = [{"id": s["id"], "title": s["title"], "checks": [self.state["checks"].get(s["id"] + "/" + c["id"], {"check": c["id"], "verdict": "unverified"}) for c in s["checks"]],
                                    "humanReview": self.state["humanReview"].get(s["id"], {"verdict": "pending"})} for s in self.manifest["scenarios"]]
            report["artifacts"] = [str(path) for pattern in ("evidence-*.json", "screen-*.png", "trace-*.zip", "process-*.log", "browser-*.jsonl") for path in sorted(self.target.glob(pattern))]
            write(self.target / "report.json", report)
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return report
        if self.state["executionStatus"] not in ("ready", "reviewing"):
            raise ContractError("session_not_ready", f"Session is {self.state['executionStatus']}")
        self.current()
        validate(data, TOOLS["test." + command][1])
        if command == "observe":
            return self.observe()
        if command == "inspect":
            value = self.probe(data["probe"])
            return {"value": value, "evidence": self.evidence("inspection", {"probe": data["probe"], "value": value})}
        if command == "act":
            self.scenario(data["scenario"])
            return self.act(data)
        if command == "check":
            return self.check(data)
        if command == "reset":
            if self.state["executionStatus"] == "reviewing":
                raise ContractError("human_review_active", "Resume before resetting the environment")
            if self.state["environment"]["ownership"] == "attached":
                raise ContractError("unsupported_reset", "Cannot reset an attached VS Code Host; provide an owned foreground launcher and isolated profile")
            self.stop()
            # Only this session's generated profile and data may be removed. Evidence stays.
            for name in ("data", "browser-profile", "target-runtime"):
                owned = self.target / name
                paths.inspect(owned, missing=True)
                if owned.exists():
                    shutil.rmtree(owned)
            self.state.update(generation=self.state["generation"] + 1, checks={}, humanReview={}, outcome="unverified")
            self.state["executionStatus"] = "starting"
            self.save()
            try:
                self.setup()
            except Exception:
                self.state["executionStatus"] = "failed"
                raise
            self.state["executionStatus"] = "ready"
            return {"reset": True, "generation": self.state["generation"]}
        if command == "review":
            if data.get("action", "open") == "resume":
                self.state["executionStatus"] = "ready"
                return {"resumed": True}
            self.state["executionStatus"] = "reviewing"
            return {"paused": True, "reviewUrl": self.review_url(), "driver": self.state["driver"],
                    "nativeTarget": self.manifest["environment"].get("chat") if self.state["driver"] == "vscode" else None}
        raise ContractError("unsupported_tool", f"Unknown test tool: {command}")

    def review_url(self):
        return f"http://127.0.0.1:{self.server.server_port}/review/{self.review_token}/"

    def execute(self, operation, command, data):
        with self.lock:
            self.operation = operation
            self.event("operation.started", command=command)
            try:
                result = self.dispatch(command, data)
                result = {"session": self.state["session"], "operation": operation, **result}
            except Exception as error:
                result = {"session": self.state["session"], "operation": operation,
                          "error": {"code": error.code if isinstance(error, ContractError) else "operation_failed", "message": str(error)}}
                self.event("operation.failed", command=command, error=result["error"])
            self.state["outcome"] = self.outcome() if self.state["executionStatus"] != "finished" else self.state["outcome"]
            self.save()
            write(self.target / f"{operation}.json", result)
            self.event("operation.completed", command=command, result=str(self.target / f"{operation}.json"))
            self.operation = None
            return result

    def human(self, data):
        with self.lock:
            if self.state["executionStatus"] != "reviewing":
                raise ContractError("review_not_active", "Open human review first")
            self.current()
            action = data.get("action")
            if action == "observe":
                observed = self.observe()
                self.save()
                return observed
            if action == "act":
                if not self.browser:
                    raise ContractError("unsupported_action", "Use the native application for this driver")
                validate(data["input"], TOOLS["test.act"][1])
                self.scenario(data["input"]["scenario"])
                result = self.act(data["input"], human=True)
                self.state["outcome"] = self.outcome()
                self.event("human.action", action=data["input"]["action"], scenario=data["input"].get("scenario"))
                self.save()
                return result
            if action == "verdict":
                self.scenario(data.get("scenario"))
                if data.get("verdict") not in ("passed", "failed") or not isinstance(data.get("note", ""), str):
                    raise ContractError("invalid_review", "Review requires passed/failed and a text note")
                value = {"verdict": data["verdict"], "note": data.get("note", ""), "at": now(),
                         "generation": self.state["generation"], "build": self.state["build"]["id"], "source": "review-console"}
                self.state["humanReview"][data["scenario"]] = value
                self.state["outcome"] = self.outcome()
                self.evidence("human-review", {"scenario": data["scenario"], **value})
                self.event("human.reviewed", scenario=data["scenario"], **value)
                self.save()
                return value
            raise ContractError("invalid_review", "Unknown review action")


def handler(session):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status_code, payload, content_type="application/json"):
            body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status_code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' blob:; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def review_path(self):
            return f"/review/{session.review_token}/"

        def do_GET(self):
            path = urlsplit(self.path).path
            prefix = self.review_path()
            if not path.startswith(prefix):
                self.send(404, {"error": "not found"})
                return
            leaf = path[len(prefix):]
            with session.lock:
                if leaf == "":
                    self.send(200, (HERE / "test-review.html").read_bytes(), "text/html; charset=utf-8")
                elif leaf == "state":
                    self.send(200, {"state": session.state, "scenarios": session.manifest["scenarios"]})
                elif leaf.startswith("screen-") and re.fullmatch(r"screen-[a-f0-9]+\.png", leaf):
                    path = session.target / leaf
                    self.send(200, path.read_bytes(), "image/png") if path.is_file() else self.send(404, {})
                else:
                    self.send(404, {})

        def do_POST(self):
            try:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                if self.path == "/command":
                    if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + session.token):
                        self.send(403, {"error": "forbidden"})
                        return
                    operation = data.get("id", "")
                    if not re.fullmatch(r"[a-f0-9]{32}", operation):
                        raise ContractError("invalid_operation", "Invalid operation ID")
                    saved = session.target / f"{operation}.json"
                    with session.lock:
                        result = read(saved) if saved.exists() else session.execute(operation, data["command"], data.get("input", {}))
                    self.send(200, result)
                elif self.path == self.review_path() + "action":
                    origin = self.headers.get("Origin")
                    if origin and origin != f"http://127.0.0.1:{session.server.server_port}":
                        self.send(403, {"error": "foreign origin"})
                        return
                    self.send(200, session.human(data))
                else:
                    self.send(404, {})
            except Exception as error:
                self.send(400, {"error": str(error)})
    return Handler


def serve(target):
    paths.inspect(target)
    session = Session(target)
    session.state["supervisor"] = process_identity(os.getpid())
    session.save()
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler(session))
    session.server = server
    write(target / "connection.json", {"url": f"http://127.0.0.1:{server.server_port}", "token": session.token})
    try:
        session.setup()
        session.state["executionStatus"] = "ready"
        session.save()
        server.serve_forever(poll_interval=0.1)
        return 0
    except Exception as error:
        session.state.update(executionStatus="failed", outcome="unverified", error=str(error))
        session.event("environment.failed", error=str(error))
        session.save()
        return 1
    finally:
        session.stop()
        session.save()
        server.server_close()
