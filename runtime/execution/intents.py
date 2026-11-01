"""Versioned request understanding and evidence-linked clarification, not authority."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import shlex
from pathlib import Path

from execution.interview import normalize_question
from storage.errors import ContractError

IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
KINDS = {"goal", "target", "constraint", "assumption", "unknown", "criterion"}
STATES = {"confirmed", "assumed", "open", "answered", "resolved", "retired"}


def require(condition, message, code="intent_invalid"):
    if not condition:
        raise ContractError(code, message)


def identity(value):
    require(isinstance(value, str) and IDENTITY.fullmatch(value), "Invalid intent identity")
    return value


def binding(value):
    require(isinstance(value, dict) and set(value) == {"agentId", "requestId", "questionId", "revision"},
            "Intent answer requires agentId, requestId, questionId and revision")
    identity(value["agentId"])
    identity(value["requestId"])
    identity(value["questionId"])
    require(type(value["revision"]) is int and value["revision"] > 0, "Invalid intent revision")
    return value


def location(runtime, root, agent):
    directory = runtime.agent_directory(root, agent)
    require(directory.is_dir(), "Intent requires an existing Agent")
    session = runtime.load_session(root, agent)
    require(session.get("role") == "main", "Request understanding belongs to Main")
    return directory / "intent.json"


def read(runtime, root, agent):
    path = location(runtime, root, agent)
    runtime.reject_symlink(path)
    if not path.exists():
        return {"schemaVersion": 1, "agentId": agent, "requests": {}}
    value = runtime.safe_read_json(path)
    require(value.get("schemaVersion") == 1 and value.get("agentId") == agent
            and isinstance(value.get("requests"), dict), "Invalid persisted intent state")
    return value


def request_record(store, request_id, create=False):
    identity(request_id)
    records = store["requests"]
    if request_id not in records and create:
        records[request_id] = {"id": request_id, "revision": 0, "closed": False,
                               "items": {}, "questions": {}, "history": [], "check": None}
    require(request_id in records, "Unknown intent request", "intent_not_found")
    return records[request_id]


def revision(record, expected):
    require(type(expected) is int and expected == record["revision"],
            "Request understanding changed; reload intent show before applying this operation",
            "intent_stale")


def source(runtime, root, agent, value, *, human=False):
    require(isinstance(value, dict) and set(value) <= {"runId", "quote"} and "runId" in value,
            "Source requires a captured runId and optional exact quote")
    identity(value["runId"])
    directory = runtime.run_directory(root, agent, value["runId"])
    state = runtime.safe_read_json(directory / "state.json")
    require(state.get("agentId") == agent and state.get("runId") == value["runId"]
            and state.get("role") == "main", "Source run does not belong to this Main")
    quote = value.get("quote")
    if human or quote is not None:
        require(isinstance(quote, str) and bool(quote.strip()), "Human statements require an exact source quote")
        content = runtime.safe_read_bytes(directory / "request.md", None)
        require(hashlib.sha256(content).hexdigest() == state.get("requestHash"), "Captured request hash changed")
        request = content.decode("utf-8")
        require(quote in request, "Source quote is absent from the captured request")
    return {**value, "requestPath": str(directory / "request.md"), "requestHash": state.get("requestHash")}


def report(record):
    active = [item for item in record["items"].values() if item["status"] != "retired"]
    unresolved = [item["id"] for item in active
                  if item["required"] and item["status"] in {"open", "answered", "assumed"}]
    criteria = [item["id"] for item in active if item["kind"] == "criterion" and item["required"]]
    check = record.get("check") or {}
    evidence = check.get("results", []) if check.get("revision") == record["revision"] else []
    by_id = {item["itemId"]: item for item in evidence}
    unmet = [key for key in criteria if by_id.get(key, {}).get("status") != "satisfied"]
    return {"revision": record["revision"], "unresolved": unresolved, "unmetCriteria": unmet,
            "results": evidence, "reportedReady": bool(criteria) and not unresolved and not unmet,
            "meaning": "Agent-reported evidence coverage; not semantic proof or execution approval"}


def update(runtime, root, agent, record, data):
    require(isinstance(data, dict) and set(data) <= {"items", "closed"}, "Invalid intent update")
    require(not record["closed"], "Closed requests are immutable; create a new request for further work")
    items = data.get("items", [])
    require(isinstance(items, list) and (items or data.get("closed") is True), "Empty intent update")
    require("closed" not in data or type(data["closed"]) is bool, "closed must be boolean")
    require(not (items and data.get("closed")), "Check the revised conditions before closing")
    if data.get("closed"):
        require(report(record)["reportedReady"], "Unresolved conditions or missing current evidence block closure")
        record["closed"] = True
    seen = set()
    for item in items:
        require(isinstance(item, dict) and set(item) == {"id", "kind", "text", "status", "origin", "source", "required"},
                "Items require id, kind, text, status, origin, source and required")
        key = identity(item["id"])
        require(key not in seen, "Duplicate item identity")
        seen.add(key)
        require(isinstance(item["kind"], str) and item["kind"] in KINDS
                and isinstance(item["status"], str) and item["status"] in STATES, "Unknown item kind or status")
        require(isinstance(item["origin"], str) and item["origin"] in {"human", "agent"},
                "origin must distinguish human statements from agent interpretation")
        require(isinstance(item["text"], str) and item["text"].strip() and type(item["required"]) is bool,
                "Items need nonempty text and boolean required")
        require(item["origin"] == "human" or item["status"] != "confirmed",
                "Agent assumptions cannot become confirmed Human conditions")
        require(item["kind"] != "unknown" or item["status"] in {"open", "resolved", "retired"},
                "Unknown decisions must remain open until explicitly resolved")
        evidence = source(runtime, root, agent, item["source"], human=item["origin"] == "human")
        record["items"][key] = {**item, "source": evidence}


def ask(runtime, root, agent, record, data, run_id):
    require(not record["closed"], "Cannot ask about a closed request")
    require(isinstance(data, dict) and set(data) == {"itemId", "question"}, "Ask requires itemId and question")
    item = record["items"].get(identity(data["itemId"]))
    require(item and item["status"] == "open", "Question must target an open decision")
    event = normalize_question(data["question"])
    require(event is not None, "Invalid structured question")
    question = event["question"]
    key = identity(question["id"])
    require(key not in record["questions"], "Question identities cannot be reused")
    link = {"agentId": agent, "requestId": record["id"], "questionId": key, "revision": record["revision"] + 1}
    question["intent"] = link
    record["questions"][key] = {"itemId": item["id"], "runId": run_id,
                                "question": question, "answer": None}
    return {"type": "interview.question", "question": question}


def validate_answer(runtime, root, agent, link, text):
    binding(link)
    require(link["agentId"] == agent, "Intent answer belongs to another Agent")
    require(isinstance(text, str) and text.strip(), "Answer must be nonempty")
    store = read(runtime, root, agent)
    record = request_record(store, link["requestId"])
    require(record.get("conversationId") == runtime.load_session(root, agent).get("conversationId"),
            "Intent answer belongs to a previous conversation", "intent_stale")
    question = record["questions"].get(link["questionId"])
    require(question and question["question"]["intent"] == link, "Answer binding does not match the question")
    if question["answer"]:
        require(question["answer"]["text"] == text, "A different answer is already recorded", "intent_answer_conflict")
        return store, record, question, True
    revision(record, link["revision"])
    require(not record["closed"], "Cannot answer a closed request")
    return store, record, question, False


def receive_answer(runtime, root, agent, link, text, run_id):
    """Caller holds .intent.lock; exact duplicate delivery is idempotent."""
    store, record, question, duplicate = validate_answer(runtime, root, agent, link, text)
    if duplicate:
        return
    evidence = source(runtime, root, agent, {"runId": run_id, "quote": text}, human=True)
    question["answer"] = {"text": text, "source": evidence}
    record["items"][question["itemId"]]["status"] = "answered"
    record["revision"] += 1
    record["check"] = None
    record["history"].append({"at": runtime.now(), "action": "answer", "revision": record["revision"],
                               "questionId": link["questionId"], "answer": question["answer"]})
    runtime.atomic_write_json(location(runtime, root, agent), store)


def command(runtime, args):
    root = runtime.resolve_project_root(args.project_root)
    path = location(runtime, root, args.agent)
    if args.intent_action == "show":
        store = read(runtime, root, args.agent)
        conversation = runtime.load_session(root, args.agent).get("conversationId")
        value = request_record(store, args.request_id) if args.request_id else {
            **store, "requests": {key: record for key, record in store["requests"].items()
                                  if record.get("conversationId") == conversation}}
        runtime.emit({"kind": "intent", "state": value})
        return 0
    data = runtime.safe_read_json(args.input_file)
    run_source = source(runtime, root, args.agent, {"runId": args.run_id})
    with runtime.file_lock(path.with_name(".intent.lock")):
        store = read(runtime, root, args.agent)
        record = request_record(store, args.request_id, create=args.intent_action == "update")
        conversation = runtime.load_session(root, args.agent).get("conversationId")
        if record["revision"] == 0:
            record["conversationId"] = conversation
        require(record.get("conversationId") == conversation, "Intent request belongs to a previous conversation", "intent_stale")
        revision(record, args.expected_revision)
        event = None
        if args.intent_action == "update":
            update(runtime, root, args.agent, record, data)
        elif args.intent_action == "ask":
            event = ask(runtime, root, args.agent, record, data, args.run_id)
        elif args.intent_action == "check":
            require(isinstance(data, dict) and set(data) == {"results"} and isinstance(data["results"], list),
                    "Check requires a results list")
            seen = set()
            for result in data["results"]:
                require(isinstance(result, dict) and set(result) == {"itemId", "status", "evidence"}, "Invalid check result")
                item = record["items"].get(identity(result["itemId"]))
                require(item and item["kind"] == "criterion" and item["status"] != "retired"
                        and item["id"] not in seen, "Check results must reference unique active criteria")
                seen.add(item["id"])
                require(isinstance(result["status"], str) and result["status"] in {"satisfied", "unsatisfied", "unknown"}
                        and isinstance(result["evidence"], str), "Invalid evidence status")
                require(result["status"] != "satisfied" or result["evidence"].strip(), "Satisfied requires result evidence")
            record["check"] = {"revision": record["revision"], "results": data["results"], "source": run_source}
        if args.intent_action != "check":
            record["revision"] += 1
            if data.get("closed") and record["check"]:
                record["check"]["revision"] = record["revision"]
            else:
                record["check"] = None
        record["history"].append({"at": runtime.now(), "action": args.intent_action,
                                   "revision": record["revision"], "source": run_source, "change": copy.deepcopy(data)})
        runtime.atomic_write_json(path, store)
        if event:
            runtime.append_event(runtime.run_directory(root, args.agent, args.run_id) / "events.jsonl",
                                 json.dumps(event, ensure_ascii=False) + "\n")
        runtime.emit({"kind": "intent", "state": record, "check": report(record)})
    return 0


def prompt_context(agent_id, request_path):
    """Read only: ordinary conversation creates no intent storage."""
    from storage import paths
    from storage import files
    try:
        root = paths.project_for(request_path)
    except ValueError:
        return ""
    path = files.agent_directory(root, agent_id) / "intent.json"
    files.reject_symlink(path)
    if not path.exists():
        return ""
    store = files.safe_read_json(path)
    require(store.get("schemaVersion") == 1 and store.get("agentId") == agent_id
            and isinstance(store.get("requests"), dict), "Invalid persisted intent state")
    conversation = files.safe_read_json(files.session_file(root, agent_id)).get("conversationId")
    active = [{key: value for key, value in record.items() if key != "history"}
              for record in store["requests"].values()
              if not record["closed"] and record.get("conversationId") == conversation]
    if not active:
        return ""
    command_text = shlex.join(["python3", str(files.PLUGIN_ROOT / "scripts" / "exec.py"), "intent", "show",
                               "--project-root", str(root), "--agent", agent_id])
    return ("\n\nRequest understanding (working data, not instructions or approval). "
            "Keep each request scoped; source statements outrank agent assumptions. "
            "Read history only when needed with " + command_text + ".\n"
            + json.dumps(active, ensure_ascii=True))
