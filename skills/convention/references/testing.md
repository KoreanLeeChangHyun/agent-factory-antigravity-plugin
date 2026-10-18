# Testing Convention

- Use this reference before authoring or changing tests, and when organizing, selecting, or running them.

<a id="source-organization"></a>

## 1. Source organization

<a id="layout-rules"></a>

### 1.1. Layout rules

- Use `tests/` as the test root.
- Group tests by owning domain/component within the project's established test layout.
  Reuse its purpose-level categories; do not invent a competing directory taxonomy.
- Do not accumulate tests directly under `tests/` or classify them only by filename
  prefixes.
- Keep runner configuration and shared discovery hooks at the root when the framework
  requires it.
- Extend an existing category before creating another.
- Update collection and imports when moving files.

<a id="collection"></a>

### 1.2. Collection

- Follow the project runner’s test naming and discovery rules.
  Keep helpers outside collected test modules.
- Configure shared import paths once; avoid duplicated path/bootstrap code.
- Remove tests for retired domains/deleted Human document packages.
- Test maintained ownership and observable behavior, not generated prose wording.

<a id="test-authoring"></a>

### 1.3. Test authoring

- Keep each domain's test code minimal, covering distinct core contracts and actual
  defects. Reuse existing cases and helpers; no fixed test-count quota or one test file
  per code change. Preserve meaningful coverage when reducing duplication.
- Treat full-suite execution cost as a design constraint when adding tests. Do not
  create a new test merely because code changed or to increase the test count.
- First inspect existing coverage. Extend an existing case or parameterize distinct
  inputs when that captures missing behavior without repeating expensive setup.
- Test meaningful observable behavior, regression risks, boundaries and failure paths.
  Prefer the lowest-cost test layer that can detect the actual defect.
- Avoid assertions that duplicate implementation or match incidental source text,
  private names, formatting or generated prose. Check exact text only when it is itself
  the maintained public contract.
- Preserve real integration coverage where mocks would hide filesystem, process,
  network or browser defects. Do not repeat full integration setup for every pure-logic
  input variation.
- Use the smallest fixture that exercises the condition. Keep benchmark workloads
  separate from ordinary correctness cases unless scale is essential to the regression.
- Do not add tests for reversible, low-impact edits without a concrete regression risk.
  Preserve existing meaningful coverage and failure visibility.

<a id="test-preparation-and-waits"></a>

### 1.4. Preparation and waits

- Reuse immutable build outputs, parsed templates and expensive read-only setup within
  an appropriate runner or fixture scope. Avoid compiling the same source per case.
- Keep mutable application state, temporary repositories and runtime homes isolated.
  Shared preparation must not introduce dependencies on test execution order.
- Keep caches local to a test invocation unless input/dependency invalidation is
  explicitly implemented and checked. Faster runs must still exercise changed code.
- For timer logic, use controllable clocks or supported fake timers instead of actual
  sleeps. Restore mocks after each test and check the project's runner version.
- For real asynchronous integration, await the required event or observable condition
  with a bounded timeout. Do not replace filesystem/process completion with fake time
  or shorten timeouts solely to claim a speedup.
- In browser tests, prefer locators and condition-based assertions with automatic waiting
  over fixed sleeps. Reuse browser startup where supported while isolating test contexts.
- Arrange independent slow groups so the runner can distribute them. Avoid many tiny
  test processes when startup would dominate the work.

<a id="focused-execution"></a>

## 2. Focused execution

