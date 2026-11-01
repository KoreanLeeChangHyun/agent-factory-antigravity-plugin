#!/usr/bin/env python3
"""Search project run evidence and lesson lifecycles, read originals and pin context selections.

All operations are read-only. Selected history is evidence, never new authority.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from execution.cli import JsonArgumentParser, add_project_argument
from execution.experience import operate
from storage import paths
from storage.errors import ContractError
from storage.files import emit, error_document


def build_parser():
    parser = JsonArgumentParser(prog='experience.py', description=__doc__)
    parser.add_argument('action', choices=['runs', 'lessons', 'read', 'select', 'sync-status'])
    add_project_argument(parser)
    parser.add_argument('--input-json', default='{}', help='Search query/scope/page, or source identity and optional character page')
    return parser


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
        root = args.project_root.resolve(strict=True)
        paths.resolve(root, home=args.runtime_home, project_id=args.project_id)
        result = operate(root, args.action, json.loads(args.input_json))
        emit({'schemaVersion': 1, 'kind': 'project-experience', 'action': args.action, **result})
        return 0
    except (ValueError, OSError, ContractError) as error:
        emit(error_document(getattr(error, 'code', 'experience_failed'), str(error)))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
