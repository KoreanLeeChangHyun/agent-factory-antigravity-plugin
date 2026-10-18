"""Per-request execution routes; missing historical values retain the fixed graph."""
from storage.errors import ContractError

TASK_MODES = ("orchestrate", "direct", "work", "plan", "verification", "plan-work", "work-verification", "plan-work-verification")
LEGACY_MODE = "work-verification"
# Work profile Main chose. It selects no model or agent: work (Expert) and workLight (Worker) are labels only;
# explore (Explorer) and scribe (Scribe) also narrow the run's tools below its authorized permissions.
WORK_PROFILES = ("work", "workLight", "explore", "scribe")
RESTRICTED_PROFILES = ("explore", "scribe")
# What orchestrator Main does with a stopped loop's `failureClass`. Guidance only: the runtime never re-dispatches Work.
FAILURE_CLASS_ACTIONS = ("A stopped loop reports failureClass; act on it: contract - the runtime's automatic receipt recovery already ran, so report a run that still ended failed; "
                         "transient - run loop.py reconcile, read the status once more, then decide; environment - stop and report the cause to the Human; "
                         "human - pass the decision to the Human; provider - report the provider's message and do not dispatch again unless the Human asks; "
                         "quota - the provider's usage limit ran out: unless the loop already records a quota handoff, continue the same task on another "
                         "provider with loop.py handoff --actor main --trigger quota (the same role's model there) and tell the Human in one line. ")

# Scribe completion and lesson consolidation: requested Documents complete without a separate review gate.
# Main owns the match between the Human's request and the delivered result (Human decision 2026-10-18); this is not
# Verification. Agent orchestration.md#result-alignment is the full rule.
RESULT_ALIGNMENT = ("Before reporting completed Work, compare the brief's Done with evidence you can read (result and receipt, "
                    "changed paths in read-only Git, named files and records, cited captures and logs). Do not review implementation "
                    "or rerun checks. On a gap, revise the same task with the exact gap (loop.py revise) and tell the Human in one line; "
                    "after two such revisions or for a Human-owned choice, report the gap with its evidence. Report the evidence you checked. ")
SCRIBE_REVIEW = ("With Work isolation on give scribe the read-only workspace plan (the shared checkout), never a code plan. "
                 "A completed scribe loop is complete: report its result and changed paths directly, without asking the Human to accept, revise or discard them; "
                 "handle later changes as ordinary follow-up requests. Keep intentional drafts and unresolved choices as the Document states them. "
                 "Main commits the files through commit.py only with actual commit authority; reverting requires separate explicit consent. "
                 "To turn lessons into Skill drafts, dispatch scribe to group recurring docs/lessons-learned records and prepare rule candidates with lessons.py candidate, citing the Human's request as authority; "
                 "publishing a candidate needs the Human's approval of that draft. ")


def validate_mode(mode):
    if mode not in TASK_MODES:
        raise ContractError("task_mode_invalid", "Unknown task mode")
    return mode


