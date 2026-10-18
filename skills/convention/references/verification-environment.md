# Verification Environment

- Use this reference when implementing, checking or reporting work in any project, and when a
  project has no recorded way to observe its own behavior.

<a id="purpose"></a>

## 1. Purpose

- The AI verifies its own work with the evidence the Human would otherwise check: it operates
  the real application, reads its logs, captures its screens, runs repeatable scenarios with
  automatic verdicts and compares checks with a baseline. It never asks the Human to look at
  what these can show (Human decision 2026-10-18).
- This evidence is what Main compares with Done under Agent's
  [result alignment](../../agent/references/orchestration.md#result-alignment).

<a id="project-record"></a>

## 2. Project record

- Each project records its verification environment in the rule Document of the owning domain
  (`docs/skills/rule-<domain>-<name>/`). Without one, create `rule-<domain>-verification`
  following Document's rule specification. Record:
  - start, rebuild and reload commands, and how to confirm the running build is current;
  - entry points that operate features as a user would: UI driver, API, CLI or chat bridge;
  - log locations, correlation identifiers and how to read one flow's records in time order;
  - the screen capture command, its viewport and its limits (fonts, host chrome);
  - repeatable scenarios: command, what each judges, files and state it creates and removes;
  - check groups with their baseline set names;
  - shared mutable resources (ports, sandboxes, databases) with their hold names, and what
    cannot be observed and why.
- Read the record before checking. When it lacks what the changed area needs, add the missing
  part within the task's scope using installed tools, then record it. Installing software,
  new services or external accounts needs the Human's approval.

<a id="observing"></a>

## 3. Observing

- **Screens:** `python3 <plugin-root>/scripts/evidence.py capture --target <url|file> --out <png>`
  renders with an installed Playwright and writes the browser console, page errors, failed
  requests and HTTP errors to `<name>.log.json` beside the image. `--click`, `--wait-for` and
  `--element` reach a state. Open and inspect the image under Theme
  [visual acceptance](theme.md#visual-acceptance). Screens inside a host application (an
  editor webview, a desktop app) use the capture path the project records.
- **Logs:** correlate the operation with its logs under Testing
  [diagnostic logs](testing.md#diagnostic-logs); cite paths and identifiers.
- **Scenarios:** drive the real entry point and judge from recorded state, files, logs and
  captures, not from a performer's claim. Name the files a scenario creates per run and
  remove only those.
- **Check groups:** `evidence.py checks --set <group> --check NAME=COMMAND ...` runs checks in
  parallel and compares them with the set's baseline in runtime project storage. Save the
  baseline (`--save-baseline`) before changing code. Only failures absent from the baseline
  belong to the change; report existing ones separately (Testing [focused execution](testing.md#focused-execution)).
- **Shared environments:** run commands that use a shared mutable environment under
  `evidence.py hold --name <environment> --purpose <text> -- <command>`. Other sessions wait
  for the hold; nested calls run inside it.

<a id="results"></a>

## 4. Results

- Work results name their evidence: capture and log paths, scenario reports and the check
  summary with new and existing failures.
- Missing evidence is reported as unverified with its reason, never as passed.
