# `exec.py docs-git` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

## `docs-git`: Report or prepare Git handling of the managed docs/ tree
Required: `docs_git_action {status,apply,unignore}`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--mode {project,separate,local}`: apply: docs in the project repository, its own repository, or local only
