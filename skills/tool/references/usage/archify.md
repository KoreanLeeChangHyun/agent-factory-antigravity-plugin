# `archify.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

## `install`: Download and verify the pinned official renderer; no npm/global install.
Required: `--tool-dir TOOL_DIR`

## `preview`: Validate JSON from stdin and return an isolated SVG preview; writes no project files.
- `--tool-dir TOOL_DIR`: Pinned renderer prepared by install; required for architecture/sequence, unused for built-in ERD.
- `--viewer`: Also return the official interactive viewer HTML for a host-isolated webview.

## `validate`: Validate JSON with the official schema.
Required: `--project-root PROJECT_ROOT`, `input INPUT`
- `--tool-dir TOOL_DIR`: Pinned renderer prepared by install; required for architecture/sequence, unused for built-in ERD.

## `render`: Validate then deliver HTML without replacing files.
Required: `--project-root PROJECT_ROOT`, `input INPUT`, `--output OUTPUT`
- `--tool-dir TOOL_DIR`: Pinned renderer prepared by install; required for architecture/sequence, unused for built-in ERD.
- `--open`: Open generated HTML in the local OS browser.

## `open`: Open an existing artifact HTML in the local OS browser.
Required: `--project-root PROJECT_ROOT`, `output OUTPUT`