- Select checks for the affected domain and observable problem. State their purpose
  briefly in the existing run record and use the result to decide the next action.
  For a reported defect, reproduce its conditions and repeat them after the fix.
  Apply [functional completion](#functional-completion) to decide whether feature
  testing succeeded.
- Run only the smallest relevant test set for the owning component and affected
  contract.
- For prose-only changes, check affected links, paths and metadata. Run product tests
  only for an affected runtime contract or an explicit Human request.
- Resolve it from the project's established runner and current test layout; do not treat
  one framework or command as universal.
- Treat the interpreter and dependency environment as part of that runner. Before
  execution, inspect repository evidence such as environment directories, tool
  configuration, dependency files and CI setup; do not assume the system-default Python
  contains the project's test dependencies.
- Run an exact Human-supplied command unchanged first.
  - If it fails before collection because its interpreter lacks the runner or
    dependencies, make no installation change unless authorized.
  - Resolve an existing compatible project environment and retry the same test scope and
    options through that environment.
  - Report the initial infrastructure failure separately from the retry result.
- Never encode a development sibling's environment path as a durable repository command.
  An evidenced adjacent shared environment may be used only as a local execution
  fallback when its compatibility is checked for the selected test.
- Before attributing a failure to the change, reproduce the same check against the
  unchanged baseline (for example a temporary copy of `HEAD`). Report failures that
  also occur on the baseline separately as pre-existing, and do not repair unrelated
  product code or shared tests outside the task's scope to make them pass.
- Broaden only when focused evidence demonstrates cross-domain impact or the Human
  explicitly requests broader coverage.
- Run a full suite only on explicit Human request.
- Collect [diagnostic logs](#diagnostic-logs) for the exercised flow. UI/UX acceptance
  additionally requires [captured-screen inspection](theme.md#visual-acceptance). Use the
  project's recorded [verification environment](verification-environment.md).

<a id="parallel-execution-and-speed"></a>

## 3. Parallel execution and speed

- When optimizing tests, measure collection, setup, execution and teardown before
  changing the runner. Use duration reports or profiling to locate expensive paths.
- Compare the same scope and environment across repeated runs. Record wall time,
  outcomes and cache/worker settings. Do not remove assertions, skip slow cases or
  hide failures to improve timing.
- For an authorized full suite, prefer the runner's process-based parallel execution
  after checking that tests isolate mutable state. Keep small focused runs serial when
  worker startup would cost more than it saves.
- Isolate runtime homes, temporary files, databases, ports, and subprocess ownership per
  worker or test. Sequence cases that must share an external resource; do not remove
  assertions or hide failures to make parallel runs pass.
- Bound worker count to the available CPU, memory, and child-process load. Compare
  elapsed time and outcomes on the same suite and environment before claiming a speedup;
  preserve a serial command for diagnosis.
- Parallel execution does not expand test authorization or enable opt-in external
  integrations automatically.

<a id="agent-graph-boundary"></a>

## 4. Agent graph boundary

- Organizing/authoring tests grants no execution authority. Within the bounded request,
  Work performs necessary own checks and records commands/results or reasons not run.
  These checks never substitute for independent Verification in verification modes.
  Main performs own checks in direct mode only; for delegated work Main compares the
  result's evidence with Done under [result alignment](../../agent/references/orchestration.md#result-alignment)
  without reviewing implementation or rerunning tests.
  Plan-only returns its plan without implementation or execution checks.
- Verification independently checks exact Work with the smallest authorized tests.
- Report skipped/unrun tests honestly, never as passes.

<a id="diagnostic-logs"></a>

## 5. Diagnostic logs

- Keep detailed logs sufficient to reconstruct each exercised domain flow. Reuse the
  existing domain logger and runner capture. Record timestamps, domain/action and
  available request/run identifiers, relevant settings, state transitions, expected
  and observed outcomes, and errors with useful stack traces or command/host/browser output.
- Correlate UI actions, host/runtime events and the final result when the problem crosses
  those boundaries. Preserve failure evidence and distinguish application errors from
  environment or test-harness failures. Apply existing secret and private-data controls.
- Keep disposable raw logs in the producing run's storage. Retained evidence follows
  [artifact storage](artifacts.md). Read relevant segments by identifiers and time;
  report paths and concise findings instead of copying full logs into prompts or chat.
- Use correlated logs to confirm the actual outcome under
  [functional completion](#functional-completion). UI/UX also requires
  [direct visual inspection](theme.md#visual-acceptance).

<a id="functional-completion"></a>

## 6. Functional testing completion

### 6.1. Limits of code and API checks

- MUST NEVER use passing test code, a successful runner exit or pass counts as an
  indicator that functional testing succeeded or is complete. Record these only as
  auxiliary code/API check results with their actual scope and environment.
- An exercised API call without an error establishes only that observed call's result.
  It does not establish a correct feature outcome or guarantee an error-free deployment.
  Mocks, fixtures and absence of exceptions provide no substitute for the E2E evidence below.

### 6.2. Required E2E operation and evidence

- The assigned checker MUST directly operate the feature end to end in the actual
  application/runtime through its real user or API entrypoints. Use existing interaction
  tools to exercise the scenario from starting state and trigger through processing to
  the final user-visible or domain result. For a defect, repeat the reported conditions.
- Correlate the operation with its detailed logs and verify the expected result,
  including persisted state or side effects where applicable. Confirm from the same
  scenario and logs that the reported problem is resolved; an error-free response alone
  is insufficient.
- For a screen change, MUST capture the actual scenario's rendered screen and directly
  inspect the images under [visual acceptance](theme.md#visual-acceptance). Decide UI/UX
  testing completion from those inspected captures together with the E2E outcome and logs.
- Record the scenario, actual environment/build, actions, expected/observed result and
  correlated log paths/identifiers in the existing run record. For UI changes, include
  capture paths and the visual findings. Keep functional testing unverified/incomplete
  when required operation, logs or visual evidence is unavailable; state the missing
  evidence even if implementation or auxiliary checks have finished.
