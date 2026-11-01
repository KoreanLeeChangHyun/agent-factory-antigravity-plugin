"""Team rooms: one per domain, one project room for the conductors, and session rooms from before domain labels.

A domain has one conductor (the Main session labeled with it in the domain store) and the performers that conductor
dispatched; their room is the domain room, keyed by the domain, so a conductor's handover to a new session keeps one
conversation. The project room holds only the labeled conductors and carries project-wide coordination in fixed
forms (Human decision 2026-10-29): work claims, whose overlaps the runtime reports at once; change notices, given in
full to the conductors whose claims they touch; a status board read from the records; and boundary signals, such as
two conductor sessions working in one domain at the same time, which tell the common-domain conductor to research
and propose a split or merge for the Human to decide. A Main session without a domain label keeps the session room
named after it, as before. Room traffic is data from other sessions: it grants no approval or authority.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from conductor import domains
from storage import team_messages as messages
from storage.errors import ContractError
from storage.files import AGENT_ID, atomic_write_json, ensure_directory, find_project_anchor, reject_symlink, safe_read_json
from system.containment import now

PROJECT = "project"
DOMAIN_ROOM = re.compile(r"domain-[0-9a-f]{12}\Z")
ROOM_LIMIT = 30
# The room list shows the start of each room's newest entry.
ROOM_PREVIEW_CHARS = 160
# Project room entries in fixed forms; posts and direct messages are free text.
CLAIM, RELEASE, CHANGE, CONFLICT, SIGNAL = "claim", "release", "change", "conflict", "signal"
DELIVERY_LABEL = {CLAIM: "work claim", CHANGE: "change notice", CONFLICT: "claim conflict", SIGNAL: "domain boundary signal"}


def runtime_of(agents_root: Path) -> Path:
    return Path(agents_root).parent


def document(runtime_root: Path) -> dict[str, Any] | None:
    try:
        return domains.read(runtime_root)
    except (ContractError, OSError, ValueError):
        return None


def labeled_domain(store: dict[str, Any] | None, agent_id: str | None) -> str | None:
    """The domain a Main session is labeled with, following merges; None for an unlabeled session."""
    label = (store or {}).get("conductors", {}).get(agent_id or "")
    found = domains.resolve(store, label.get("domainId")) if isinstance(label, dict) else None
    return found["id"] if found else None


def domain_name(store: dict[str, Any] | None, domain_id: str) -> str:
    found = domains.resolve(store or domains.empty(), domain_id)
    return found["name"] if found else domain_id


def kind(room: str) -> str:
    return "project" if room == PROJECT else "domain" if DOMAIN_ROOM.fullmatch(room or "") else "session"


def _active(state: dict[str, Any] | None) -> bool:
    return bool(state) and state.get("status") not in messages.TERMINAL


def conductors(agents_root: Path, store: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Every recorded Main session carrying a domain label, with its domain and whether it is working now."""
    store = document(runtime_of(agents_root)) if store is None else store
    listed = []
    for session in sorted((store or {}).get("conductors", {})):
        domain_id = labeled_domain(store, session)
        if not domain_id or not messages.agent_exists(agents_root, session):
            continue
        state = messages.latest_state(agents_root / session) or {}
        listed.append({"agentId": session, "domainId": domain_id, "name": domain_name(store, domain_id),
                       "common": domain_id == domains.COMMON_ID, "active": _active(state),
                       "lastActivity": state.get("acceptedAt") or state.get("updatedAt")})
    return listed


def team_of(agents_root: Path, agent_id: str) -> str | None:
    """An agent's room: its conductor's domain room, or the session room of an unlabeled lead."""
    state = messages.latest_state(agents_root / agent_id) or {}
    role = state.get("role") or messages.session_record(agents_root / agent_id).get("role")
    lead = agent_id if role == "main" else state.get("parentAgentId")
    if not lead:
        return None
    return labeled_domain(document(runtime_of(agents_root)), lead) or lead


