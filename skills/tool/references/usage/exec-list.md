# `exec.py list` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

## `list`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--field FIELD`: Select a JSON Pointer before paging; strings are returned verbatim
- `--offset OFFSET`: Zero-based Unicode character offset (enables paging)
- `--length LENGTH`: Characters per page, default 4000; no total document limit
- `--revision REVISION`: Require the SHA-256 returned by the first page; changed data fails closed
