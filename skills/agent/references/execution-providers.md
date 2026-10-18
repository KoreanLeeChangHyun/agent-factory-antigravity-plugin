# Execution providers

## 7. Execution providers

- Historical sessions remain Codex sessions. `--model claude-opus`, `claude-sonnet`,
  or `claude-haiku` selects Claude Code's corresponding alias. Full `claude-*`
  model IDs such as `claude-opus-5-5`, `claude-sonnet-5`, `claude-fable-5-1` and
  `claude-haiku-4-5-20251001` pass through unchanged; account access is checked by Claude at execution.
- `exec.py submit` accepts `--provider codex|claude|antigravity`, `--claude <executable>` and
  `--agy <executable>`.
  `send` preserves the captured executable and provider unless an unstarted or
  explicitly cleared conversation selects another provider. Never pass a Codex
  session ID to Claude, or vice versa. Existing run history is retained.
- `capabilities --model <model>` reports the selected provider before submission.
  Do not infer Claude capabilities from Codex's app-server schema.
- Claude supports every task mode. Fast is accepted as a no-op; Goal uses Claude's `/goal`
  (see [Native Fast and Goal](native-fast-goal.md#claude-goal)). Plan runs in Claude's `plan`
  permission mode; plan-work routes then resume the same session to execute the approved plan.
- Execution policies map to the nearest Claude permission mode, always with
  `--permission-prompts none`.

  Claude tool permissions are not an OS sandbox: network access is not confined. Without an
  explicit policy (CLI default), `permissions.defaultMode` from the user, project and local
  Claude settings selects the policy; an unset or other mode maps to `read-only`.
- Claude effort values are `low`, `medium`, `high`, `xhigh`, and `max`. `minimal` maps to
  `low`, `ultra` to `max`, and `none` leaves Claude's default effort.
- Claude child runs load the user's Claude settings, hooks, tool servers and CLAUDE.md.
  Each run records `contextUsage` (latest prompt size and context window) in its state.

| Policy | Claude permission mode |
|---|---|
| `danger-full-access` | `bypassPermissions` |
| `workspace-write` | `acceptEdits`, extra writable roots as `--add-dir` |
| `read-only` | `dontAsk` |

<a id="antigravity"></a>

### 7.1. Antigravity

- The Antigravity CLI (`agy`) runs Google AI subscription models in print mode. `gemini-*`
  models select it. Name its other models `antigravity/<id>` (for example
  `antigravity/claude-sonnet-4-6`) or pass `--provider antigravity` with the plain `<id>`;
  a plain `claude-*` model always selects Claude Code.
- Runs use an `agent-factory-<id>` custom agent, which each installed plugin copy writes to
  `~/.gemini/config/agents/agent-factory-<id>/agent.md` and prunes when its copy is removed. It replaces agy's default system prompt and
  keeps only file, shell, web, image generation and `finish` tools and the Agent Factory Skills; project rules (`AGENTS.md`, `GEMINI.md`) still
  apply, and the user's agy tool servers are not loaded.
- Every task mode and Goal are supported; Fast is a no-op and images are rejected (text only).
  Plan runs by instruction without skipped permissions, because agy's `plan` mode waits for review.
- Policies map to agy permissions, which are not an OS sandbox.

  The default denies commands and reads outside the workspace, run directory and Agent Factory
  Skills, and allows
  workspace edits even under `read-only`. A denied call ends the turn without a result, so
  the run fails. The CLI default policy is `workspace-write`.
- `--effort` applies to agy's default model and base IDs such as `gemini-3.8-flash`; IDs
  ending in a level (`-low`, `-medium`, `-high`) fix their effort, and other families ignore it.
  A level the model does not offer (`gemini-3.1-pro` has `low` and `high`) uses the nearest one.
  `minimal` maps to `low`, `xhigh` and `ultra` to `max`, and `none` leaves the default.

| Policy | agy permissions |
|---|---|
| `danger-full-access` | `--dangerously-skip-permissions` |
| `workspace-write` | default; extra writable roots as `--add-dir` |
| `read-only` | default, with a read-only instruction |