def lead(agents_root: Path, room: str, store: dict[str, Any] | None = None) -> str | None:
    """Who leads a room: the domain's conductor (the working session first, then the latest), or the session itself."""
    if kind(room) == "session":
        return room if messages.agent_exists(agents_root, room) else None
    if kind(room) == "project":
        return None
    labeled = [item for item in conductors(agents_root, store) if item["domainId"] == room]
    labeled.sort(key=lambda item: (item["active"], str(item["lastActivity"] or "")), reverse=True)
    return labeled[0]["agentId"] if labeled else None


def members(agents_root: Path, room: str) -> list[str]:
    """The agents of a room. Raises room_unknown when no one belongs to it now."""
    store = document(runtime_of(agents_root))
    removed = set((store or {}).get("removedWorkers", {}))
    if kind(room) == "project":
        found = sorted({item["agentId"] for item in conductors(agents_root, store)})
        if not found:
            raise ContractError("room_unknown", "No conductor session carries a domain label, so there is no project room yet")
        return found
    if kind(room) == "session":
        if not messages.agent_exists(agents_root, room) or team_of(agents_root, room) != room:
            raise ContractError("room_unknown", f"`{room}` leads no team room")
        leads = {room}
    else:
        leads = {item["agentId"] for item in conductors(agents_root, store) if item["domainId"] == room}
    found = set(leads)
    if Path(agents_root).is_dir():
        for directory in Path(agents_root).iterdir():
            if not AGENT_ID.fullmatch(directory.name) or directory.is_symlink() or directory.name in removed:
                continue
            if (messages.latest_state(directory) or {}).get("parentAgentId") in leads:
                found.add(directory.name)
    if not found:
        raise ContractError("room_unknown", f"`{room}` has no conductor or performer now")
    return sorted(found)


def peers(agents_root: Path, agent_id: str) -> dict[str, Any]:
    """The agent's room and its members with status; a labeled conductor also sees the other conductors."""
    store = document(runtime_of(agents_root))
    room = team_of(agents_root, agent_id)
    try:
        listed = members(agents_root, room) if room else []
    except ContractError:
        listed = []
    leader = lead(agents_root, room, store) if room else None
    if agent_id not in listed:
        listed.append(agent_id)
    result = {"agentId": agent_id, "lead": leader, "room": room, "roomKind": kind(room) if room else None,
              "members": [_member(agents_root, name, leader, agent_id) for name in listed if (agents_root / name).is_dir()]}
    if labeled_domain(store, agent_id):
        result["conductors"] = [item for item in conductors(agents_root, store) if item["agentId"] != agent_id]
    return result


def _member(agents_root: Path, name: str, leader: str | None, caller: str) -> dict[str, Any]:
    state = messages.latest_state(agents_root / name) or {}
    details = messages.session_record(agents_root / name)
    return {"agentId": name, "role": details.get("role"), "provider": details.get("provider"), "model": details.get("model"),
            "workProfile": state.get("workProfile"), "lead": name == leader, "self": name == caller,
            "status": "running" if _active(state) else "idle", "lastRunId": state.get("runId"),
            "task": messages.task_title(state), "queuedMessages": messages.queued_count(runtime_of(agents_root), name)}


def profile(agents_root: Path, agent_id: str) -> dict[str, Any] | None:
    """Who an agent is, for showing a conversation: its role, work profile, provider and model."""
    if not AGENT_ID.fullmatch(agent_id or "") or not (agents_root / agent_id).is_dir():
        return None
    details, state = messages.session_record(agents_root / agent_id), messages.latest_state(agents_root / agent_id) or {}
    return {"role": details.get("role") or state.get("role"), "workProfile": state.get("workProfile"),
            "provider": details.get("provider") or state.get("provider"), "model": details.get("model") or state.get("model")}


# -- storage -------------------------------------------------------------------------------------

def directory(runtime_root: Path, room: str) -> Path:
    if not AGENT_ID.fullmatch(room or ""):
        raise ContractError("room_invalid", "A room is named project, by its domain id, or by its lead agent id")
    return Path(runtime_root) / "rooms" / room


def append(runtime_root: Path, room: str, entry: dict[str, Any]) -> None:
    folder = directory(runtime_root, room)
    ensure_directory(folder, find_project_anchor(folder))
    path = folder / f"{entry['id']}.json"
    if not path.exists():
        atomic_write_json(path, entry)


