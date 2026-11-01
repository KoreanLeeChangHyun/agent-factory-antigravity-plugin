# `testing.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

## `catalog`: List versioned tools, JSON schemas, drivers and limitations; launches nothing
- `--tool {test.start,test.observe,test.act,test.inspect,test.check,test.reset,test.review,test.finish,test.doctor,test.setup,test.environments,test.configure}`

## `doctor`: Detect dependencies and verify a real Chromium launch; read-only
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`

## `setup`: Install missing per-user Node.js, Playwright and Chromium, then verify launch
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`

## `environments`: List saved project environments and retained sessions
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`

## `configure`: Validate and save a named environment in project runtime storage
Required: `--profile PROFILE`
One of: `--input` | `--input-json`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--input INPUT`
- `--input-json INPUT_JSON`

## `start`: test.start: launch a dedicated environment with a frozen manifest
One of: `--file` | `--profile`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--file FILE`: JSON manifest; see the catalog and testing-harness reference
- `--profile PROFILE`: Saved environment identifier
- `--wait-sec WAIT_SEC`: Startup wait; a timeout preserves the session ID for status/finish

## `status`: Read session state and evidence paths, including after the supervisor stops
Required: `--session SESSION`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`

## `observe`: test.observe: capture the running screen, elements and correlated logs
Required: `--session SESSION`
One of: `--input` | `--input-json`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--input INPUT`: Tool input JSON file
- `--input-json INPUT_JSON`: Tool input JSON object; do not put secrets in shell history
- `--wait-sec WAIT_SEC`: Request wait; timeout never retries the action automatically

## `act`: test.act: click, fill, type, press, navigate, scroll, execute argv or drive a VS Code bridge
Required: `--session SESSION`
One of: `--input` | `--input-json`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--input INPUT`: Tool input JSON file
- `--input-json INPUT_JSON`: Tool input JSON object; do not put secrets in shell history
- `--wait-sec WAIT_SEC`: Request wait; timeout never retries the action automatically

## `inspect`: test.inspect: read browser state, files, HTTP responses, SQLite rows or a VS Code snapshot
Required: `--session SESSION`
One of: `--input` | `--input-json`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--input INPUT`: Tool input JSON file
- `--input-json INPUT_JSON`: Tool input JSON object; do not put secrets in shell history
- `--wait-sec WAIT_SEC`: Request wait; timeout never retries the action automatically

## `check`: test.check: evaluate a frozen scenario/check against an independently read observation
Required: `--session SESSION`
One of: `--input` | `--input-json`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--input INPUT`: Tool input JSON file
- `--input-json INPUT_JSON`: Tool input JSON object; do not put secrets in shell history
- `--wait-sec WAIT_SEC`: Request wait; timeout never retries the action automatically

## `reset`: test.reset: restart owned processes and restore session-owned data; retain all attempts
Required: `--session SESSION`
One of: `--input` | `--input-json`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--input INPUT`: Tool input JSON file
- `--input-json INPUT_JSON`: Tool input JSON object; do not put secrets in shell history
- `--wait-sec WAIT_SEC`: Request wait; timeout never retries the action automatically

## `review`: test.review: pause automation and open a local interactive review console; resume explicitly
Required: `--session SESSION`
One of: `--input` | `--input-json`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--input INPUT`: Tool input JSON file
- `--input-json INPUT_JSON`: Tool input JSON object; do not put secrets in shell history
- `--wait-sec WAIT_SEC`: Request wait; timeout never retries the action automatically

## `finish`: test.finish: save the report and stop only this session's owned environment
Required: `--session SESSION`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--wait-sec WAIT_SEC`: Request wait; timeout never retries the action automatically
