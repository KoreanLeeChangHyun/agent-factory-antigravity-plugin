# Lessons Learned writing

<a id="mandatory-recording"></a>

## 1. Mandatory recording

### 1.1. Observed errors and judgment differences

- Every error that occurs during Agent work MUST be recorded, including tool, command,
  test, implementation and infrastructure errors, even when a retry succeeds or the error
  remains unresolved. Managed execution records observed failures as occurrences of
  their [signature record](#runtime-capture); the Agent's own record MUST cover an
  error whose cause it establishes, that changes its approach or that the runtime does
  not capture.
- A test failure the task expects, such as a test-first red step, needs no Agent record;
  its runtime occurrence suffices. Record it when the failure or its cause was unexpected.
- The Agent MUST also record observed differences between the Human's judgment and
  its own judgment, including corrections or rejected recommendations. A difference
  is not automatically an error by either party; do not infer disagreement from silence.

### 1.2. Role recording boundary

- Main MUST NOT write lessons (`record`, `resolve`, `candidate`, `publish`). It keeps error and
  judgment facts with sources in run records and delegates the lesson to Work or Scribe.
- Other roles MUST NOT write lessons mid-task. Just before handoff, they MUST bundle only
  the needed errors and judgment differences into one record.

### 1.3. Incomplete records and repair

- Record an unknown cause as unknown and a missing solution as unresolved. Separate
  hypotheses and proposed remedies from confirmed causes and verified solutions.
- Update the same record when the cause, remedy or verification becomes known.
  For a recurrence, append the occurrence and its outcome without erasing prior evidence.
- If recording is blocked, report the storage failure and pending record content in
  the task result or handoff. Do not claim it was saved; persist it when access returns.
- Lessons Learned is a mandatory documentation side effect, including for Verification; it
  authorizes no implementation change, broader repair, publication or destructive action.

<a id="package-and-metadata"></a>

## 2. Package and metadata

### 2.1. Body, metadata and source ownership

- Apply the shared [Document requirements](../SKILL.md) for user language, authority and
  source fidelity. Error and judgment difference are distinct categories, not maturity levels.
- Follow the [directory layout](layout.md) for error and judgment-difference package paths.
  Preserve existing record IDs and narrative bodies.
- Runtime `storage/paths.py` resolves machine metadata at
  `<project-runtime>/lessons-learned/<id>.json`; respect `AGENT_FACTORY_HOME`, project identity
  and relocation. Never hardcode a home or put this metadata in the checkout.
- Markdown is the sole editable prose source, including causes, solutions, judgments,
  reflection, rule text and historical evidence. Field blocks use stable HTML anchors
  and Markdown quotes; edit their text while retaining anchors and quote prefixes.

### 2.2. Schema and lifecycle history

- Generated labels support Korean and English; other languages retain supplied prose and
  language-neutral field identifiers. Never translate preserved source text implicitly.
- JSON schema 2 keeps identities, categories, scopes, states, timestamps, execution links,
  document paths and text locators. It contains no second copy of narrative content.
  Front matter and displayed state are CLI-managed projections; change state through the lifecycle.
- Occurrences, resolutions, applications, candidates, evaluations, publications and
  retirements retain their original order, IDs and actual sources. The CLI joins body and
  metadata on demand; unknown causes and unresolved outcomes stay unknown/unresolved.

### 2.3. Discovery and record identity

- Catalog and search discover these records. They never activate them as Skills or export
  them to hosts. `runtime` is a capture scope, not a document category or user folder.
- Operational records under `docs/lessons-learned/` are local data excluded from Git,
  including generated projections and scratch files. Recording creates a self-ignored
  `docs/lessons-learned/.gitignore` unless `docs/.gitignore` already ends with
  `/lessons-learned/`. A separate `docs` repository should track that outer configuration.
  Already tracked records require explicit authorization to remove their exact paths from
  the index with `git rm --cached`, preserving local files. Never force-add records.
  Keep lesson implementation, tests, usage documentation and adopted Skills tracked.
  Ignored records in an isolated Work Unit remain there after integration; cleanup may
  stay pending to preserve them. A commit manifest may include an explicitly authorized,
  already staged index removal with a null content hash, keeping the local body intact.
- Keep one record for the same incident or known recurring cause. Separate error and
  judgment records may link to each other; judgment difference alone is not an error.

<a id="record-content"></a>

## 3. Record content

- For error records, include the following fields.

- Preserve useful error messages and identifiers, but redact credentials, tokens and
  private payloads; do not copy entire sensitive logs into a record.
- A successful retry establishes recovery, not a confirmed root cause. Retain that
  distinction and any remaining uncertainty.

| Required content | Meaning |
|---|---|
| Occurrence | Date, affected task/component and available Agent/run identity. |
| Error | Observed symptom, triggering operation and relevant diagnostic evidence. |
| Cause | Confirmed cause with evidence, or explicitly unknown with any hypotheses labeled. |
| Solution | Actions attempted and their outcomes; distinguish proposed from applied remedies. |
| Verification | Actual check and result, or explicitly not checked. |
| Status and follow-up | Resolved or unresolved, remaining investigation and preventive action when known. |

<a id="judgment-differences"></a>

## 4. Judgment differences

- Preserve the Human's meaning and follow applicable Human decision authority.
  Do not invent motives, infer personality traits or treat agreement as proof of correctness.
- A preference for one task is not automatically a universal rule. Record the known
  scope; do not require the Human to explain every correction before continuing work.

| Required content | Meaning |
|---|---|
| Context | Date, task, decision at issue and available conversation/run reference. |
| Human judgment | The Human's actual choice and stated reasons; mark unstated reasons as unknown. |
| AI judgment | The original recommendation and its assumptions, evidence and priorities. |
| Difference | The precise point of divergence, without rewriting the AI's original position after correction. |
| Reflection | Possible differences in information, interpretation, preferences, priorities or constraints; distinguish evidence from hypotheses. |
| Outcome | The actual decision, correction or unresolved question and any observed result. |
| Future application | What to check or ask next time, its scope and remaining uncertainty. |

<a id="rule-consolidation"></a>

## 5. Consolidating lessons into Skill rules

- When the Human requests consolidation, or has already authorized an ongoing
  consolidation workflow, collect relevant error and judgment records by topic.
  An existing authorization does not require a new approval for each in-scope rule.
- Compare recurring causes, successful remedies, judgment differences and conflicting
  evidence. Extract reusable guidance with explicit triggers, actions, scope and exceptions;
  keep uncertain or contradictory conclusions in Lessons Learned until resolved.
- Apply [Specification writing](specification.md) to integrate supported rules into
  the owning `docs/skills/rule-*/SKILL.md`; create a new rule package only when no owner fits.
  A Human request to turn lessons into Skill rules supplies Specification authority
  within that scope, but does not settle unresolved Human-owned product or risk choices.
- Keep rule documents self-contained descriptions of the current accepted guidance.
  Preserve incident history and reflection in their Lessons Learned records;
  keep provenance in metadata, not incident logs or lesson IDs.
- Follow the shared Document synchronization contract after changing `docs/skills/`.
  Recording a lesson alone does not activate it as a Skill or authorize arbitrary rule changes.

<a id="lifecycle-cli"></a>

## 6. Lifecycle CLI

- Read the complete contract in [Lesson lifecycle CLI](lesson-lifecycle.md#lifecycle-cli).

### 6.1. Invocation, compatibility and roots

- Read the complete contract in [Lesson lifecycle CLI](lesson-lifecycle.md#61-invocation-compatibility-and-roots).

### 6.2. Payloads, identity and semantics

- Read the complete contract in [Lesson lifecycle CLI](lesson-lifecycle.md#62-payloads-identity-and-semantics).

### 6.3. Retrieval and rule application

- Read the complete contract in [Lesson lifecycle CLI](lesson-lifecycle.md#63-retrieval-and-rule-application).

### 6.4. Lifecycle actions

- Read the complete contract in [Lesson lifecycle CLI](lesson-lifecycle.md#64-lifecycle-actions).

<a id="runtime-capture"></a>

## 7. Runtime capture

### 7.1. Observed runtime occurrences

- Managed execution captures nonzero completed command exits, commands every provider
  reports failed without an exit code (`command-failed`), failed tool calls, backend/Goal
  errors and attempt failures. A `grep`/`rg` that ends the command with exit code 1 and
  no output found nothing; it is not captured.
- Each capture is an occurrence of one record per signature: provider, role, command kind
  (`test`, `search`, `build`, `lessons-cli`, `git`, `script`, `read`, `other`; `tool` or
  `runtime` otherwise) and exit code. The stable record ID is `runtime-<signature hash>`
  with scope `runtime`, stored through the body/metadata contract above; it counts recurrences and carries no diagnosis. Occurrences keep
  the signature and point to the run; raw commands and outputs are never stored.
- When the same command later succeeds in the same run, its earlier occurrences are marked
  `recovered`. Recovery is not a confirmed cause.

### 7.2. Resolution and isolated storage

- The Agent resolves or promotes only a cause it has established: record it in its own
  error record in the task scope, citing the occurrence `source`. Resolve a signature
  record only when that cause explains the signature itself, not one occurrence.
- An isolated code run captures into its document-owning Work Unit while retaining the
  original project runtime identity. If no unit contains that document workspace, keep
  the capture pending; never write the original checkout to compensate.

### 7.3. Pending and restricted-run capture

- A pending capture never fails or delays a run; the run's public state counts it as
  `pendingLessons`. Providers that do not emit a failure event still require Agent recording
  and occurrence auditing before handoff.
- Restricted-run hooks persist redacted rejection occurrences directly into the bound run's
  pending capture storage even when the provider emits no failed-tool event. The runtime
  later records them where permitted.

### 7.4. Migration and read-only behavior

- `migrate_runtime_lessons.py` previews merging older per-occurrence captures into signature
  records, keeping each original ID and source on its occurrence; resolved, reviewed and
  Agent-written records stay. It changes files only with `--apply` and an empty backup directory,
  which the Human must authorize because it removes the merged originals.
- Read-only execution leaves a pending record in runtime storage instead of writing
  the project through the host. Report the storage constraint; do not bypass it.

### 7.5. Capture storage and replay

- The runtime owns `lesson-capture/` and names its captures `<24 hex digits>.json`; only
  those count as pending. Keep your own CLI input files beside it in the run directory.
- Recording failures remain in the run's `lesson-capture/` directory. Managed completion
  retries them, and every later run that may write the project records what earlier runs
  left pending once its own outcome is stored: idempotent per occurrence, bounded per
  sweep and never changing that run's result. You may also retry `record` with the pending
  JSON. This retries documentation only, never the failed tool.
- A non-retryable storage diagnostic stops automatic recording, replay and pending sweeps
  for the same run and document workspace. Its run-local `lesson-storage-block.json`
  retains the diagnostic; capture inputs remain pending and counts remain accurate.
  Transient failures retain bounded retries. After repair, a new writable run can resume
  earlier pending captures; manual lifecycle calls can resume after a successful `check`.