def _entry(path: Path) -> dict[str, Any] | None:
    """One room entry; an unreadable or malformed file is None so one bad file never hides the rest of the room."""
    try:
        value = safe_read_json(path)
    except (ContractError, OSError, ValueError):
        return None
    return value if isinstance(value, dict) and isinstance(value.get("text"), str) and isinstance(value.get("from"), dict) else None


def entry_paths(folder: Path) -> list[Path]:
    return [path for path in sorted(folder.glob("msg-*.json")) if messages.MESSAGE_ID.fullmatch(path.stem) and not path.is_symlink()]


def folders(runtime_root: Path, room: str, store: dict[str, Any] | None = None) -> list[Path]:
    """Where a room's entries are kept: its own folder and, for a domain room, the session rooms its conductor
    sessions kept before they carried the domain label, so the domain keeps one history."""
    found = [directory(runtime_root, room)]
    if kind(room) == "domain":
        store = document(runtime_root) if store is None else store
        found += [directory(runtime_root, session) for session in sorted((store or {}).get("conductors", {}))
                  if labeled_domain(store, session) == room and AGENT_ID.fullmatch(session)]
    present = []
    for folder in found:
        if folder.is_dir():
            reject_symlink(folder)
            present.append(folder)
    return present


def read(runtime_root: Path, room: str, limit: int | None = ROOM_LIMIT) -> tuple[list[dict[str, Any]], int]:
    """The newest readable entries, oldest first, and how many of the selected files could not be read."""
    # Entry ids begin with their UTC time, so file names order entries from several folders by time.
    paths = sorted((path for folder in folders(runtime_root, room) for path in entry_paths(folder)), key=lambda path: path.name)
    values = [_entry(path) for path in (paths[-limit:] if limit else paths)]
    return [value for value in values if value is not None], sum(value is None for value in values)


def listing(runtime_root: Path) -> list[dict[str, Any]]:
    """Every room with entries: the project room first, then the newest activity first."""
    base = Path(runtime_root) / "rooms"
    if not base.is_dir():
        return []
    reject_symlink(base)
    store = document(runtime_root)
    rooms, names = [], set()
    for folder in sorted(base.iterdir()):
        if not AGENT_ID.fullmatch(folder.name) or not folder.is_dir() or folder.is_symlink():
            continue
        # A session room whose conductor now carries a domain label is listed as part of that domain's room.
        names.add(labeled_domain(store, folder.name) if kind(folder.name) == "session" and labeled_domain(store, folder.name) else folder.name)
    for name in sorted(names):
        paths = sorted((path for folder in folders(runtime_root, name, store) for path in entry_paths(folder)), key=lambda path: path.name)
        if not paths:
            continue
        folder = directory(runtime_root, name)
        # The preview comes from the newest entry that can be read.
        last = next((value for value in map(_entry, reversed(paths)) if value is not None), None) or {}
        sender = last.get("from") or {}
        room = {"room": folder.name, "kind": kind(folder.name), "entries": len(paths), "lastAt": last.get("createdAt"),
                "lastFrom": sender.get("agentId") or sender.get("actor"), "lastKind": last.get("kind"),
                "lastText": " ".join(str(last.get("text") or "").split())[:ROOM_PREVIEW_CHARS]}
        if room["kind"] == "domain":
            room["name"] = domain_name(store, folder.name)
        # A conductor is shown by its domain rather than its session id.
        if labeled_domain(store, room["lastFrom"]):
            room["lastFromName"] = domain_name(store, labeled_domain(store, room["lastFrom"]))
        rooms.append(room)
    rooms.sort(key=lambda value: str(value.get("lastAt") or ""), reverse=True)
    return sorted(rooms, key=lambda value: value["kind"] != "project")


# -- delivery ------------------------------------------------------------------------------------

def delivery_text(entry: dict[str, Any], store: dict[str, Any] | None = None) -> str:
    """What a member's copy says: the text, with the claim's or change's domain and paths."""
    form = entry.get("kind")
    if form not in DELIVERY_LABEL:
        return entry["text"]
    head = DELIVERY_LABEL[form].capitalize()
    if entry.get("domainId"):
        head += f" from the {domain_name(store, entry['domainId'])} domain"
    paths = f"\nPaths: {', '.join(entry['paths'])}" if entry.get("paths") else ""
    return f"{head}:\n{entry['text']}{paths}"


