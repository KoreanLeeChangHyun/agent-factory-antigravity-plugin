#!/usr/bin/env python3
"""Install pinned Archify, validate diagram JSON originals, and render/open standalone HTML."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from system import archify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    install = commands.add_parser("install", help="Download and verify the pinned official renderer; no npm/global install.")
    install.add_argument("--tool-dir", type=Path, required=True, help="New renderer directory outside the project, with an existing parent.")
    preview = commands.add_parser("preview", help="Validate JSON from stdin and return an isolated SVG preview; writes no project files.")
    preview.add_argument("--tool-dir", type=Path, help="Pinned renderer prepared by install; required for architecture/sequence, unused for built-in ERD.")
    preview.add_argument("--viewer", action="store_true", help="Also return the official interactive viewer HTML for a host-isolated webview.")
    for name in ("validate", "render"):
        command = commands.add_parser(name, help="Validate JSON with the official schema." if name == "validate" else "Validate then deliver HTML without replacing files.")
        command.add_argument("--project-root", type=Path, required=True)
        command.add_argument("--tool-dir", type=Path, help="Pinned renderer prepared by install; required for architecture/sequence, unused for built-in ERD.")
        command.add_argument("input", type=Path, help="JSON in docs/artifact/diagram/; existing Document package assets/ remain readable.")
        if name == "render":
            command.add_argument("--output", type=Path, required=True, help="New docs/artifact/<fixed-domain>/<name>.html file; parent must exist, no nested directories.")
            command.add_argument("--open", action="store_true", help="Open generated HTML in the local OS browser.")
    opener = commands.add_parser("open", help="Open an existing artifact HTML in the local OS browser.")
    opener.add_argument("--project-root", type=Path, required=True)
    opener.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        result = archify.execute(args)
    except (OSError, ValueError, archify.ArchifyError) as error:
        result = {"ok": False, "error": str(error)}
        if getattr(error, "diagnostics", None):
            result["diagnostics"] = error.diagnostics
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
