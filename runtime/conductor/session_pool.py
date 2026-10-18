"""Bounded operating sessions; archived identities and immutable run history are retained.

Admission is serialized with domain edits. Waiting runs own no native session slot and
can be cancelled normally. Lowering a limit never evicts an active/decision session.
"""
from __future__ import annotations

import copy
from pathlib import Path

from conductor import domains
from storage.errors import ContractError
from storage.files import atomic_write_json, file_lock, safe_read_json, update_json

DEFAULT_LIMIT = 5


def limit(domain):
    value = domain.get("maxSessions", DEFAULT_LIMIT)
    if type(value) is not int or not 1 <= value <= 9007199254740991:
        raise ContractError("domain_capacity_invalid", "Maximum operating sessions must be a positive safe integer")
    return value


def observe(root, document, domain_id=None):
    entries = {}
    for agent, assignment in document["assignments"].items():
        if domain_id is not None and assignment.get("domainId") != domain_id:
            continue
        if agent in document.get("removedWorkers", {}):
            continue
        directory = Path(root) / "agents" / agent
        if not (directory / "session.json").exists():
            continue
        try:
            session = safe_read_json(directory / "session.json")
            if session.get("role") == "main":
                continue
            runs = [safe_read_json(path) for path in directory.glob("runs/*/state.json")]
            latest = max(runs, key=lambda r: (r.get("acceptedAt", ""), r.get("runId", "")), default={})
            busy = any(r.get("status") in {"starting", "running", "cancelling"}
                       or r.get("status") in {"accepted", "queued"} and r.get("domainAdmission", {}).get("status") == "admitted"
                       for r in runs) or latest.get("status") == "needs-human-decision"
            entries[agent] = {"domainId": assignment["domainId"], "busy": busy, "runs": runs,
                              "recent": latest.get("acceptedAt") or session.get("updatedAt") or session.get("createdAt") or ""}
        except (ContractError, OSError, ValueError):
            # An unreadable owner is never assumed idle and silently recycled.
            entries[agent] = {"domainId": assignment["domainId"], "busy": True, "runs": [], "recent": ""}
    return entries


def operating(document, domain, entries):
    members = [a for a, e in entries.items() if e["domainId"] == domain["id"]]
    busy = sorted(a for a in members if entries[a]["busy"])
    saved = document.get("sessionPools", {}).get(domain["id"])
    candidates = members if saved is None else [a for a in saved if a in members]
    idle = sorted((a for a in candidates if a not in busy), key=lambda a: (entries[a]["recent"], a), reverse=True)
    return busy + idle[:max(0, limit(domain) - len(busy))]


def public_document(root, document):
    result = copy.deepcopy(document)
    entries = observe(root, document)
    for domain in result["domains"]:
        domain["maxSessions"] = limit(domain)
        domain["operatingAgentIds"] = operating(document, domain, entries)
    result.pop("sessionPools", None)
    return result


def admit(root, state_path):
    """Atomically reserve capacity before launching a provider; retrying is idempotent."""
    root, state_path = Path(root), Path(state_path)
    if safe_read_json(state_path).get("role") == "main":
        return True
    with file_lock(root / domains.LOCK):
        state = safe_read_json(state_path)
        document = domains.read(root)
        if state["agentId"] in document.get("removedWorkers", {}):
            raise ContractError("worker_removed", "This performer was removed from the operating roster")
        assignment = document["assignments"].get(state["agentId"], {})
        domain = next((d for d in document["domains"] if d["id"] == assignment.get("domainId")), None)
        if domain is None:
            return True  # Legacy unplaced sessions have no invented domain or limit.
        if state.get("domainAdmission", {}).get("status") == "admitted":
            return True
        entries = observe(root, document, domain["id"])
        busy = {a for a, e in entries.items() if e["domainId"] == domain["id"] and e["busy"]}
        waiting = sorted((r.get("acceptedAt", ""), r["runId"]) for e in entries.values() if e["domainId"] == domain["id"]
                         for r in e["runs"] if r.get("status") in {"accepted", "queued"}
                         and r.get("domainAdmission", {}).get("status") != "admitted")
        position = next((i for i, item in enumerate(waiting) if item[1] == state["runId"]), 0)
        allowed = position < max(0, limit(domain) - len(busy))
        admission = {"domainId": domain["id"], "status": "admitted" if allowed else "waiting", "maxSessions": limit(domain)}
        if allowed:
            members = operating(document, domain, entries)
            if state["agentId"] not in members:
                while len(members) >= limit(domain):
                    victim = next((a for a in reversed(members) if a not in busy), None)
                    if victim is None:
                        return False
                    members.remove(victim)
                members.append(state["agentId"])
            document.setdefault("sessionPools", {})[domain["id"]] = members
            # Internal admission does not invalidate a Human settings edit's revision.
            atomic_write_json(root / domains.FILE, document)
        if state.get("domainAdmission") != admission:
            update_json(state_path, state_path.parent / ".state.lock", lambda value: value.update(domainAdmission=admission))
        return allowed
