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
  with that profile's exact model ID and effort; the one retry after a failed `workLight`,
  `scribe` or `explore` attempt passes `--work-profile work`. The profile is stored with the loop and each
  of its Work runs, including revision and receipt-recovery turns, so hosts display the
  choice instead of inferring it from model settings. It selects no model and no permission:
  every profile, Explorer and Scribe included, runs with the run's authorized permissions
  (Human decision 2026-10-20, message `2159d770`, removed their write limits).
- The Human-facing host captures each role's model settings with the Main run (`exec.py --agent-models`,
  capability `roleModelCandidates`). A role holds one fixed model, or several candidates, each with its own
  model, reasoning effort and Fast. When a role's candidates have `selection: conductor`, choose one candidate
  per task by fit (scope, difficulty, needed tools) and pass its exact model with `--work-model` (or
  `--verification-model`) and the reason with `--work-model-reason` (or `--verification-model-reason`); the
  runtime rejects a candidate choice without a reason and fills the candidate's own effort and Fast. A fixed
  role keeps its model. A model you pass explicitly always wins, so a model the Human names in the request is
  kept even when it is not a candidate. Without a choice the first candidate applies and is recorded as such.
  The loop stores `execution.modelSelection` (candidates, source, selected settings, reason, warnings) as
  evidence; it grants no authority and leaves permissions, routes and Verification unchanged. Never rank
  candidates by unverified cost or performance claims.
- The `designer` profile (Designer, 도안자) creates or edits raster images with an image-generation tool. It runs
  only on an OpenAI (`gpt-*`) or Google (`gemini-*`) model; `loop.py start` refuses an Anthropic (`claude-*`) model,
  also one Antigravity runs, and a designer start without a model, because it has no fallback role. It defaults
  `--work-image-need` to `image-tool` (Human request 2026-10-21, message `c1c85ffb`).
- Image generation is a tool, not a provider property. Pass `--work-image-need image-tool` when the task must
  create raster images with an image-generation tool, `code-drawing` when it draws with SVG, Canvas or CSS
  code (no image tool needed), and `none` otherwise. A provider name is no evidence that the selected model
  has an image tool: the runtime records its availability as `unconfirmed` unless the captured candidate
  itself was marked confirmed; report that limitation instead of assuming the tool exists.

### 6.2. Scribe and Document boundaries

- Report completed research separately from pending drafting and integration.
  A research result alone does not complete a follow-up role's work.
- Use the [direct role exceptions](role-exceptions.md) for exact Explorer assignments,
  shared Document ownership, own records, captured authority and ordinary local commits.
- A completed scribe loop is complete: Main reports its result and
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
| `explore` | Explorer | Authorized permissions |
| `scribe` | Scribe | Authorized permissions |
| `designer` | Designer | Authorized permissions; OpenAI or Google models only |
