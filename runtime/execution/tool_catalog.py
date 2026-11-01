"""The plugin's standard actions as native tools: which commands each role may call, generated from argparse.

The command-line scripts stay the source of truth. This module lists the agent-facing commands and the
roles that may call them; `distribution/tool_usage.py` reads each script's argparse definition and writes
the resulting tool schemas to `tool_catalog.json`, which the local tool server loads. Commands only the
Human, the extension or the runtime use (setup, migration, worker removal, memory approval) are not tools.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = Path(__file__).with_name("tool_catalog.json")
VERSION = 1
# The runtime supplies these from the calling run; a tool never takes them as arguments.
BOUND_OPTIONS = {"--project-root", "--runtime-home", "--project-id"}

MAIN, WORK, EXPLORE, VERIFY = "main", "work", "explore", "verification"
EVERYONE = (MAIN, WORK, EXPLORE, VERIFY)
PERFORMERS = (MAIN, WORK, VERIFY)
# Effects: "read" changes nothing; "records" writes only runtime records (messages, memory, lessons, intents);
# "project" may change project files or start work. Explore performers and read-only runs get read and records.
READ, RECORDS, PROJECT = "read", "records", "project"
# (script, subcommand or None, roles, effect).
COMMANDS = [
    ("imagegen", None, (MAIN, WORK), PROJECT),
    # Team messages and shared memory.
    ("messages", "peers", EVERYONE, READ), ("messages", "room", EVERYONE, READ), ("messages", "inbox", EVERYONE, RECORDS),
    ("messages", "send", EVERYONE, RECORDS), ("messages", "post", EVERYONE, RECORDS),
    # The project room's fixed forms belong to the conductors labeled with a domain.
    ("messages", "claim", (MAIN,), RECORDS), ("messages", "release", (MAIN,), RECORDS),
    ("messages", "change", (MAIN,), RECORDS), ("messages", "status", (MAIN,), READ),
    ("memory", "list", EVERYONE, READ), ("memory", "search", EVERYONE, READ), ("memory", "show", EVERYONE, READ),
    ("memory", "write", EVERYONE, RECORDS),
    # Documents.
    ("search_documents", None, EVERYONE, READ), ("catalog_documents", None, EVERYONE, READ),
    ("experience", None, EVERYONE, READ),
    ("sync_documents", None, (MAIN, WORK), PROJECT), ("export_documents", None, (MAIN, WORK), PROJECT),
    # Lessons; the allowed actions depend on the caller's role (see CHOICE_LIMITS).
    ("lessons", None, EVERYONE, RECORDS),
    # Run records.
    ("exec", "status", EVERYONE, READ), ("exec", "result", EVERYONE, READ), ("exec", "list", EVERYONE, READ),
    ("operation_records", "query", EVERYONE, READ), ("operation_records", "search", EVERYONE, READ),
    ("operation_records", "supervise", (MAIN,), READ),
    # Evidence, test harness and diagrams.
    ("evidence", "capture", PERFORMERS, PROJECT), ("evidence", "checks", PERFORMERS, PROJECT),
    ("evidence", "hold", PERFORMERS, PROJECT),
    *[("testing", name, (WORK, VERIFY), READ if name in ("catalog", "doctor", "environments", "status", "inspect") else PROJECT)
      for name in ("catalog", "doctor", "setup", "environments", "configure", "start", "status", "observe", "act",
                   "inspect", "check", "reset", "review", "finish")],
    ("archify", "validate", EVERYONE, READ), ("archify", "render", PERFORMERS, PROJECT),
    ("archify", "preview", PERFORMERS, PROJECT),
    # Conductor: request understanding, dispatch, revision, records and commits.
    ("exec", "intent", (MAIN,), RECORDS), ("exec", "announce-tasks", (MAIN,), RECORDS), ("exec", "cancel", (MAIN,), PROJECT),
    *[("loop", name, (MAIN,), READ if name in ("status", "team-roster", "team-history") else PROJECT)
      for name in ("start", "status", "heal", "reconcile", "revise", "review", "skip", "answer", "steer", "retry-preparation",
                   "handoff", "close", "stop-task", "refresh-progress", "extend-revisions", "recover-receipt",
                   "team-roster", "team-history")],
    ("coordination", None, (MAIN,), RECORDS), ("commit", None, (MAIN,), PROJECT),
    ("domains", "list", (MAIN,), READ), ("domains", "create", (MAIN,), RECORDS), ("domains", "link", (MAIN,), RECORDS),
    ("domains", "conductors", (MAIN,), READ), ("domains", "label-conductor", (MAIN,), RECORDS),
]

# Choices a role may pass, where a tool's own command serves several authorities. Main never records
# lessons; publication, sync and retirement stay with the Human.
READ_LESSONS = ["retrieve", "audit", "check", "brief", "pending"]
CHOICE_LIMITS = {"lessons": {"action": {MAIN: READ_LESSONS, EXPLORE: READ_LESSONS,
                                         WORK: READ_LESSONS + ["record", "resolve", "note", "evaluate"],
                                         VERIFY: READ_LESSONS + ["record", "resolve", "note", "evaluate"]}}}

# Runs in a child interpreter: the script's parser as plain data, without running the script.
PROBE = r"""
import argparse, json, runpy, sys
def option(action):
    kind = type(action).__name__
    flags = [o for o in action.option_strings if not o.startswith("--no-")]
    return {"flags": flags or [action.dest], "dest": action.dest, "help": action.help, "required": action.required,
            "positional": not action.option_strings, "choices": [str(c) for c in action.choices] if action.choices else None,
            "kind": kind, "nargs": action.nargs if isinstance(action.nargs, (int, str)) else None,
            "negatable": any(o.startswith("--no-") for o in action.option_strings),
            "metavar": action.metavar if isinstance(action.metavar, str) else None}
