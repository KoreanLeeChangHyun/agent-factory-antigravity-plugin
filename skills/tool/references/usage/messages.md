# `messages.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Every subcommand with options also accepts: `--project-root PROJECT_ROOT`, `--runtime-home RUNTIME_HOME`, `--project-id PROJECT_ID`.

## `peers`: List your room's members with status; a conductor also sees the other conductors
- `--agent AGENT`: Whose team to list; defaults to the calling agent run

## `send`: Send a message to another agent of this project
Required: `--to TO`
One of: `--message` | `--message-file`
- `--message MESSAGE`: Message text
- `--message-file MESSAGE_FILE`: UTF-8 file holding the message text
- `--reply-to REPLY_TO`: Message id this answers
- `--actor {human}`: Required outside an agent run; an agent run never sends as the Human

## `post`: Post to your room (or a conductor to the project room): every member receives it, and members named with @agent-id receive the full text
One of: `--message` | `--message-file`
- `--message MESSAGE`: Post text
- `--message-file MESSAGE_FILE`: UTF-8 file holding the post text
- `--room ROOM`: project for the project room (conductors); otherwise a run posts to its own room
- `--actor {human}`: Required outside an agent run

## `rooms`: Human only: list the project's rooms with entry counts

## `room`: Read a room: posts, claims, change notices and the direct messages kept there
- `--room ROOM`: project for the project room (conductors); otherwise a run reads its own room
- `--limit LIMIT`: Newest entries to show; 0 shows all

## `claim`: Conductor: claim files or directories your domain is about to change; an overlap with another domain's claim is reported to both at once
Required: `--paths PATHS`, `--intent INTENT`

## `release`: Conductor: release your domain's claims when that work is done
One of: `--claim` | `--all`
- `--claim CLAIM`: Claim id to release (repeat for several)
- `--all`: Release every claim of your domain
- `--actor {human}`: Required outside an agent run

## `change`: Conductor: announce a finished change other domains may depend on (an interface, message format or shared file)
Required: `--paths PATHS`
One of: `--message` | `--message-file`
- `--message MESSAGE`: What changed and what others must adapt
- `--message-file MESSAGE_FILE`: UTF-8 file holding the notice

## `status`: Conductor: the project status board, per domain its conductor, working performers and claims

## `inbox`: Read messages addressed to the calling agent; shown messages count as delivered
- `--agent AGENT`: Outside an agent run: whose inbox to view (read-only)
- `--all`: Include messages already delivered
- `--peek`: Show without marking them delivered
