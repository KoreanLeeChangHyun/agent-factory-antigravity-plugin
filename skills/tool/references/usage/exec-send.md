# `exec.py send` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

## `send`
Required: `--agent AGENT`
One of: `--request-file` | `--message` | `--input-file`
- `--project-root PROJECT_ROOT`
- `--runtime-home RUNTIME_HOME`
- `--project-id PROJECT_ID`
- `--task-workspace-file TASK_WORKSPACE_FILE`: Runtime-owned task Work Unit binding captured by loop.py
- `--task-list-file TASK_LIST_FILE`
- `--task-id TASK_ID`
- `--document-context-file DOCUMENT_CONTEXT_FILE`: Explicit per-request document query, scope, required sources and selections JSON; does not grant authority
- `--request-file REQUEST_FILE`
- `--message MESSAGE`
- `--input-file INPUT_FILE`: versioned agent-input JSON with sibling, file-backed images
- `--actor {main,human}`
- `--human-approval-policy {required,bypass}`: Main delegation approval policy; omitted sends preserve the session policy
- `--task-mode {orchestrate,direct,work,plan,verification,plan-work,work-verification,plan-work-verification}`: Captured execution route; new Main requests default to orchestrate
- `--work-profile {work,workLight,explore,scribe}`: Work profile Main chose (work = Expert, workLight = Worker, explore = Explorer, scribe = Scribe); selects no model; explore writes exact task-bound evidence Documents and scribe writes only inside docs/
- `--model MODEL`
- `--provider {codex,claude,antigravity}`
- `--reasoning-effort {none,minimal,low,medium,high,xhigh,max,ultra}`
- `--agent-permissions AGENT_PERMISSIONS`: Captured Human-selected role permission overrides as JSON
- `--work-isolation {on,off}`: Captured Human-selected Work isolation toggle; on requires AI-chosen task Work Units for delegated Work
- `--fast | --no-fast`
- `--goal-mode | --no-goal-mode`
- `--goal-objective GOAL_OBJECTIVE`: Native persisted nonempty objective; omitted on send preserves the existing objective
- `--receipt-request-hash RECEIPT_REQUEST_HASH`: SHA-256 identity the role receipt must bind (defaults to this run request)
- `--response-contract {1,2}`: Work response contract: 1 = the Agent writes receipt.json, 2 = receipt fields in the structured final output (default where the provider attaches the schema to the final turn)
- `--verified-work-run-id VERIFIED_WORK_RUN_ID`: exact Work run checked by a Verification Agent (required for Verification runs)
- `--dispatch-id DISPATCH_ID`: optional idempotency key: dispatch-[A-Za-z0-9][A-Za-z0-9._:-]{0,127}; generated when omitted; reuse the same key only for recovery of the same request
- `--handoff-experiment`: Opt a newly created Main experiment into two-session handoff; never resets an existing conversation
- `--handoff-preparation-for HANDOFF_PREPARATION_FOR`: Main-owned read preparation for an opted-in experiment; grants no response or task-assignment authority
- `--capability-binding-file CAPABILITY_BINDING_FILE`: strict Agent capability/authority/effects binding to preserve in this run
- `--codex CODEX`
- `--sandbox {read-only,workspace-write,danger-full-access}`
- `--execution-policy-file EXECUTION_POLICY_FILE`
- `--approval-policy {never,on-request,untrusted,on-failure}`
- `--network-access | --no-network-access`
- `--writable-root WRITABLE_ROOT`