def describe(parser):
    tree = {"description": parser.description, "options": [], "groups": [], "commands": []}
    tree["groups"] = [{"flags": [a.option_strings[0] for a in g._group_actions if a.option_strings], "required": g.required}
                      for g in parser._mutually_exclusive_groups]
    for action in parser._actions:
        if isinstance(action, argparse._HelpAction) or action.help == argparse.SUPPRESS:
            continue
        if isinstance(action, argparse._SubParsersAction):
            helps = {c.dest: c.help for c in action._choices_actions}
            for name, sub in action.choices.items():
                if not name.startswith("_"):
                    tree["commands"].append({"name": name, "help": helps.get(name) or sub.description, **describe(sub)})
            continue
        tree["options"].append(option(action))
    return tree
def capture(self, *args, **kwargs):
    print(json.dumps(describe(self)))
    raise SystemExit(0)
argparse.ArgumentParser.parse_known_args = capture
sys.argv = [sys.argv[1]]
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[0])))
runpy.run_path(sys.argv[0], run_name="__main__")
"""


def describe(script: Path, environment: dict | None = None) -> dict:
    result = subprocess.run([sys.executable, "-c", PROBE, str(script)], capture_output=True, text=True,
                            env=environment, timeout=60, check=False)
    lines = result.stdout.strip().splitlines()
    if not lines:
        raise RuntimeError(f"{script.name}: no argparse definition ({result.stderr.strip()[-300:]})")
    return json.loads(lines[-1])


def tool_name(script: str, command: str | None) -> str:
    return (script if command is None else f"{script}_{command}").replace("-", "_")


def _property(option: dict) -> tuple[str, dict]:
    key = option["dest"]
    text = " ".join((option.get("help") or "").split())
    if option["kind"] in ("_StoreTrueAction", "_StoreFalseAction") or option.get("negatable") or option["kind"] == "BooleanOptionalAction":
        schema = {"type": "boolean"}
    elif option["kind"] == "_CountAction":
        schema = {"type": "integer", "minimum": 0}
    elif option["kind"] == "_AppendAction" or option.get("nargs") in ("*", "+") or isinstance(option.get("nargs"), int):
        schema = {"type": "array", "items": {"type": "string", **({"enum": option["choices"]} if option.get("choices") else {})}}
    else:
        schema = {"type": "string", **({"enum": option["choices"]} if option.get("choices") else {})}
    if text:
        schema["description"] = text
    return key, schema


def tool(script: str, command: str | None, roles, effect: str, tree: dict) -> dict:
    """One tool: its argument schema and how to rebuild the exact command line from arguments."""
    # Options the runtime binds, and Human-only actor choices, are never tool arguments.
    bound = [o["flags"][0] for o in tree["options"] if o["flags"][0] in BOUND_OPTIONS]
    options = [o for o in tree["options"] if o["flags"][0] not in BOUND_OPTIONS and o.get("choices") != ["human"]]
    properties, required, arguments = {}, [], []
    for option in options:
        key, schema = _property(option)
        properties[key] = schema
        if option["required"] or (option["positional"] and option.get("nargs") not in ("?", "*")):
            required.append(key)
        arguments.append({"key": key, "flag": None if option["positional"] else option["flags"][0],
                          "kind": schema["type"], "negatable": bool(option.get("negatable")),
                          "storeFalse": option["kind"] == "_StoreFalseAction", "repeat": option["kind"] == "_AppendAction"})
    dest = {o["flags"][0]: o["dest"] for o in options}
    groups = [{"keys": [dest[flag] for flag in group["flags"] if flag in dest], "required": group["required"]}
              for group in tree.get("groups") or []]
    groups = [group for group in groups if group["keys"]]
    description = " ".join((tree.get("help") or tree.get("description") or "").split())
    for group in groups:
        description += (" Give exactly one of: " if group["required"] else " Give at most one of: ") + ", ".join(group["keys"]) + "."
    if tuple(roles) == (MAIN,):
        description += " Conductor (Main) only."
    schema = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = sorted(set(required))
    limits = CHOICE_LIMITS.get(tool_name(script, command))
    return {"name": tool_name(script, command), "script": f"{script}.py", "command": command, "roles": list(roles),
            **({"choiceLimits": limits} if limits else {}),
            "effect": effect, "bound": bound, "groups": groups, "description": description.strip() or tool_name(script, command),
            "inputSchema": schema, "arguments": arguments}


def build(environment: dict | None = None) -> dict:
    trees, tools = {}, []
    for script, command, roles, effect in COMMANDS:
        if script not in trees:
            trees[script] = describe(ROOT / "scripts" / f"{script}.py", environment)
        tree = trees[script]
        if command is not None:
            matches = [item for item in tree["commands"] if item["name"] == command]
            if not matches:
                raise RuntimeError(f"{script}.py has no subcommand {command}")
            tree = matches[0]
        else:
            tree = {**tree, "help": tree.get("description")}
        tools.append(tool(script, command, roles, effect, tree))
    return {"schemaVersion": VERSION, "generatedBy": "distribution/tool_usage.py", "tools": tools}


def render(environment: dict | None = None) -> str:
    return json.dumps(build(environment), ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def load() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))
