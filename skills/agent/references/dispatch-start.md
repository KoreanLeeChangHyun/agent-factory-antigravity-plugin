# Managed dispatch start

- Main uses this function guide after the captured authorization gate. Responsibility,
  approval policy and model/profile limits remain in the supplied role contract.
- Reuse supplied instructions and bindings. Read only the branch and section needed next.

<a id="dispatch-branch"></a>

## 1. Select the dispatch branch

- Ordinary briefs do not require task announcements or contract Documents. Existing explicit
  task lists and captured bindings retain their dispatch contract; never collapse their tasks.
- Required conditional dependencies still apply. A route row is not permission to skip
  authorization, file scope, capability checks or completion evidence.

| Condition | Function/section for that branch |
|---|---|
| Conversation or captured `direct` mode | No managed dispatch guide is needed. |
| Authorized bounded `orchestrate` brief | This guide's commands and [chain sequencing](orchestration.md); the runtime derives the brief's single task. |
| An explicit task list, announcement or contract binding | [Task binding](task-dispatch.md#task-binding) and the matching announcement/workflow section. Preserve separately announced task identities and criteria. |
| Captured Work isolation is enabled | [Task Work Units](task-dispatch.md#task-workspaces), including its captured workspace plan, for a brief or structured task. |
| Choosing owners, sessions, profiles/models or dependencies | [Task allocation](task-allocation.md); use its model-recommendation section when that capability is installed. |
| Plan transitions or a mode detail is not supplied | The matching [execution-mode section](execution-modes.md). |
| Continue or revise an accepted loop | [Orchestration](orchestration.md); retain the accepted loop/task/session identities. |

<a id="managed-execution-quick-path"></a>

## 2. Commands and acceptance

- `direct` needs no managed commands. An `orchestrate` brief needs no task list,
  announcement, contract or progress Document. Use the installed absolute script path,
  actual project root and bounded request; do not rediscover submission through runtime source.

- Agent IDs use at most 64 ASCII letters/digits/`.`/`_`/`-`, starting with a letter or digit.
  Give independent chains new identities; retain them for revisions.
- Loops own dispatch IDs and recovery. Standalone submit/send returns its generated ID.
  Preserve acceptance identities and inspect the existing Agent before retrying an uncertain submission.
  Explicit recovery keys use `dispatch-[A-Za-z0-9][A-Za-z0-9._:-]{0,127}` with the same immutable request.
- Inspect capabilities once per executable/configuration. Recheck after changes or relevant failures;
  do not prepend doctor/capabilities to every submission. Launch-time preflight still applies.
- Inspect a loop with `loop.py status/reconcile --project-root PROJECT --work-agent WORK_AGENT_ID --loop-id RETURNED_LOOP_ID`;
  a standalone run with `exec.py status/result --project-root PROJECT --agent AGENT_ID --run-id RETURNED_RUN_ID`.
  Acceptance is not completion. Preserve inherited policy and role/model choices.

| Captured route | Command |
|---|---|
| `orchestrate` brief | `python3 <plugin-root>/scripts/loop.py start --project-root PROJECT --task-mode work --work-agent UNIQUE_WORK_ID --request-file BRIEF --work-profile PROFILE`; `PROFILE`: `work`, `workLight`, `explore` or `scribe`. Begin `BRIEF` with a `Title: <a few words naming the work>` line (about 20 characters, a noun phrase in the Human's language, never the instruction itself); the runtime uses it as the task title. For explicit Verification, select `--task-mode work-verification` and supply `--verification-agent ID`. |
| `work`, `plan-work` | `python3 <plugin-root>/scripts/loop.py start --project-root PROJECT --task-mode MODE --work-agent UNIQUE_WORK_ID --request-file REQUEST` |
| `work-verification`, `plan-work-verification` | Same loop command, plus `--verification-agent UNIQUE_VERIFICATION_ID`. |
| `plan` | `python3 <plugin-root>/scripts/exec.py submit --project-root PROJECT --role work --task-mode plan --agent UNIQUE_WORK_ID --request-file REQUEST`; actual Plan mode, no implementation. |
| `verification` | `python3 <plugin-root>/scripts/exec.py submit --project-root PROJECT --role verification --task-mode verification --agent UNIQUE_VERIFICATION_ID --request-file REQUEST`; standalone receipt, not a Work-loop pass. |
