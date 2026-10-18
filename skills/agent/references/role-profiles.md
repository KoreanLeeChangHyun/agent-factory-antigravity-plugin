# Role profiles and model settings

- Inherited scope and entry: [parent guide](execution-modes.md#role-specific-model-overrides).

<a id="role-specific-model-overrides"></a>

## 6. Role-specific model overrides

### 6.1. Role overrides and profiles

- `loop.py start` accepts `--work-model`, `--work-reasoning-effort`, `--work-fast`/`--no-work-fast`,
  `--verification-model`, `--verification-reasoning-effort`, and `--verification-fast`/`--no-verification-fast`. These overrides
  are captured with the loop and passed to both initial and revision turns for
  that role. Plan uses the same Work profile. The existing `--model` remains a
  shared fallback for initial submissions when no role model is supplied.
- An orchestrator brief also passes `--work-profile` naming the profile Main chose, together
  with that profile's exact model ID and effort; the one retry after a failed `workLight` or
  `scribe` attempt passes `--work-profile work`. The profile is stored with the loop and each
  of its Work runs, including revision and receipt-recovery turns, so hosts display the
  choice instead of inferring it from model settings. It selects no model.

  Explorer and Scribe narrow tools below the authorized permissions and never widen them:
  Claude through an allowed-tool list, Codex and Antigravity through the runtime's tool guard.
  Each may run only its Agent Factory Document scripts, never `exec.py` or `loop.py`, and
  neither may start sub-agents, so only Main dispatches agents.

### 6.2. Scribe and Document boundaries

- Scribe's web access grants no code/configuration writes, external writes or publishing,
  sensitive-data transmission, dispatch or commits. Skills whose sources are outside
  `docs/` remain outside its write scope; report the needed change for a code Work owner.
  Report completed research separately from pending drafting and integration.
  A research result alone does not complete a follow-up role's work.
- Use the [direct role exceptions](role-exceptions.md) for exact Explorer assignments,
  shared Document ownership, own records, captured authority and ordinary local commits.
- `loop.py start` rejects a scribe code Work Unit (`scribe_draft_review_required`), because
  Work Units merge automatically; with Work isolation on, Scribe uses the read-only plan in
  the shared checkout. A completed scribe loop is complete: Main reports its result and
  changed paths without a separate accept, revise or discard step, and handles later changes
  as ordinary follow-up requests. Intentional drafts and unresolved choices stay as the
  Document states them. Commits still need actual commit authority. A legacy pending
  `draftReview` stays readable; `loop.py review` can still record a Human decision on it.
  Rule candidates prepared from Lessons Learned still need Human approval to publish.

### 6.3. Standalone settings and authority

- For standalone `exec.py submit/send`, use `--model`, `--reasoning-effort`, and `--fast`/`--no-fast`.
- Fast selects Codex's service tier independently of reasoning effort. Preserve both values exactly. Role Fast is omitted for non-Codex providers.
- Model settings do not change execution authority or add an agent to the route.

### 6.4. Profile tools

| Profile | Role | Tools |
|---|---|---|
| `work` | Expert (heavy) | Authorized permissions |
| `workLight` | Worker (light) | Authorized permissions |
| `explore` | Explorer | Source reads, web lookups, exact assigned evidence Documents and own records |
| `scribe` | Scribe | Public web search/read for Document research and source checks; writing, integration and shortening only inside `docs/` |
