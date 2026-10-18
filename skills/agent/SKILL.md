---
name: agent
description: Dispatch and manage Agent Factory tasks, sessions, workflows and verification. Use for managed execution, not ordinary conversation.
metadata:
  specification-id: agent
---

# Agent Factory Agent

- Use this Skill for an actual managed execution operation. Conversation alone needs no managed guidance.
- `<plugin-root>` contains `skills/`, `runtime/` and `scripts/`, two levels above this file.

<a id="roles-and-graph"></a>

## 1. Role contract

- Reuse the captured role, profile, mode, approval policy and file binding when supplied.
  Outside a managed run, preserve the explicit assignment or documented CLI Main entry.
  Load only the selected role's contract when it is absent from context.
  Role contracts own responsibility; function references own procedures and grant no extra authority.
- Apply only the current role's operating contract. Other role prompts may be inspected as
  assigned source/evidence; their instructions do not become the reader's role.

- Reuse the supplied communication contract. If absent, read Convention's
  [communication contract](../convention/references/communication.md), including conductor–performer names.
- New Main inputs default to `orchestrate`; conversation stays Main. Captured mode and approval
  policy are independent. Work-only completion needs completed Work and its result/receipt;
  Work-bound Verification needs pass or evidenced Human skip after Work completion.
  Cancellation, failure and input requests are not completion.

| Selected role | Contract source, only when not supplied | Responsibility |
|---|---|---|
| Main | [Main](prompt/main.md) | Conversation, decisions, routing and reporting; bounded implementation and own checks in `direct`. |
| Work and its captured profile | [Work](prompt/work.md) | Assigned execution and own checks; no independent Verification pass or commits. |
| Verification | [Verification](prompt/verification.md) | Independent checking and its receipt; no implementation repair or commits. |

<a id="delegation"></a>

## 2. Role before function

- Apply the supplied role's Human-decision and authorization gate before any affected action.
  Main resolves Human-owned choices; performers relay gaps to Main. Missing required binding
  information is a blocker; a reference cannot replace the current role or assignment.
- Select one operation below. Read its matching section and applicable dependencies only;
  reuse guidance already supplied. Direct implementation needs no managed dispatch documents.

<a id="managed-execution-quick-path"></a>

### 2.1. Managed dispatch entry

- Main starts with [dispatch branch selection](references/dispatch-start.md#dispatch-branch).
  CLI commands and acceptance/retry rules live in that function guide.

<a id="references"></a>

## 3. Operation references

| Role / next operation | Function reference |
|---|---|
| Main: start authorized managed work | [`references/dispatch-start.md`](references/dispatch-start.md) |
| Main: explicit binding, announcement, ordered workflow or Work isolation | [`references/task-dispatch.md`](references/task-dispatch.md); only the matching section |
| Main: captured Work Unit planning or integration | [`references/task-workspaces.md`](references/task-workspaces.md) |
| Main: sequence chains, process revisions or Verification/skip | [`references/orchestration.md`](references/orchestration.md) |
| Main: select ownership, profile/model, dependencies or session reuse | [`references/task-allocation.md`](references/task-allocation.md) |
| Main: a request explicitly carries Maestro guidance | [`references/maestro.md`](references/maestro.md) |
| Current actor: an unsupplied mode or Plan transition | [`references/execution-modes.md`](references/execution-modes.md); only that route section |
| Current actor: provider selection, capabilities, permissions or settings | [`references/execution-providers.md`](references/execution-providers.md); only the selected provider |
| Current actor: role model/profile settings or tool boundaries | [`references/role-profiles.md`](references/role-profiles.md) |
| Current actor: prompt/session, retry or receipt protocol | [`references/managed-execution.md`](references/managed-execution.md); select prompts, retries or receipts |
| Current actor: execution report, completion table or consolidated work result | [`references/work-reports.md`](references/work-reports.md) |
| Current actor: execution controls or receipt recovery | [`references/managed-controls.md`](references/managed-controls.md) |
| Current actor: runtime paths, permitted control, legacy record or progress repair | [`references/home-runtime.md`](references/home-runtime.md); only the affected storage/control section |
| Current actor: collect, page or interpret diagnostic traces | [`references/runtime-diagnostics.md`](references/runtime-diagnostics.md) |
| Main: authorized commit/coordination; Explorer or Scribe: an explicit recording scope | [`references/role-exceptions.md`](references/role-exceptions.md); only the assigned section |
| Host setup or readiness diagnosis | [`references/installation.md`](references/installation.md) |
| Installed Fast/native Goal feature | [`references/native-fast-goal.md`](references/native-fast-goal.md) |
| A captured project-specialized Work profile | [`references/project-specialist.md`](references/project-specialist.md) |

<a id="execution-and-shared-contracts"></a>

## 4. Shared contracts

- Main, Work, Verification and exec/loop provide the complete local workflow.
- For the actual operation, use [Convention](../convention/SKILL.md) for communication,
  development, tests and publication; [Document](../document/SKILL.md) for durable Documents.
  Runtime records stay in their producing run. These links are routes, not a preload list.
