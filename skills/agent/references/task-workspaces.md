# Captured task Work Units

- Entry and inherited scope: [parent reference](task-dispatch.md#task-workspaces).

<a id="task-workspaces"></a>

## 6. Captured task Work Units

### 6.1. Isolation plan and repositories

- Work isolation is the Human's toggle, captured on the Main run as `workIsolation`. Off keeps the
  shared checkout. On (runtime advertising `workIsolation`), Main supplies `loop.py start
  --workspace-file FILE` for every brief or task: `code` for changes, `read-only` for research
  and questions; `shared` and a missing plan are rejected. Loops inherit the toggle.
- Store the input in the Main run directory. A code plan contains `mode: code` and
  `repositories`: exact `path`, optional `targetBranch`, and nonempty `checks` arrays of executable
  argv arrays from project rules. Derive repositories from the brief's target paths; nested
  repositories need separate tasks. Under isolation an omitted target is the current branch.
- Select only repositories owned by the task. Use the selected Work Unit's captured target when
  present, otherwise inspect the actual repository default branch. Missing repository/semantic
  decisions require clarification; do not guess targets or select every repository.
- Ordered task lists may instead carry each task's `workspace` plan. The accepted private list
  retains it, and each task acquires its own space before dispatch. Explicit `shared` and
  `read-only` modes have no repositories or automatic Git operations.

### 6.2. Workspace preparation and reuse

- The runtime prepares repository-specific branches under the project's managed `worktrees/`,
  relocates Work/Verification CWD and workspace-write roots, and retains original projectRoot,
  session/run/receipt identity. Source dirty/untracked changes remain excluded and visible.
- Revisions and recovery reuse the accepted task workspace. A duplicate code-task start with
  the same Agent/request/options returns the accepted loop; different options are rejected.
  Never retrofit an accepted loop, ignore an isolation prohibition, or isolate conversation,
  read-only research, standalone Verification or planning-only work.

### 6.3. Integration and ownership waits

- Work and Verification never commit. After Work's actual own checks and the requested
  Verification pass or recorded Human skip, runtime commits receipt-bound changes and prepares
  a checked ordinary two-parent target merge. Integration locks serialize each repository.
  Latest-target checks precede the target update; external updates require rechecking.
- An active competing checkout owner or integration lock keeps the loop `active` in
  `integrating`, with `integrationWait` evidence. The driver retries the same completed
  Work and receipt, without re-dispatch. New lifecycle-versioned loops preserve this wait
  across restarts without an arbitrary observation limit; historical loops keep their captured budget.
  Only the exact accepted parent Main is
  exempt on the target; another Main, queued runs and uncertain process ownership block.
  Expired runs are ignored only with positive empty containment or dead identity evidence.
  Historical busy stops can be reconciled
  in their original loop. Project bindings, provider failures and Human decisions remain enforced.

### 6.4. Conflict repair, preservation and cleanup

- Conflicts remain isolated. Runtime sends exact files/base/target and Git-stage instructions
  to the same Work session. Work stages justified resolutions and rechecks without committing.
  Requested Verification runs again. Without isolation, revision limits and unchanged conflict
  stages stop for concrete Human decisions. Never force ours/theirs, rewrite unrelated files or weaken tests.
- Under isolation conflicts never wait for a Human. Unchanged stages, the revision limit, a dirty
  target or another unmergeable outcome preserve branches and paths. New loops report
  `runtime-error` and `completion.integration=preserved|partial`; historical
  `completed/integration_preserved` records remain unchanged. Failed integration checks
  send their exact evidence back to Work for repair; unchanged failure evidence is preserved
  instead of repeatedly spending model tokens on the same repair.
- Failure, cancellation, dirty/active targets and failed checks preserve Work Units without
  reporting integration complete. Multi-repository outcomes are partial and resumable, not atomic.
  Cleanup retains unpreserved/ignored files and active runs; it removes only proven merged units.
- Inspect `taskWorkspaces` in loop status/progress for paths, branches, base/result/merge commits,
  check evidence, conflict/error and cleanup state. Chat/run/receipt history remains accessible.
  Supply exact integration commits for rollback; execute no revert, push, deploy or history rewrite.
