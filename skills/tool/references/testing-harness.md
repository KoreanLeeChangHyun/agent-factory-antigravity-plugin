# Persistent test harness

## 1. Tools and discovery

- Run `python3 <plugin-root>/scripts/testing.py catalog` for the versioned machine catalog:
  tool names, input JSON Schemas, driver capabilities and limitations. Use
  `catalog --tool test.act` to select one tool. The generated
  [CLI usage](usage/testing.md) is derived from argparse.
- Tools are CLI-backed. `test.start` maps
  to `testing.py start`; the other `test.*` names map to their matching subcommands.
- Every session command takes `--project-root`, optional pinned `--runtime-home` and
  `--project-id`, and `--session` from start. Payloads use `--input <file>` or
  `--input-json <object>`. Start instead takes `--file <manifest>`.
- The tools preserve the caller's existing authority. Only `test.setup` installs
  dependencies; session tools never install software or change their frozen expectations.

| Tool | Effect |
| --- | --- |
| `test.doctor` | Detect dependencies and verify a real Chromium launch without installing anything |
| `test.setup` | Install missing per-user dependencies and verify Chromium launch |
| `test.environments` | List saved project environments and retained sessions |
| `test.configure` | Validate and save a named environment manifest |
| `test.start` | Freeze build files, scenarios and expectations; start an owned environment and persistent supervisor |
| `test.observe` | Capture the actual browser viewport and elements/log paths, command logs, or a live VS Code bridge snapshot |
| `test.act` | Operate the browser, execute argument tokens, or drive the designated VS Code development chat |
| `test.inspect` | Read browser state, files, HTTP GET responses, read-only SQLite queries or a VS Code snapshot |
| `test.check` | Compare a frozen check against a fresh probe; no caller-supplied actual or expected values |
| `test.reset` | Stop owned processes and recreate session-owned data/profile; retain every prior attempt and its evidence |
| `test.review` | Pause AI mutation and return the local review console; `{"action":"resume"}` resumes automation |
| `test.finish` | Stop owned processes and preserve the report, screenshots, browser trace, logs and unchecked items |

- `status` reads durable session state even after the supervisor exits. Exit codes are
  0 for an observed operation, 1 for an environment/tool error and 2 for a failed check
  or failed overall outcome. Exit 0 does not establish functional completion.

## 2. Start manifest

- Initialize the project through `exec.py init` first. Keep the manifest in an existing
  task/run location. It must contain at least one scenario with at least one check.
- `build.files` lists the actual executable/bundled files being exercised, relative
  to the project root. Their SHA-256 identities and the manifest are fixed at start.
  Changes invalidate the session; a label or source commit alone cannot prove which
  build a running target loaded. Include all relevant build dependencies.
- Start runs only an explicit `environment.argv` array, without shell parsing. The
  command must stay in the foreground. `readyUrl` or `readyFile` establishes startup
  readiness. Without them, start establishes process launch only; subsequent actions
  and probes must establish application readiness.
- `${projectRoot}`, `${sessionDir}`, `${dataDir}` and `${port}` are expanded in target
  commands, environment values, URLs and probe paths. The target receives
  `AF_TEST_DATA_DIR`, `AF_TEST_PORT`, `AF_TEST_SESSION` and a dedicated
  `AGENT_FACTORY_HOME`. It must honor those locations for state isolation.
- `environment.seed` optionally names a project directory frozen into the session at
  start and copied from that frozen snapshot into its data directory at start/reset.
  Later edits to the original seed cannot change reset conditions. Only session-owned data, browser profile and target
  runtime are removed by reset. Other filesystem/database state is not reset.

For a project with an existing `index.html` containing `#setting` and `#save`, this
manifest serves the real page and checks the setting after the scenario's actions:

```json
{
  "schemaVersion": 1,
  "name": "Setting persistence",
  "build": {"files": ["index.html"]},
  "environment": {
    "kind": "browser",
    "argv": ["python3", "-m", "http.server", "${port}", "--bind", "127.0.0.1"],
    "readyUrl": "http://127.0.0.1:${port}/index.html",
    "url": "http://127.0.0.1:${port}/index.html",
    "timeoutSec": 30
  },
  "scenarios": [{
    "id": "save", "title": "Save and reopen a setting",
    "checks": [{
      "id": "persisted", "probe": {"kind": "browser", "selector": "#setting", "property": "value"},
      "operator": "equals", "expected": "example"
    }]
  }]
}
```

```sh
python3 <plugin-root>/scripts/testing.py start --project-root <project-root> --file <manifest.json>
python3 <plugin-root>/scripts/testing.py act --project-root <project-root> --session <session> --input-json '{"scenario":"save","action":"fill","selector":"#setting","text":"example"}'
python3 <plugin-root>/scripts/testing.py act --project-root <project-root> --session <session> --input-json '{"scenario":"save","action":"click","selector":"#save"}'
python3 <plugin-root>/scripts/testing.py act --project-root <project-root> --session <session> --input-json '{"scenario":"save","action":"reload"}'
python3 <plugin-root>/scripts/testing.py check --project-root <project-root> --session <session> --input-json '{"scenario":"save","check":"persisted"}'
python3 <plugin-root>/scripts/testing.py review --project-root <project-root> --session <session>
python3 <plugin-root>/scripts/testing.py finish --project-root <project-root> --session <session>
```

## 3. Drivers and probes

- **Browser:** requires installed Node.js, Playwright and its Chromium. Set
  `environment.playwrightModule` or `PLAYWRIGHT_MODULE` when needed; otherwise reuse
  the same installed-module discovery as `evidence.py`. The browser stays alive
  between tool calls. Observe returns visible element descriptions and an actual
  viewport screenshot, not an HTML replay. Browser logs are recorded immediately;
  Playwright trace ZIP files are finalized when the browser closes/reset/finish.
