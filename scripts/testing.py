#!/usr/bin/env python3
"""Persistent test environments, real interactions, evidence and human review.

Use catalog for machine-readable tool contracts; start binds a manifest for the
entire session. Only setup installs dependencies; session tools never change expected results.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))

from execution.cli import JsonArgumentParser, add_project_argument  # noqa: E402
from execution import test_harness, test_environment  # noqa: E402
from storage.errors import ContractError  # noqa: E402
from storage.files import emit, error_document  # noqa: E402


def build_parser():
    parser = JsonArgumentParser(prog="testing.py", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    catalog = commands.add_parser("catalog", help="List versioned tools, JSON schemas, drivers and limitations; launches nothing")
    catalog.add_argument("--tool", choices=tuple(test_harness.TOOLS))
    for command in ("doctor", "setup", "environments", "configure"):
        sub = commands.add_parser(command, help={"doctor": "Detect dependencies and verify a real Chromium launch; read-only",
            "setup": "Install missing per-user Node.js, Playwright and Chromium, then verify launch",
            "environments": "List saved project environments and retained sessions",
            "configure": "Validate and save a named environment in project runtime storage"}[command])
        add_project_argument(sub)
        if command == "configure":
            sub.add_argument("--profile", required=True, help="Environment identifier")
            data = sub.add_mutually_exclusive_group(required=True)
            data.add_argument("--input", type=Path)
            data.add_argument("--input-json")
    start = commands.add_parser("start", help="test.start: launch a dedicated environment with a frozen manifest")
    add_project_argument(start)
    source = start.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path, help="JSON manifest; see the catalog and testing-harness reference")
    source.add_argument("--profile", help="Saved environment identifier")
    start.add_argument("--wait-sec", type=float, default=60, help="Startup wait; a timeout preserves the session ID for status/finish")
    for command, help_text in (
        ("status", "Read session state and evidence paths, including after the supervisor stops"),
        ("observe", "test.observe: capture the running screen, elements and correlated logs"),
        ("act", "test.act: click, fill, type, press, navigate, scroll, execute argv or drive a VS Code bridge"),
        ("inspect", "test.inspect: read browser state, files, HTTP responses, SQLite rows or a VS Code snapshot"),
        ("check", "test.check: evaluate a frozen scenario/check against an independently read observation"),
        ("reset", "test.reset: restart owned processes and restore session-owned data; retain all attempts"),
        ("review", "test.review: pause automation and open a local interactive review console; resume explicitly"),
        ("finish", "test.finish: save the report and stop only this session's owned environment"),
    ):
        sub = commands.add_parser(command, help=help_text)
        add_project_argument(sub)
        sub.add_argument("--session", required=True, help="Session ID returned by start")
        if command not in ("status", "finish"):
            data = sub.add_mutually_exclusive_group()
            data.add_argument("--input", type=Path, help="Tool input JSON file")
            data.add_argument("--input-json", help="Tool input JSON object; do not put secrets in shell history")
        if command != "status":
            sub.add_argument("--wait-sec", type=float, default=60, help="Request wait; timeout never retries the action automatically")
    serve = commands.add_parser("_serve", help="Internal owned environment supervisor")
    serve.add_argument("--directory", type=Path, required=True)
    return parser


def main():
    try:
        args = build_parser().parse_args()
        if args.command == "_serve":
            return test_harness.serve(args.directory)
        if args.command == "catalog":
            emit(test_harness.catalog(args.tool))
            return 0
        if args.command in ("doctor", "setup", "environments", "configure"):
            if args.command == "configure":
                data = json.loads(args.input.read_text(encoding="utf-8") if args.input else args.input_json)
                result = test_environment.configure(args, data)
            else:
                result = {"doctor": test_environment.doctor, "setup": test_environment.setup,
                          "environments": test_environment.snapshot}[args.command](args)
            emit(result)
            return 0
        if args.command == "start":
            if args.profile:
                args.file = test_environment.profile_path(args, args.profile)
            result = test_harness.start(args)
        elif args.command == "status":
            result = test_harness.status(args)
        else:
            raw = args.input.read_text(encoding="utf-8") if getattr(args, "input", None) else getattr(args, "input_json", None)
            data = json.loads(raw) if raw else {}
            if not isinstance(data, dict):
                raise ContractError("invalid_input", "tool input must be a JSON object")
            result = test_harness.request(args, data)
        emit(result)
        if result.get("executionStatus") in ("failed", "interrupted"):
            return 1
        return 2 if result.get("verdict") == "failed" or result.get("outcome") == "failed" else 0
    except (ContractError, ValueError, OSError) as error:
        emit(error_document(error.code if isinstance(error, ContractError) else "testing_failed", str(error)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
