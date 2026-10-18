# `evidence.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Every subcommand with options also accepts: `--project-root PROJECT_ROOT`, `--runtime-home RUNTIME_HOME`, `--project-id PROJECT_ID`.

## `capture`: Screenshot a page or local file with an installed Playwright and save its browser log
Required: `--target TARGET`, `--out OUT`
- `--viewport VIEWPORT`: WIDTHxHEIGHT in CSS pixels
- `--scale SCALE`: Device scale factor
- `--wait-for WAIT_FOR`: CSS selector that must appear before anything else
- `--click CLICK`: CSS selector clicked before the capture; repeat in order
- `--wait-ms WAIT_MS`: Extra settle time after the clicks
- `--element ELEMENT`: Capture only the first visible element matching this selector
- `--full-page`: Capture the whole scrollable page
- `--timeout-sec TIMEOUT_SEC`

## `checks`: Run named checks in parallel and compare them with this project's saved baseline
- `--check NAME=COMMAND`: A check run by the shell in the project root; repeat
- `--file FILE`: JSON {"checks":[{"name","command","cwd"?}]} with more checks
- `--set SET`: Baseline name, for separate check groups
- `--jobs JOBS`
- `--timeout-sec TIMEOUT_SEC`
- `--save-baseline`: Store this run as the baseline of --set

## `hold`: Run a command while holding a named shared test environment; other holders wait
Required: `--name NAME`, `--purpose PURPOSE`, `argv -- COMMAND`
- `--wait-sec WAIT_SEC`
