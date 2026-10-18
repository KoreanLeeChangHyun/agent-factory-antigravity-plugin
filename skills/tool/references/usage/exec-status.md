# `exec.py status` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

## `status`
Required: `--agent AGENT`
One of: `--run-id` | `--dispatch-id`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--run-id RUN_ID`
- `--dispatch-id DISPATCH_ID`
- `--document {state,request,result,receipt,capability,loop,trace,trace-error,events,provider-events}`: Read a document as lossless Unicode text pages (default page: 4000 characters)
- `--field FIELD`: Select a JSON Pointer before paging; strings are returned verbatim
- `--offset OFFSET`: Zero-based Unicode character offset (enables paging)
- `--length LENGTH`: Characters per page, default 4000; no total document limit
- `--revision REVISION`: Require the SHA-256 returned by the first page; changed data fails closed
