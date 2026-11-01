#!/usr/bin/env python3
"""Project memory shared by every Agent Factory session, whatever its provider.

Record one durable fact per entry that others cannot derive from the code or Documents:
a user preference (user), a correction or confirmed approach (feedback), a decision or
constraint (project), or where to find something outside the project (reference). Inside an
agent run the entry goes to the run's outbox and becomes a candidate until the Human
approves it. Memory is evidence from earlier sessions, never authority.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from execution.cli import JsonArgumentParser, add_project_argument  # noqa: E402
from storage import paths as runtime_paths  # noqa: E402
from storage import shared_memory as memory  # noqa: E402
from storage import team_messages  # noqa: E402
from storage.errors import ContractError  # noqa: E402
from storage.files import emit, error_document  # noqa: E402


def build_parser():
    parser = JsonArgumentParser(prog="memory.py", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="List entries, newest first; candidates are not yet confirmed by the user")
    add_project_argument(listing)
    listing.add_argument("--all", action="store_true", help="Include superseded and retired entries")
    search = commands.add_parser("search", help="Find entries containing every query word")
    add_project_argument(search)
    search.add_argument("--query", required=True)
    search.add_argument("--all", action="store_true", help="Include superseded and retired entries")
    show = commands.add_parser("show", help="Read one entry in full")
    add_project_argument(show)
    show.add_argument("--id", required=True)
    write = commands.add_parser("write", help="Record one durable fact with its source")
    add_project_argument(write)
    write.add_argument("--type", required=True, choices=memory.TYPES)
    write.add_argument("--title", required=True, help="One line shown in every session's memory index")
    text = write.add_mutually_exclusive_group(required=True)
    text.add_argument("--text")
    text.add_argument("--text-file", type=Path, help="UTF-8 file holding the entry text")
    write.add_argument("--source", required=True, help="Where the fact comes from: run id, message id, file or URL")
    write.add_argument("--supersedes", help="Entry this one corrects; it is retired when this entry becomes active")
    write.add_argument("--actor", choices=("human",), help="Required outside an agent run; Human entries are active at once")
    approve = commands.add_parser("approve", help="Human only: confirm a candidate entry")
    add_project_argument(approve)
    approve.add_argument("--id", required=True)
    approve.add_argument("--actor", choices=("human",), required=True)
    retire = commands.add_parser("retire", help="Human only: retire an entry that no longer holds; it stays recorded")
    add_project_argument(retire)
    retire.add_argument("--id", required=True)
    retire.add_argument("--reason", required=True)
    retire.add_argument("--actor", choices=("human",), required=True)
    return parser


def entry_text(args):
    if args.text_file is None:
        return args.text
    try:
        return args.text_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ContractError("memory_text_unreadable", f"Text file could not be read as UTF-8: {args.text_file}") from error


def main(argv=None):
    try:
        args = build_parser().parse_args(sys.argv[1:] if argv is None else list(argv))
        binding = runtime_paths.resolve(args.project_root, home=args.runtime_home, project_id=args.project_id)
        if not binding["registered"]:
            raise ContractError("project_uninitialized", "project has no registered runtime")
        runtime_root = Path(binding["runtimeRoot"])
        identity = team_messages.caller(Path(binding["agentsRoot"]))
        if args.command == "list":
            values = memory.read_all(runtime_root)
            values = sorted(values, key=lambda value: str(value.get("modified", "")), reverse=True) if args.all else memory.visible(values)
            result = {"entries": [{key: value.get(key) for key in ("id", "type", "title", "status", "modified")} for value in values]}
        elif args.command == "search":
            result = {"entries": [memory.public(value) for value in memory.search(runtime_root, args.query, args.all)]}
        elif args.command == "show":
            result = {"entry": memory.public(memory.find(runtime_root, args.id))}
        elif args.command == "write":
            if identity is not None:
                if args.actor == "human":
                    raise ContractError("team_actor_invalid", "An agent run cannot write as the Human")
                writer = team_messages.sender_identity(identity)
            elif args.actor == "human":
                writer = {"actor": "human"}
            else:
                raise ContractError("team_actor_required", "Outside an agent run, write only as the Human with --actor human")
            value = memory.entry(writer, args.type, args.title, entry_text(args), args.source, args.supersedes)
            if value["supersedes"]:
                memory.find(runtime_root, value["supersedes"])
            if identity is not None:
                team_messages.write_outbox(Path(identity["runDirectory"]), {**value, "outbox": "memory"})
                result = {"id": value["id"], "status": "outbox",
                          "delivery": "The runtime records it within seconds as a candidate until the user approves it."}
            else:
                result = {"entry": memory.public(memory.store(runtime_root, value))}
        else:
            if identity is not None:
                raise ContractError("team_actor_invalid", f"Only the Human can {args.command} memory entries")
            changed = memory.approve(runtime_root, args.id) if args.command == "approve" else memory.retire(runtime_root, args.id, args.reason)
            result = {"entry": memory.public(changed)}
        emit({"schemaVersion": 1, "kind": "shared-memory-result", "command": args.command, **result}, sys.stdout)
        return 0
    except (ContractError, OSError, ValueError) as error:
        emit(error_document(getattr(error, "code", "memory_failed"), str(error)), sys.stdout)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
