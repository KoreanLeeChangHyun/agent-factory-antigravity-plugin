#!/usr/bin/env python3
"""Local stdio tool server that offers the plugin's standard actions as native tools to the calling run.

Providers start it for each Agent Factory run; it is not an agent-facing command.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from execution.cli import JsonArgumentParser  # noqa: E402


def build_parser():
    parser = JsonArgumentParser(prog="tool_server.py", description=__doc__)
    parser.add_argument("--host", choices=("claude", "codex", "antigravity"), required=True,
                        help="Provider that started the server; it decides how the calling run is identified")
    return parser


def main(argv=None):
    args = build_parser().parse_args(sys.argv[1:] if argv is None else list(argv))
    from execution.tool_server import Server
    Server(args.host).serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