def deliver(runtime_root: Path, agents_root: Path, room: str, entry: dict[str, Any], recipients, mentioned=(),
            store: dict[str, Any] | None = None) -> dict[str, Any]:
    """Give each recipient a copy of a room entry: the full text for those it concerns, a summary for the rest."""
    delivered, skipped = [], []
    text = delivery_text(entry, store)
    sender = (entry.get("from") or {}).get("agentId")
    for member in sorted(set(recipients)):
        if member == sender:
            continue
        copy = {**messages.record(entry["from"], member, text, None), "room": room, "roomKind": kind(room),
                "roomPost": entry["id"], "entryKind": entry.get("kind"), "mentioned": member in mentioned}
        try:
            result = messages.queue(runtime_root, agents_root, copy)
        except ContractError as error:
            skipped.append({"agentId": member, "code": error.code})
            continue
        delivered.append(member)
        if copy["mentioned"] and not result.get("duplicate") and messages.idle(agents_root, member):
            messages.notify_lead(runtime_root, agents_root, member, [copy], "it was named in a room after it finished.")
    return {"delivered": delivered, "skipped": skipped}


def post(runtime_root: Path, agents_root: Path, sender: dict[str, Any], room: str, text: str,
         post_id: str | None = None) -> dict[str, Any]:
    """Record a free post and give every other member a copy; members it mentions get the full text."""
    listed = members(agents_root, room)
    if sender.get("agentId") and sender["agentId"] not in listed:
        raise ContractError("room_denied", f"`{sender['agentId']}` is not a member of the `{room}` room")
    mentions = sorted({name for name in messages.MENTION.findall(text) if name in listed})
    entry = {"schemaVersion": messages.SCHEMA_VERSION, "kind": "room-post", "id": post_id or messages.new_id("msg"),
             "room": room, "from": sender, "text": text, "mentions": mentions, "createdAt": now()}
    append(runtime_root, room, entry)
    return {"id": entry["id"], "room": room, "mentions": mentions,
            **deliver(runtime_root, agents_root, room, entry, listed, mentions)}


def share_direct(runtime_root: Path, agents_root: Path, message: dict[str, Any]) -> None:
    """Keep a direct message in a room. Between two conductors it belongs to the project room; otherwise to the
    recipient's room, whose lead receives a summary copy."""
    if message.get("room") or message.get("from") == messages.RUNTIME_SENDER:
        return
    store = document(runtime_root)
    sender = (message.get("from") or {}).get("agentId")
    if sender and labeled_domain(store, sender) and labeled_domain(store, message["to"]):
        room = PROJECT
    else:
        room = team_of(agents_root, message["to"])
    if not room:
        return
    append(runtime_root, room, {"schemaVersion": messages.SCHEMA_VERSION, "kind": "room-direct", "id": message["id"],
                                "room": room, "from": message["from"], "to": message["to"], "text": message["text"],
                                "replyTo": message.get("replyTo"), "createdAt": message.get("createdAt")})
    leader = lead(agents_root, room, store)
    if room == PROJECT or not leader or leader in (sender, message["to"]):
        return
    copy = {**messages.record(message["from"], leader, message["text"], message.get("replyTo")), "room": room, "cc": True,
            "ccTo": message["to"]}
    try:
        messages.queue(runtime_root, agents_root, copy)
    except ContractError:
        pass  # The full text stays in the room; a full lead queue only loses the summary copy.


# -- project room: claims, change notices, signals and the status board ----------------------------

