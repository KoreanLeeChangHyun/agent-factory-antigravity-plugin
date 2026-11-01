#!/usr/bin/env python3
"""Project work-area domains, worker memberships and conductor session labels shared by the Human (control center)
and Main.

Every worker belongs to a real named domain; there is no unclassified state or placeholder domain. Every project has
one common domain for cross-cutting work; it cannot be deleted or merged away.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from execution.cli import JsonArgumentParser, add_project_argument  # noqa: E402
from storage import paths as runtime_paths  # noqa: E402
from storage.errors import ContractError  # noqa: E402
from storage.files import emit, error_document  # noqa: E402
from conductor import domains  # noqa: E402


def build_parser():
    parser = JsonArgumentParser(prog="domains.py", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def command(name, help_text, writes=True):
        sub = commands.add_parser(name, help=help_text)
        add_project_argument(sub)
        if writes:
            sub.add_argument("--actor", choices=domains.ACTORS, required=True,
                             help="human for control-center edits; ai for Main. Main may not change Human edits")
            sub.add_argument("--source", required=True, help="Evidence for the change, such as the Main run ID")
            sub.add_argument("--expected-revision", type=int, help="Fail with domain_conflict if the list changed since this revision")
        return sub
    command("list", "Read the project's domains, worker memberships, unresolved workers and recent change history", writes=False)
    create = command("create", "Create a domain with a real work-area name; for ai an existing matching name is reused")
    create.add_argument("--name", required=True)
    rename = command("rename", "Rename a domain; former names stay linked to recorded tasks")
    rename.add_argument("--domain-id", required=True)
    rename.add_argument("--name", required=True)
    accept = command("accept", "Human only: accept a domain Main proposed")
    accept.add_argument("--domain-id", required=True)
    archive = command("archive", "Human only: archive a domain; its workers and records stay, new placements are refused")
    archive.add_argument("--domain-id", required=True)
    archive.add_argument("--restore", action="store_true", help="Restore an archived domain")
    merge = command("merge", "Human only: move a domain's workers into another and keep its names as former names")
    merge.add_argument("--domain-id", required=True)
    merge.add_argument("--target-id", required=True)
    delete = command("delete", "Human only: delete a domain that holds no worker")
    delete.add_argument("--domain-id", required=True)
    assign = command("assign", "Place a worker in a real domain; ai cannot move a worker the Human placed")
    assign.add_argument("--agent", required=True)
    assign.add_argument("--domain-id", required=True)
    remove = command("remove-worker", "Human only: hide a stopped worker from the worker list; its records and domain are preserved")
    remove.add_argument("--agent", required=True)
    link = command("link", "Main: reuse or create the named domain and place the worker unless the Human placed it")
    link.add_argument("--agent", required=True)
    link.add_argument("--name", required=True)
    sessions = command("conductors", "Read one chat's conductor (Main) sessions and the domain label of each", writes=False)
    sessions.add_argument("--agent", required=True, help="Any Main session of the chat, such as your own agent ID")
    label = command("label-conductor", "Label a conductor (Main) session with a domain; ai cannot change a label the Human set")
    label.add_argument("--agent", required=True, help="The Main session to label, from conductors")
    target = label.add_mutually_exclusive_group(required=True)
    target.add_argument("--domain-id", help="A listed domain")
    target.add_argument("--name", help="A domain name: an existing domain is reused, otherwise it is created")
    target.add_argument("--clear", action="store_true", help="Remove the session's label")
    recover = command("recover", "Place workers without any entry in the one domain their own runs recorded; list the rest as unresolved")
    recover.add_argument("--dry-run", action="store_true", help="Report what would be recovered without writing")
    return parser


# Former ways to leave a worker without a domain; refused explicitly rather than as unknown options.
NO_DOMAIN_OPTIONS = ("--placeholder", "--unclassified")


def main(argv=None):
    try:
        argv = sys.argv[1:] if argv is None else list(argv)
        if any(argument in NO_DOMAIN_OPTIONS for argument in argv):
            raise ContractError("domain_membership_required", "--placeholder and --unclassified were removed: "
                                + domains.MEMBERSHIP_REQUIRED)
        args = build_parser().parse_args(argv)
        binding = runtime_paths.resolve(args.project_root, home=args.runtime_home, project_id=args.project_id)
        if not binding["registered"]:
            raise ContractError("project_uninitialized", "project has no registered runtime")
        root = Path(binding["runtimeRoot"])
        if args.command == "list":
            document = domains.read(root)
            result = {"domains": document, "unresolved": domains.unresolved(root, document)}
        elif args.command == "create":
            result = domains.create(root, args.name, args.actor, args.source, args.expected_revision)
        elif args.command == "rename":
            result = domains.rename(root, args.domain_id, args.name, args.actor, args.source, args.expected_revision)
        elif args.command == "accept":
            result = domains.accept(root, args.domain_id, args.actor, args.source, args.expected_revision)
        elif args.command == "archive":
            result = domains.archive(root, args.domain_id, args.actor, args.source, args.expected_revision, args.restore)
        elif args.command == "merge":
            result = domains.merge(root, args.domain_id, args.target_id, args.actor, args.source, args.expected_revision)
        elif args.command == "delete":
            result = domains.delete(root, args.domain_id, args.actor, args.source, args.expected_revision)
        elif args.command == "assign":
            result = domains.assign(root, args.agent, args.domain_id, args.actor, args.source, args.expected_revision)
        elif args.command == "remove-worker":
            result = domains.remove_worker(root, args.agent, args.actor, args.source, args.expected_revision)
        elif args.command == "conductors":
            result = domains.conductors(root, args.agent)
        elif args.command == "label-conductor":
            result = domains.label_conductor(root, args.agent, args.actor, args.source, args.domain_id, args.name,
                                             args.clear, args.expected_revision)
        elif args.command == "recover":
            result = domains.recover(root, args.actor, args.source, args.expected_revision, args.dry_run)
        else:
            if args.actor != "ai":
                raise ContractError("domain_actor_invalid", "link is Main's dispatch path; the Human uses assign")
            result = domains.link_dispatch(root, args.agent, args.name, args.source)
            result["domains"] = domains.read(root)
        emit({"schemaVersion": 1, "kind": "project-domains-result", "command": args.command, **result}, sys.stdout)
        return 0
    except (ContractError, OSError, ValueError) as error:
        emit(error_document(getattr(error, "code", "domains_failed"), str(error)), sys.stdout)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
