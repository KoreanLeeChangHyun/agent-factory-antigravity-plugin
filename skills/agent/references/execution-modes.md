# Execution modes

<a id="captured-routes"></a>

## 1. Captured routes

### 1.1. Role routing and briefs

- Conversation and Human Interview always remain Main.
- The Human chooses between conductor mode (`orchestrate`) and direct mode (`direct`). In
  conductor mode Main keeps conversation, planning, Interview, requirement shaping,
  routing, reporting, commits and known-location lookups ([lookup
  boundary](#lookup-boundary)). It delegates every project change and broader research to
  Work, sizing the Work model light (bounded, already-decided change) or heavy
  (multi-file, design or unknown cause) and retrying a failed light attempt once with the
  heavy profile. It adds Verification only when the Human explicitly requests it. In
  direct mode Main implements directly.
- <a id="lookup-boundary"></a>Lookup boundary: Main looks up only a location it already
  knows (one the Human named, a performer's reported evidence or one already opened in
  this conversation) and handles it directly when that one look answers; when the location
  is unknown or the look needs further searching, it delegates the lookup to `explore` or
  `workLight` on a light model with evidence (paths, lines, record IDs) to spot-check.
  Classify by this one-look test, never by time, size or file-count limits. A single-fact
  web lookup is one look when one search or one read of a known page answers it; Main
  answers it with its source.
- The work request (brief) is the only handoff from Main to a performer. It carries only
  what the performer needs for the task; Main's allocation reasons (profile, model,
  session), preparation steps and own preparation errors stay in Main's run records or
  allocation evidence, not in the brief.
- <a id="rerun-or-new"></a>Re-run or new execution: when the Human corrects or adds to
  performed work, Main asks whether the original Done still holds. If it does (the result
  fell short, or a fix or missing part within the same Done), it is a re-run of the same
  task: use `loop.py steer` while its run is active or `loop.py revise` after it ended,
  keeping the performer and session. If Done must change (a new goal, another target, or
  new work on top of a finished result), it is a new execution with a new brief whose
  References name the earlier run. Right after dispatch Main tells the Human in one line
  which it is (re-run with its round number, or new execution) and why. The Human talks
  only to Main; an explicit Human choice to start fresh or keep fixing overrides Main's
  judgment.
- An orchestrator brief is the short-term contract of its change, not a long-term work
  contract. It starts with a `Title:` line naming the work in a few words of the Human's
  language (the task title shown to the Human) and carries exactly four English-headed
  sections: Goal, Scope (`### Do` and `### Do not` subheadings), Done (the Human-observable outcome
  and the evidence that shows it, including task-specific deliverables) and References (the Human's source
  message ID/time, related files, records, prior runs and source links) as short list items. It has no Report
  section: the runtime result form already requires the result, changed paths and checks.
  Headings stay English; the extension translates them for display. Its loop state is the
  project's record of it. A read-only brief needs no task-list JSON, announcement or
  long-term contract. Exact Explorer Document assignments use the existing
  task-list/task-ID binding, not prose path inference. Long-term work contracts remain the
  Human-selected multi-task procedure between the Human and Main (Convention's [work
  contracts](../../convention/references/work-contracts.md#scope)).
- Conductor mode is enforced per provider by tool permissions, not model choice. Main may
  read, write inside its own run directory, run `python3 <plugin-root>/scripts/*` of an
  installed Agent Factory copy and read-only Git (`status`, `diff`, `log`, `show`); it
  cannot edit implementation. It may perform an approved ordinary local commit through
  the [receipt-bound commit tool](role-exceptions.md#ordinary-local-commit); raw Git mutation stays denied.
  Lookup routing follows the [lookup boundary](#lookup-boundary).
  The run's sandbox policy is unchanged, so delegated Work keeps its permissions.
  - Claude: `dontAsk` with an `--allowedTools` list and a `PreToolUse` hook on shell/edit tools.
    Explorer native Write/Edit permissions name exact assigned files; the hook also rejects
    symlink traversal. Main retains bounded web confirmation tools.
  - Codex: a session-flag `PreToolUse` hook (`runtime/hooks/orchestrator_guard.py`) on
    `Bash`, `apply_patch` and the sub-agent start tools. The runtime adds an exact-hash
    `hooks.state` trust entry to the user's Codex config on first use and fails the run if
    Codex does not trust the hook.
  - Antigravity: the same guard as a global plugin hook (`~/.gemini/config/plugins/
    agent-factory-<id>-guard/`). It is inert unless the runtime arms it through the
    `AGENT_FACTORY_ORCHESTRATOR_GUARD` environment of an orchestrate Main run.
- Work may start only read-only exploration sub-agents; `capabilities` reports the result
  as `workSubagents`.
  - Claude: a PreToolUse hook allows only `Explore`.
  - Codex: `none`. The model can choose no sub-agent type and sub-agents inherit the parent's
    sandbox, so none is read-only. Work carries Main's hook definition (Codex keeps one trust
    hash for session-flag hooks), armed with Work rules that deny `spawn_agent` and
    `resume_agent`. A hook is a guardrail, not a complete boundary: a shell command that
    launches another agent CLI and the legacy `codex exec` backend are not covered.
  - Antigravity: the managed agent lists no sub-agent tool.

### 1.3. Authority and message capture

- Selecting a mode does not satisfy the independent Human approval gate or expand
  execution permissions.
- Composer actions send the current draft through Main immediately and are never persisted.
  Ordinary Enter/send always captures direct, even after restoring old saved modes.
  Queued messages retain their action; different actions must never merge.
- Main preserves an active task's route when handling conversational steering.

### 1.4. Mode and completion matrix

| Mode | Implementation | Completion |
| --- | --- | --- |
| `orchestrate` (conductor mode, new Main input default) | Main routes; managed Work for changes and research | Completed Work Goal and receipt with own checks; separate Verification only on explicit Human request |
| `direct` (direct mode) | Main directly | Appropriate Main checks |
| `work` | Managed Work | Completed Work Goal and receipt with own checks; separate Verification not requested |
| `plan` | Actual Work Plan collaboration mode only | Return plan; no execution or Verification |
| `verification` | Managed standalone Verification | Request-bound standalone receipt and findings; no repairs |
| `plan-work` | Actual Plan then default execution in the same Work thread | Completed Work Goal and receipt with own checks; separate Verification not requested |
| `work-verification` | Managed Work | Separate Verification pass or evidenced Human skip |
| `plan-work-verification` | Actual Plan then default execution in the same Work thread | Separate Verification pass or evidenced Human skip |

<a id="runtime-interface"></a>

## 2. Runtime interface

### 2.1. Captured modes and loop start

- `exec.py submit/send --task-mode MODE` snapshots the route. New Main requests without a flag capture `orchestrate`;
  persisted runs with no mode use `work-verification`. Explicit flags participate in the
  immutable dispatch tuple.
- `loop.py start` without `--task-list-file`/`--task-id` is the orchestrator brief route: the
  runtime derives one task (title from the brief's first line) so the panel shows it; no
  announcement check applies. Announced lists keep their full binding contract.
- Main performs `direct` work itself; do not create a direct-mode loop. `orchestrate` is
  Main-only: Main starts `loop.py start --task-mode work` (or a verification route on
  explicit request) and never submits Work with `--task-mode orchestrate`.
- `loop.py start --task-mode work --work-agent ID --request-file PATH` (also `--task-mode plan-work`) needs no Verification identity. Its completed Work
  receipt ends the loop with terminal reason `work-completed`. Main applies
  [result alignment](orchestration.md#result-alignment) to the bound result/receipt before reporting.

### 2.2. Verification and revision controls

- Work-bound verification modes additionally require `--verification-agent ID`. Failure revises the same Work
  session, then reuses the same Verification session and binds its receipt to the new
  exact Work run. No planning role or extra Agent exists.
- A task gets at most `--max-revisions` Work revisions (default 3; `0` is unlimited). The next
  failed Verification stops the loop as `needs-human-decision` with `revision_limit_reached`
  and the open finding IDs. Only a Human continues it, with
  `loop.py extend-revisions --actor human --authorization-reference REF --decision-evidence TEXT [--additional N]`,
  or ends it with `loop.py close`. Loops persisted before the limit stay unbounded.
  The loop's public state carries the stop as `pause` (`code`, `revisionCount`, `maxRevisions`,
  `pendingFindingIds`, `findings`), `null` otherwise; `capabilities` advertises
  `revisionLimitPause` so a host can offer the Human both decisions.

### 2.3. Defaults and capability compatibility

- The low-level loop CLI's omitted flag retains `work-verification` for existing callers.
  Persisted loops without the field use `work-verification`. New Main uses its captured mode
  explicitly when starting a loop.
- `capabilities` version 0.1.0 exposes `submit/send.taskModes`. Clients require the selected mode in
  that list before dispatch; absence is unsupported, never an invitation to inject prose
  or silently choose another route. Existing fields and receipt schema versions remain
  compatible.

<a id="actual-plan-transition"></a>

## 3. Actual Plan transition

- `plan`, `plan-work` and `plan-work-verification` require advertised Plan support.
- The runtime plans and executes within the same exact Work session, preserving model,
  reasoning, permissions and approval policy.
- The plan is retained as `plan.json`. In `plan` mode the host stops after the actual Plan turn,
  records a read-only Work completion receipt (no project changes or tests), and returns
  the plan. Other Plan routes require implementation before Work completion.
- No transition click is required.
- An unresolved required Human decision returns `needs-human-decision`.
- Failure or interruption cannot start implementation or Verification.
- Missing Plan support fails before a model turn; do not imitate the transition in prose.
- For Plan·Work routes, completed implementation and a valid Work receipt are required.
- `plan-work` completes with Work own checks; `plan-work-verification` requires separate Verification.

<a id="reports-and-authority"></a>

## 4. Reports and authority

- Apply the [work report contract](work-reports.md).
- Use `not requested` for separate Verification in orchestrate/direct/work/plan-work modes, not
  `pass` or Human skip.
- Report Main's own checks for direct and Work-reported own checks for delegated work separately
  from independent Verification. Status and receipt identity checks do not re-verify work.
- Work performs necessary own checks but never claims independent Verification pass or commits.
- Permission, approval, publication and destructive-action authority remain independent
  of mode.
- Mode selection alone sends no messages to external services.


<a id="standalone-verification-and-planning"></a>

## 5. Standalone verification and planning

- Main resolves a standalone verification target from explicit input first, then prior
  completed work in this chat. Missing or ambiguous targets require a Human answer;
  never fabricate a Work ID or evidence.
- Dispatch `exec.py submit --role verification --task-mode verification --agent ID --request-file PATH`.
  The bounded request identifies the exact target and authorized checks. Do not supply
  `--verified-work-run-id` or `--receipt-request-hash`. Sends to this verifier also use
  `--task-mode verification` explicitly.
- `standalone-verification-receipt` binds `runId` and `requestHash` of this target request,
  with `decision` and `findings`; it contains no Work binding and cannot close a Work loop.
  Work-bound receipts and loop fix/recheck transitions keep their existing contracts.
- Plan alone dispatches `exec.py submit --role work --task-mode plan`; it does not create
  a loop or substitute literal `/plan` text for collaboration mode. Plan·Work routes
  continue using loop.py and the same Work session for Plan/default turns.
- Historical runs and omitted legacy loop routes retain their original meaning.

<a id="role-specific-model-overrides"></a>

## 6. Role-specific model overrides

- Read the [full contract](role-profiles.md#role-specific-model-overrides).

### 6.1. Role overrides and profiles

- Read the [full contract](role-profiles.md#61-role-overrides-and-profiles).

### 6.2. Scribe and Document boundaries

- Read the [full contract](role-profiles.md#62-scribe-and-document-boundaries).

### 6.3. Standalone settings and authority

- Read the [full contract](role-profiles.md#63-standalone-settings-and-authority).

### 6.4. Profile tools

- Read the [full contract](role-profiles.md#64-profile-tools).

## 7. Execution providers

- Before selecting a provider or using provider-specific capabilities, policies, effort or tool settings, read [Execution providers](execution-providers.md#7-execution-providers).

<a id="antigravity"></a>

### 7.1. Antigravity

- Read the [Antigravity contract](execution-providers.md#antigravity) for its provider-specific behavior.