def route_instruction(mode, role):
    validate_mode(mode)
    if role != "main":
        return ""
    routes = {
        "orchestrate": ("Orchestrator mode. Handle conversation, planning, Interview, requirement shaping and routing directly as Main. "
                        "Project implementation and broader research are delegated. Main may directly confirm a bounded fact or link at a location it already knows (Human-named, a performer's reported evidence or already opened in this conversation) when one look answers; when the location is unknown or the look needs further searching, delegate the lookup to explore or workLight on a light model with evidence (paths, lines, record IDs) to spot-check. Classify by this one-look test, never time/size/file limits. A single-fact web lookup is one look when one search or one read of a known page answers it; answer it with its source. A comparison, several facts or an investigation is research. The brief is the only handoff to a performer: put only what the performer needs in it and keep allocation reasons (profile, model, session) and Main's own preparation errors in this run's records. Delegate with a brief, not a long-term work contract: write one request file in this run's directory starting with a `Title:` line (a few words in the Human's language, about 20 characters: a noun phrase naming the work, never the instruction itself, e.g. `Title: 도메인 목록 상태 점 색 정리`; it becomes the task title shown to the Human) followed by exactly four English headings: Goal (one or two items), Scope (two English subheadings `### Do` for target files, research topic and required actions and `### Do not` for prohibited actions, e.g. no commits), Done (what must be true when finished, including task-specific deliverables) and References (the Human's source message ID/time, related files, records, prior runs and source links). Write every section body as short bulleted or numbered items, one point each; in Korean end items in nominal form (e.g. `커밋 금지`, `지정 파일 1개 생성`), never full polite sentences such as `~해 주세요`. Write no Report section; the runtime result form already asks for the result, changed paths and sources. Re-run or new execution: when the Human corrects or adds to performed work, Main asks whether the original Done still holds. If it does (the result fell short, or a fix or missing part within the same Done), it is a re-run of the same task: use loop.py steer while its run is active or loop.py revise after it ended, keeping the performer and session. If Done must change (a new goal, another target, or new work on top of a finished result), it is a new execution with a new brief whose References name the earlier run. Right after dispatch Main tells the Human in one line which it is (re-run with its round number, or new execution) and why. The Human talks only to Main; an explicit Human choice to start fresh or keep fixing overrides Main's judgment. Then run "
                        "`python3 <plugin-root>/scripts/loop.py start --project-root PROJECT --task-mode work --work-agent UNIQUE_ID --request-file BRIEF` plus the Work profile flags. Every worker belongs to a real work-area domain: before a new worker's first start run `python3 <plugin-root>/scripts/domains.py link --project-root PROJECT --actor ai --source RUN_ID --agent UNIQUE_ID --name DOMAIN`, reusing a name from `domains.py list` for the same area (never a catch-all such as 미분류 or 기타); loop start refuses a worker without a domain. A read brief needs no task-list JSON, announce-tasks, task-flow block or long-term contract; for assigned Document writes use the existing --task-list-file/--task-id binding with exact documentPaths or the accepted contract requiredFileOperations; the runtime derives the single task shown in the panel. Allocation fields, domains and model recommendation (allocation taskType with the supplied modelCatalog as --model-catalog-file) follow the Agent task-allocation guide. "
                        "Choose the profile: explore for source reading, web research and assigned evidence/analysis Documents; scribe for Document research/source checking, writing, integration and shortening confined to the project's docs/ (Documents, records, lessons); workLight for other bounded, already-decided changes; work for multi-file, design or unknown-cause changes. Code changes that also need document updates stay with workLight or work; after such a run, dispatch scribe only when its reported changes affect documents. Pass --work-profile naming that choice, together with the profile's exact model ID and effort as --work-model/--work-reasoning-effort (explore and scribe use the workLight settings unless their own are supplied), and retry a failed workLight or scribe attempt once with the work profile (--work-profile work) only when its failureClass is contract or absent; a failed explore run is reported, not retried with write access. "
                        "explore writes only exact task-bound research/evidence Documents and own run records, with web access; scribe uses public web search/read for Documents and writes only inside docs/. Scribe's web access grants no code/configuration writes, external writes/publishing, sensitive-data transmission, dispatch or commits; it never widens the selected execution policy. Skills outside docs/ remain outside its write scope. Report research completion separately from any pending drafting or integration; a research result does not complete a follow-up role's work. work and workLight are labels that select no model or authority. Never pass a profile word such as light or heavy as a model, and without configured profile models omit --work-model but keep --work-profile. "
                        + SCRIBE_REVIEW +
                        "Start separate Verification only when the Human explicitly requests it (--task-mode work-verification with --verification-agent). After acceptance, finish this turn with the accepted IDs without polling the child, and keep Main Goal disabled for delegated routes; a dispatch acknowledgement is not completion. On the completion notification, acknowledge the exact result/receipt. " + RESULT_ALIGNMENT + "Report separate Verification as not requested unless it ran. "
                        + FAILURE_CLASS_ACTIONS +
                        "Control-plane records and ordinary commits follow the Main prompt's Human conversation and Git integration sections; neither grants code editing. Read with single read-only shell commands and run each Agent Factory script separately. Explorer owns its assigned research package; scribe integrates shared canonical Documents. Assign one writer per shared file and use one owner or managed CLI for summaries/catalogs. The long-term contract procedure remains Human-selected."),
        "direct": ("Single-session mode (the composer's Performer selection). Continue the ordinary conversation in this session; "
                   "messages are turns, not task assignments. A greeting or a performer/session test needs only a brief acknowledgement. "
                   "Do not ask for a task assignment, performer profile or a switch to conductor mode to answer it. "
                   "Do not introduce internal roles, routing or delegation unless the Human asks about them. "
                   "When this message explicitly requests work, perform the bounded task directly as Main, including appropriate own checks. "
                   "Do not dispatch Work or Verification for this task."),
        "plan": "Dispatch role work using exec.py submit --role work --task-mode plan. The runtime uses actual Codex Plan collaboration mode and stops after planning. Return that plan without implementation, verification, or an automatic execution transition. Do not send literal /plan text as a substitute.",
        "verification": "Resolve the inspection target from explicit input first, otherwise prior completed work in this current chat. If neither supplies an unambiguous target, ask the Human for the target; never invent Work evidence. Dispatch a managed Verification agent using exec.py submit --role verification --task-mode verification with a bounded request identifying the exact target and authorized checks. Do not pass --verified-work-run-id or --receipt-request-hash: standalone receipts bind their own target request and cannot satisfy a Work loop. Report its findings without repair or a Work dispatch.",
        "work": "Delegate bounded implementation to Work using exec.py or loop.py start --task-mode work. Work uses native Goal to finish the bounded task and necessary own checks. After completion, acknowledge the exact result/receipt. " + RESULT_ALIGNMENT + "Do not start separate Verification. Report separate Verification as not requested, never pass or Human skip.",
        "plan-work": "Use loop.py start --task-mode plan-work. The runtime runs actual Codex Plan collaboration mode then default execution mode in the SAME Work session. Do not create a planning Agent, manually request transition clicks, or replace Plan mode with prose. Work uses native Goal to finish the bounded task and necessary own checks. After completion, acknowledge the exact result/receipt. " + RESULT_ALIGNMENT + "Do not start separate Verification. Report separate Verification as not requested, never pass or Human skip.",
        "work-verification": "Use loop.py start --task-mode work-verification. Work then separate Verification. On fail, reuse the same Work and Verification sessions until pass, an explicitly evidenced Human skip, or the loop's revision limit, where the Human decides whether to extend or close.",
        "plan-work-verification": "Use loop.py start --task-mode plan-work-verification. The runtime runs actual Codex Plan collaboration mode then default execution mode in the SAME Work session, then separate Verification. Do not create a planning Agent, manually request transition clicks, or replace Plan mode with prose. Reuse Work and Verification sessions on failure.",
    }
    return (f"\nCaptured task mode: {mode}. This applies to this request; later selections cannot change it.\n"
            + routes[mode] + "\nConversation always remains direct Main: answer questions, consultation, discussion, planning and unclear messages without editing files, running changes or delegating changes. Mode selection grants no Human approval or permission expansion. Apply the independent approval policy.\n")


def work_goal_options(options, request_text):
    """Bind Goal to this Work request, leaving plan-only read-only and finite."""
    options = dict(options)
    if options.get("taskMode") == "plan":
        if options.get("goalMode") is True:
            raise ContractError("goal_role_invalid", "Plan-only cannot execute a Goal")
        options["goalMode"] = False
        return options
    if options.get("goalMode") is False:
        raise ContractError("goal_required", "Work execution requires native Goal support")
    options["goalMode"] = True
    options.setdefault("goalObjective", request_text if len(request_text) <= 4000 else
                       "Complete this run's bounded request supplied in the developer instructions, "
                       "including necessary own checks and the exact result/receipt contract. "
                       "Repair in-scope implementation and check failures and rerun affected checks until they pass. "
                       "Preserve progress and stop only for cancellation, an unavailable external prerequisite, "
                       "exhausted provider limits or a required unresolved Human decision.")
    return options
