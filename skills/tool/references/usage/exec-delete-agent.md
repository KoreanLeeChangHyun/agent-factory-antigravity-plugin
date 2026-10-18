# `exec.py delete-agent` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

## `delete-agent`: Permanently delete one inactive Main agent's private runtime records
Required: `--agent AGENT`, `--actor {human}`, `--authorization-reference AUTHORIZATION_REFERENCE`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--with-tasks`: Also delete the ended task histories this Main dispatched
- `--preview`: Check deletability and count dispatched tasks without deleting
