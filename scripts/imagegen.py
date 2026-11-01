#!/usr/bin/env python3
"""Generate images using the installed Codex native image_gen tool and existing ChatGPT login.

No API key or external command backend is used. Consumes the existing Codex plan's usage.
A failed generation is not automatically retried. Returns actual native image bytes.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from execution.cli import JsonArgumentParser
from execution.image_generation import generate
from storage.errors import ContractError
from storage.files import emit, error_document


def build_parser():
    parser = JsonArgumentParser(prog="imagegen.py", description=__doc__)
    parser.add_argument("--prompt", required=True, help="Description of the image to generate; not a command or backend configuration")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        emit(generate(args.prompt))
        return 0
    except ContractError as error:
        emit(error_document(error.code, error.message))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
