# Orchestration

- Main reads this before dispatching managed Work or Verification. Direct mode does not use it.

<a id="chains"></a>

## 1. Chains and shared resources

- Work isolation off (the default): use the current shared checkout without separate Git
  worktrees. Apply Convention's
  [shared checkout coordination](../../convention/references/development.md#shared-checkout-coordination) when assigning write boundaries, sequencing conflicts and stabilizing
  Verification inputs.
- Work isolation on (the Human's toggle, captured as `workIsolation` on the Main run): every
  delegated Work uses a Main-chosen [task Work Unit](task-dispatch.md#task-workspaces); the
  runtime integrates and cleans up without Human waits.
- Assess dependencies across repository paths/writes and shared mutable resources: Git
  index/worktree, Agent/session/loop/run IDs, databases, ports and external systems.
- Sequence uncertain independence or obtain the missing Human decision. Parallelize only
  useful independent chains with distinct Agent/loop/run IDs, bounded inputs, scoped
  authority and capability bindings.
- Each chain stays sequential.
  - In Work-bound verification modes bind separate Verification to exact completed Work unless
    Human skip applies.
  - In work and plan-work modes relay completed Work under [result relay](#result-relay),
    including its own checks, and end without separate Verification.
  - Plan alone dispatches Work with `--task-mode plan` and stops at its plan.
  - Plan-work routes use actual collaboration-mode transitions in the same Work session
    through loop.py.
  - Standalone verification dispatches Verification with `--task-mode verification`;
    resolve explicit target first, then prior completed work in this chat, otherwise ask.
    Its standalone receipt never substitutes for a Work-bound loop receipt.
  - Sequence overlapping work and repository-wide integration.
- Track every chain, preserve execution/results and integrate in dependency order.
  Conflict avoidance is your judgment, not a runtime guarantee or parallelism quota.

<a id="verification-and-skip"></a>

## 2. Verification and skip

- **Fail:** send findings to the same Work Agent; send revisions to the same
  Verification Agent. At the loop's revision limit, report the open findings and ask the
  Human whether to extend or close; never extend on your own.
- **Pass:** integrate and report.
- **Human skip:** record actor, authorization reference and decision evidence before the
  next Verification. Intent alone is no transition. Apply only after current
  initial/revision Work completes; reach END without starting further Verification.

<a id="result-relay"></a><a id="result-alignment"></a>

## 3. Result relay

- Main relays results under the Main prompt's [relay](../prompt/main.md#relay) rule (Human
  decision 2026-10-20, replacing result alignment of 2026-10-18).
- On completed Work, read the exact result and receipt and report what the performer
  reported: outcome, changed paths, checks, evidence, limitations and open questions,
  with a link to the result. Do not compare it with criteria of Main's own, review the
  implementation, rerun checks or revise the task on Main's initiative.
- Failed, cancelled and needs-human-decision outcomes are reported as recorded. Relay a
  performer's question to the Human exactly as asked; send a revision only when the Human
  asks for one, carrying the Human's words.