def paths_of(values) -> list[str]:
    """Project-relative file or directory paths, normalized; absolute paths and `..` are refused."""
    result = []
    for raw in values or []:
        value = raw.strip().replace("\\", "/") if isinstance(raw, str) else ""
        while value.startswith("./"):
            value = value[2:]
        value = value.rstrip("/")
        parts = value.split("/")
        if (not value or len(value) > 500 or "\0" in value or value.startswith("/") or re.match(r"[A-Za-z]:", value)
                or any(part in ("", ".", "..") for part in parts)):
            raise ContractError("claim_path_invalid", f"{raw!r}: name a file or directory relative to the project root")
        result.append(value)
    if not result:
        raise ContractError("claim_path_required", "Name at least one file or directory path")
    return sorted(set(result))


def overlaps(first: str, second: str) -> bool:
    return first == second or first.startswith(second + "/") or second.startswith(first + "/")


def conductor_domain(agents_root: Path, sender: dict[str, Any], store: dict[str, Any] | None = None) -> str:
    domain_id = labeled_domain(store if store is not None else document(runtime_of(agents_root)), sender.get("agentId"))
    if sender.get("role") != "main" or not domain_id:
        raise ContractError("conductor_domain_required", "Only a conductor session labeled with a domain uses the project "
                            "room; label this session with domains.py label-conductor first")
    return domain_id


def claim_domain(store: dict[str, Any] | None, item: dict[str, Any]) -> str | None:
    """The domain that holds a claim now, following merges; None when that domain is gone."""
    found = domains.resolve(store or domains.empty(), item.get("domainId"))
    return found["id"] if found else None


