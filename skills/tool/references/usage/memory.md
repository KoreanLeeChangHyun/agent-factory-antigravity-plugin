# `memory.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Every subcommand with options also accepts: `--project-root PROJECT_ROOT`, `--runtime-home RUNTIME_HOME`, `--project-id PROJECT_ID`.

## `list`: List entries, newest first; candidates are not yet confirmed by the user
- `--all`: Include superseded and retired entries

## `search`: Find entries containing every query word
Required: `--query QUERY`
- `--all`: Include superseded and retired entries

## `show`: Read one entry in full
Required: `--id ID`

## `write`: Record one durable fact with its source
Required: `--type {user,feedback,project,reference}`, `--title TITLE`, `--source SOURCE`
One of: `--text` | `--text-file`
- `--text TEXT`
- `--text-file TEXT_FILE`: UTF-8 file holding the entry text
- `--supersedes SUPERSEDES`: Entry this one corrects; it is retired when this entry becomes active
- `--actor {human}`: Required outside an agent run; Human entries are active at once

## `approve`: Human only: confirm a candidate entry
Required: `--id ID`, `--actor {human}`

## `retire`: Human only: retire an entry that no longer holds; it stays recorded
Required: `--id ID`, `--reason REASON`, `--actor {human}`