- Browser actions: `click` with `selector` or viewport `x/y`; `fill` with
  `selector/text`; `type` with `text`; `press` with `key`; `scroll` with `x/y`;
  `navigate` with `url`; `reload`; `back`; `select` with `selector/value`; `check`
  with `selector/value` boolean; `tab` with a zero-based `index` from observe.
- **Command:** `act` takes `{"scenario":"id","action":"exec","argv":[...]}`.
  Commands inherit the dedicated session environment. Exit status, complete output
  and the log path are evidence; exit 0 does not pass a scenario.
- **VS Code:** set `environment.kind` to `vscode` and `bridgeCommand` to explicit
  tokens such as `["node","/installed-extension/scripts/debug-chat.mjs"]`.
  `chat` selects the designated development chat. The extension must already provide
  its development bridge; start does not switch modes or install an extension.
  Actions are `send` with `text`, `close`, `reload`, and `click` with `selector`.
  With no explicit foreground launcher the Host is attached, not owned or isolated;
  reset is refused. Its existing chat/runtime data remain under that Host's control.
  Click uses the existing bridge capture with `--keep`; any returned capture is HTML
  replay, not a native-window screenshot. Review the native Host directly.
- File/SQLite paths must resolve inside the project or this session. SQLite uses
  read-only mode and an authorizer rejecting writes/attachments. HTTP probes perform
  GET and return `{"status":...,"body":...}`; JSON bodies are decoded. Browser
  properties are `text`, `value`, `visible`, `count`, `url`, `title`.
- `jsonPointer` selects a value from a decoded JSON file, HTTP response, SQLite rows
  or bridge snapshot. Empty pointer selects the full value. A missing source or a
  probe error stays unverified rather than passing.
- Operators: `equals` compares type and value, `contains` tests membership, `exists`
  compares presence against a boolean, `count` compares length to an integer, and
  `matches` uses a regular expression. The frozen check defines operator/expected.
- A check may bind `timeoutSec` to wait for an asynchronous result; default 0 observes
  once. Probe errors remain unverified. Budget the CLI request wait for the full probe
  timeout plus the check deadline.

## 4. Evidence, review and recovery

- Sessions live under the project's resolved runtime, outside the checkout:
  `test-sessions/<session>/`. `state.json`, `manifest.json`, `events.jsonl`, per-operation
  JSON, `evidence-*.json`, screenshots, process/browser logs and final `report.json`
  retain the build identity and reset generation. Runtime evidence may contain
  application data; it is private and never automatically uploaded or deleted.
- A check without a successful scenario action in the current generation is
  unverified. A new action invalidates that scenario's previous checks; reset clears
  current checks/reviews while retaining historical evidence. Failed actions and
  probes remain in the event/operation records.
- `automationVerdict` reports the frozen checks. `humanVerdict` reports the separate
  per-scenario review. `outcome` passes only when both pass; pending review or missing
  checks stays unverified. These are recorded observations, subject to the
  [functional completion contract](../../convention/references/testing.md#functional-completion).
- The local review URL controls the **same** live browser, through screenshots,
  clicks, text entry, keys and scrolls. It supports per-scenario pass/fail and notes.
  For command/VS Code drivers it shows evidence and records review; native interaction
  remains in the target application. Use port forwarding for a remote host. Protect
  the capability URL; the console is local and does not independently authenticate
  the reviewer's identity. The CLI provides no Human-approved flag.
- While review is active, automation actions and reset are refused. Observation and
  fresh checks remain available. Manual actions are recorded and invalidate affected
  checks too; recheck the scenario before finalizing if necessary.
- Do not automatically retry a timed-out mutation. The error includes its operation
  ID and result path; inspect them and status first. The supervisor survives CLI and
  Extension Host restarts. After supervisor loss, finish uses recorded process
  identities to recover owned children and reports unverified. It never adopts or
  kills an unrelated application. Keep target processes in the foreground.
- Profiles and data directories are application-state isolation, not an OS sandbox.
  External targets remain subject to the task's authority and their own side effects.

## Settings and automatic setup

The extension exposes Settings → Testing, with dependency detection, installation, saved environments, session controls and the tool catalog. The environment form saves a manifest without hand-writing JSON. Starting a saved browser environment prepares missing dependencies automatically. Command and VS Code targets do not require browser installation.

`testing.py doctor --project-root ROOT` is read-only and verifies an actual Chromium launch, not merely a package file. `setup` installs missing Node.js, Playwright and Chromium per user under `<runtime-home>/tools/testing`, outside the project checkout. Healthy existing installations are reused. Managed installs use Node.js 24.21.0 and Playwright 1.61.1; Node archives are verified against the official SHA256 list. Installation failures, unsupported platforms and missing OS libraries remain errors, never readiness. OS package installation is not performed by this command.

Use `configure --project-root ROOT --profile ID --input FILE` to validate and save a manifest, `environments --project-root ROOT` to list saved environments and retained sessions, and `start --project-root ROOT --profile ID` to launch one. All commands except catalog accept the ordinary runtime-home/project-id binding options. CLI start never implicitly installs dependencies; call setup first when needed. Editing a saved environment never changes an existing session's frozen manifest or expected results. The catalog also lists the four environment-management commands.

Dependency installation follows the official [Playwright browser installation contract](https://playwright.dev/docs/browsers) and downloads Node.js archives and checksums from [the official Node.js release archive](https://nodejs.org/dist/).