def active_claims(entries: list[dict[str, Any]], store: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Claims not released, whose domain still exists, each with the domain that holds it now."""
    released = {claim for item in entries if item.get("kind") == RELEASE for claim in item.get("claimIds") or []}
    return [{**item, "domainId": claim_domain(store, item)} for item in entries
            if item.get("kind") == CLAIM and item["id"] not in released and claim_domain(store, item)]


def _common_conductors(agents_root: Path, store) -> set[str]:
    return {item["agentId"] for item in conductors(agents_root, store) if item["common"]}


def claim(runtime_root: Path, agents_root: Path, sender: dict[str, Any], paths, intent: str,
          claim_id: str | None = None) -> dict[str, Any]:
    """Record a conductor's work claim; an overlap with another domain's claim is reported to both at once."""
    store = document(runtime_root)
    domain_id = conductor_domain(agents_root, sender, store)
    paths = paths_of(paths)
    entries, _ = read(runtime_root, PROJECT, None)
    others = [item for item in active_claims(entries, store) if item["domainId"] != domain_id
              and any(overlaps(mine, theirs) for mine in paths for theirs in item.get("paths") or [])]
    entry = {"schemaVersion": messages.SCHEMA_VERSION, "kind": CLAIM, "id": claim_id or messages.new_id("msg"), "room": PROJECT,
             "from": sender, "domainId": domain_id, "paths": paths, "text": intent, "createdAt": now()}
    append(runtime_root, PROJECT, entry)
    listed = members(agents_root, PROJECT)
    result = {"id": entry["id"], "room": PROJECT, "domainId": domain_id, "paths": paths,
              **deliver(runtime_root, agents_root, PROJECT, entry, listed, (), store)}
    if others:
        result["conflict"] = _conflict(runtime_root, agents_root, entry, others, entries, store)
    return result


def conflicts_preview(runtime_root: Path, agents_root: Path, sender: dict[str, Any], paths) -> list[dict[str, Any]]:
    """Other domains' active claims a new claim would overlap, read without writing anything."""
    store = document(runtime_root)
    domain_id = conductor_domain(agents_root, sender, store)
    paths = paths_of(paths)
    entries, _ = read(runtime_root, PROJECT, None)
    return [{"claimId": item["id"], "domainId": item["domainId"], "domain": domain_name(store, item["domainId"]),
             "paths": item["paths"], "by": (item.get("from") or {}).get("agentId"), "createdAt": item.get("createdAt")}
            for item in active_claims(entries, store) if item["domainId"] != domain_id
            and any(overlaps(mine, theirs) for mine in paths for theirs in item.get("paths") or [])]


def _conflict(runtime_root, agents_root, entry, others, entries, store) -> dict[str, Any]:
    mine = entry["domainId"]
    theirs = sorted({item["domainId"] for item in others})
    earlier = sum(1 for item in entries if item.get("kind") == CONFLICT and mine in (item.get("domains") or [])
                  and set(theirs) & set(item.get("domains") or []))
    lines = [f"Work claims overlap. The {domain_name(store, mine)} domain (`{entry['from'].get('agentId')}`) claimed "
             f"{', '.join(entry['paths'])} ({entry['id']})."]
    for item in others:
        lines.append(f"- The {domain_name(store, item['domainId'])} domain (`{(item.get('from') or {}).get('agentId')}`) holds "
                     f"{', '.join(item['paths'])} since {item.get('createdAt')} ({item['id']}).")
    lines.append("Agree in the project room who goes first or how to divide the files before editing them. "
                 + (f"These domains have overlapped {earlier} time(s) before; the common-domain conductor researches and "
                    "proposes a boundary change for the user to decide." if earlier else
                    "If such overlaps repeat, the common-domain conductor researches and proposes a boundary change."))
    holders = {(item.get("from") or {}).get("agentId") for item in others}
    named = {entry["from"].get("agentId"), *holders, *_common_conductors(agents_root, store)} - {None}
    conflict = {"schemaVersion": messages.SCHEMA_VERSION, "kind": CONFLICT, "id": messages.new_id("msg"), "room": PROJECT,
                "from": messages.RUNTIME_SENDER, "domains": sorted({mine, *theirs}), "claimIds": [entry["id"], *[item["id"] for item in others]],
                "paths": entry["paths"], "text": "\n".join(lines), "createdAt": now()}
    append(runtime_root, PROJECT, conflict)
    listed = members(agents_root, PROJECT)
    return {"id": conflict["id"], "earlier": earlier, **deliver(runtime_root, agents_root, PROJECT, conflict, listed, named, store)}


def release(runtime_root: Path, agents_root: Path, sender: dict[str, Any], claim_ids=None, everything: bool = False) -> dict[str, Any]:
    """Release claims: a conductor releases its domain's claims; the user may release any claim by id."""
    store = document(runtime_root)
    entries, _ = read(runtime_root, PROJECT, None)
    active = active_claims(entries, store)
    if sender.get("actor") == "human":
        if everything or not claim_ids:
            raise ContractError("claim_release_invalid", "The user releases claims by id")
        chosen = [item for item in active if item["id"] in set(claim_ids)]
        domain_id = None
    else:
        domain_id = conductor_domain(agents_root, sender, store)
        own = [item for item in active if item["domainId"] == domain_id]
        if everything:
            chosen = own
        else:
            if not claim_ids:
                raise ContractError("claim_release_invalid", "Give claim ids or --all")
            foreign = set(claim_ids) - {item["id"] for item in own}
            if foreign & {item["id"] for item in active}:
                raise ContractError("claim_release_denied", "A conductor releases only its own domain's claims")
            chosen = [item for item in own if item["id"] in set(claim_ids)]
    if not chosen:
        return {"released": [], "room": PROJECT}
    entry = {"schemaVersion": messages.SCHEMA_VERSION, "kind": RELEASE, "id": messages.new_id("msg"), "room": PROJECT,
             "from": sender, "domainId": domain_id, "claimIds": [item["id"] for item in chosen],
             "paths": sorted({path for item in chosen for path in item.get("paths") or []}),
             "text": f"Released {len(chosen)} claim(s).", "createdAt": now()}
    append(runtime_root, PROJECT, entry)
    return {"id": entry["id"], "room": PROJECT, "released": entry["claimIds"]}


def change(runtime_root: Path, agents_root: Path, sender: dict[str, Any], paths, text: str,
           change_id: str | None = None) -> dict[str, Any]:
    """Record a finished change other domains may depend on; conductors whose claims it touches get it in full."""
    store = document(runtime_root)
    domain_id = conductor_domain(agents_root, sender, store)
    paths = paths_of(paths)
    entries, _ = read(runtime_root, PROJECT, None)
    touched = {(item.get("from") or {}).get("agentId") for item in active_claims(entries, store)
               if item["domainId"] != domain_id and any(overlaps(mine, theirs) for mine in paths for theirs in item.get("paths") or [])}
    listed = members(agents_root, PROJECT)
    mentions = {name for name in messages.MENTION.findall(text) if name in listed}
    entry = {"schemaVersion": messages.SCHEMA_VERSION, "kind": CHANGE, "id": change_id or messages.new_id("msg"), "room": PROJECT,
             "from": sender, "domainId": domain_id, "paths": paths, "text": text, "mentions": sorted(mentions | (touched - {None})),
             "createdAt": now()}
    append(runtime_root, PROJECT, entry)
    return {"id": entry["id"], "room": PROJECT, "affected": sorted(touched - {None}),
            **deliver(runtime_root, agents_root, PROJECT, entry, listed, entry["mentions"], store)}


def signal_shared_domain(runtime_root: Path, agents_root: Path, session: str) -> dict[str, Any] | None:
    """Two conductor sessions working in one domain at once mean the domain was divided wrongly; say so once.
    A handover, where the earlier session has stopped, is not a signal."""
    store = document(runtime_root)
    domain_id = labeled_domain(store, session)
    if not domain_id:
        return None
    sharing = sorted(item["agentId"] for item in conductors(agents_root, store)
                     if item["domainId"] == domain_id and item["active"] and item["agentId"] != session)
    if not sharing:
        return None
    sessions = sorted({session, *sharing})
    entries, _ = read(runtime_root, PROJECT, None)
    if any(item.get("kind") == SIGNAL and item.get("domainId") == domain_id and item.get("sessions") == sessions for item in entries):
        return None
    name = domain_name(store, domain_id)
    text = (f"Conductor sessions {', '.join(f'`{item}`' for item in sessions)} are working in the {name} domain at the same "
            "time. One domain has one conductor, so this domain was divided wrongly. The common-domain conductor researches "
            "the work each session holds and proposes how to split the domain; the user decides. Until then, agree in the "
            "project room which session continues which work.")
    entry = {"schemaVersion": messages.SCHEMA_VERSION, "kind": SIGNAL, "id": messages.new_id("msg"), "room": PROJECT,
             "from": messages.RUNTIME_SENDER, "domainId": domain_id, "sessions": sessions, "text": text, "createdAt": now()}
    append(runtime_root, PROJECT, entry)
    named = set(sessions) | _common_conductors(agents_root, store)
    return {"id": entry["id"], **deliver(runtime_root, agents_root, PROJECT, entry, members(agents_root, PROJECT), named, store)}


def status(runtime_root: Path, agents_root: Path) -> list[dict[str, Any]]:
    """The status board, read from the records: per domain its conductor, whether it or its performers work, and its claims."""
    store = document(runtime_root)
    entries, _ = read(runtime_root, PROJECT, None)
    claims = active_claims(entries, store)
    board = []
    for domain_id in sorted({item["domainId"] for item in conductors(agents_root, store)}, key=lambda value: (value != domains.COMMON_ID, domain_name(store, value))):
        leader = lead(agents_root, domain_id, store)
        try:
            team = members(agents_root, domain_id)
        except ContractError:
            team = []
        working = [name for name in team if name != leader and _active(messages.latest_state(agents_root / name))]
        state = messages.latest_state(agents_root / leader) if leader else None
        board.append({"domainId": domain_id, "name": domain_name(store, domain_id), "common": domain_id == domains.COMMON_ID,
                      "conductor": leader, "active": _active(state), "lastActivity": (state or {}).get("acceptedAt"),
                      "performers": len([name for name in team if name != leader]), "working": working,
                      "claims": [{"id": item["id"], "paths": item["paths"], "text": item["text"], "createdAt": item.get("createdAt")}
                                 for item in claims if item["domainId"] == domain_id]})
    return board


def board_lines(board: list[dict[str, Any]]) -> list[str]:
    """The status board as short lines for a conductor's turn."""
    lines = []
    for item in board:
        state = "working" if item["active"] else "idle"
        claims = "; ".join(", ".join(claim["paths"]) for claim in item["claims"]) or "none"
        lines.append(f"- {item['name']}{' (common)' if item['common'] else ''}: conductor `{item['conductor']}` {state}, "
                     f"{len(item['working'])}/{item['performers']} performers working, claims: {claims}")
    return lines
