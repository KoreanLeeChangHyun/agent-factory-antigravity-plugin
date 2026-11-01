"""Messages between Agent Factory agents, provider-neutral and recorded in the project runtime.

An agent run never writes outside its own run directory: providers such as Codex sandbox
every other path. A message sent from inside a run therefore lands in that run's outbox,
and the unsandboxed run worker relays it to the recipient's inbox under the project
runtime. Outside a run (the Human's terminal or the extension) the message is queued
directly. The recipient sees queued messages at its next turn or when it pulls its inbox.

A message is data from another session, never the Human's words: it grants no approval,
permission, configuration change or command authority.
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage.errors import ContractError
from storage.files import (AGENT_ID, atomic_write_json, ensure_directory, file_lock, find_project_anchor,
                           reject_symlink, safe_read_json)
from system.containment import now

SCHEMA_VERSION = 1
PARENT_STATE_ENV = "AGENT_FACTORY_PARENT_STATE"
MESSAGE_ID = re.compile(r"msg-[0-9]{8}T[0-9]{12}Z-[a-f0-9]{8}\Z")
# A message is one turn's input for its recipient. Larger material belongs in a file the message names.
MAX_MESSAGE_CHARS = 100_000
# Undelivered messages one recipient holds; further sends ask the sender to batch or wait, so loops stop.
MAX_QUEUED = 50
TERMINAL = {"completed", "needs-human-decision", "failed", "cancelled", "runtime-error"}
OUTBOX = "outbox"
DONE = "done"
# Notices the runtime itself sends, such as telling a lead that a message waits for an idle agent.
RUNTIME_SENDER = {"actor": "runtime"}
# `@agent-id` in a team room post asks for that member's attention; it receives the full text.
MENTION = re.compile(r"@([A-Za-z0-9][A-Za-z0-9._-]{0,63})")


def new_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def caller(agents_root: Path) -> dict[str, Any] | None:
    """The agent run invoking this process, from the runtime-set parent state; None outside a run."""
    locator = os.environ.get(PARENT_STATE_ENV, "").strip()
    if not locator:
        return None
    path = Path(locator)
    if not path.is_absolute() or path.name != "state.json":
        raise ContractError("team_caller_invalid", f"{PARENT_STATE_ENV} does not name a run state")
    try:
        relative = path.resolve(strict=True).relative_to(agents_root.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise ContractError("team_caller_invalid", "The calling run belongs to another project runtime") from error
    if len(relative.parts) != 4 or relative.parts[1] != "runs":
        raise ContractError("team_caller_invalid", "The calling run state is not an agent run")
    state = safe_read_json(path)
    agent, run = relative.parts[0], relative.parts[2]
    if state.get("agentId") != agent or state.get("runId") != run:
        raise ContractError("team_caller_invalid", "The calling run state does not match its location")
    return {"agentId": agent, "runId": run, "role": state.get("role"), "provider": state.get("provider"),
            "parentAgentId": state.get("parentAgentId"), "runDirectory": str(path.parent)}


def sender_identity(identity: dict[str, Any] | None) -> dict[str, Any]:
    if identity is None:
        return {"actor": "human"}
    return {key: identity.get(key) for key in ("agentId", "runId", "role", "provider")}


def inbox_directory(runtime_root: Path, agent_id: str) -> Path:
    if not AGENT_ID.fullmatch(agent_id or ""):
        raise ContractError("agent_id_invalid", "agent_id is invalid")
    return runtime_root / "messages" / agent_id


def message_text(text: str | None, path: Path | None) -> str:
    if (text is None) == (path is None):
        raise ContractError("message_missing", "Provide exactly one of --message or --message-file")
    if path is not None:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise ContractError("message_unreadable", f"Message file could not be read as UTF-8: {path}") from error
    text = text.strip()
    if not text:
        raise ContractError("message_missing", "Message text is empty")
    if len(text) > MAX_MESSAGE_CHARS:
        raise ContractError("message_too_large", f"Message has {len(text)} characters; the limit is {MAX_MESSAGE_CHARS}. "
                            "Put large material in a file and send its path")
    return text


def read_messages(runtime_root: Path, agent_id: str) -> list[dict[str, Any]]:
    directory = inbox_directory(runtime_root, agent_id)
    if not directory.is_dir():
        return []
    reject_symlink(directory)
    values = []
    for path in sorted(directory.glob("msg-*.json")):
        if MESSAGE_ID.fullmatch(path.stem) and not path.is_symlink():
            values.append(safe_read_json(path))
    return values


def agent_exists(agents_root: Path, agent_id: str) -> bool:
    return bool(AGENT_ID.fullmatch(agent_id or "")) and (agents_root / agent_id / "session.json").is_file()


def check_send(runtime_root: Path, agents_root: Path, sender: dict[str, Any], to: str, text: str) -> str | None:
    """Validate before queueing; returns the id of an identical undelivered message, if any."""
    if not agent_exists(agents_root, to):
        raise ContractError("message_recipient_unknown", f"No agent `{to}` exists in this project; list teammates with peers")
    if sender.get("agentId") == to:
        raise ContractError("message_recipient_self", "An agent cannot message itself")
    queued = [value for value in read_messages(runtime_root, to) if value.get("status") == "queued"]
    for value in queued:
        if value.get("from") == sender and value.get("text") == text:
            return str(value["id"])
    if len(queued) >= MAX_QUEUED:
        raise ContractError("message_queue_full", f"`{to}` already holds {MAX_QUEUED} undelivered messages; "
                            "batch the rest into one message or wait until it reads them")
    return None


def record(sender: dict[str, Any], to: str, text: str, reply_to: str | None) -> dict[str, Any]:
    if reply_to is not None and not MESSAGE_ID.fullmatch(reply_to):
        raise ContractError("message_reply_invalid", "--reply-to must be a message id")
    return {"schemaVersion": SCHEMA_VERSION, "kind": "agent-message", "id": new_id("msg"), "from": sender,
            "to": to, "text": text, "replyTo": reply_to, "createdAt": now(), "status": "queued", "deliveries": []}


def queue(runtime_root: Path, agents_root: Path, message: dict[str, Any]) -> dict[str, Any]:
    """Place a validated message in its recipient's inbox; an identical undelivered one is reused."""
    directory = inbox_directory(runtime_root, message["to"])
    ensure_directory(directory, find_project_anchor(directory))
    with file_lock(directory / ".lock"):
        existing = check_send(runtime_root, agents_root, message["from"], message["to"], message["text"])
        if existing is not None:
            return {"id": existing, "status": "queued", "duplicate": True}
        path = directory / f"{message['id']}.json"
        if path.exists():
            return {"id": message["id"], "status": safe_read_json(path).get("status"), "duplicate": True}
        atomic_write_json(path, {**message, "queuedAt": now()})
    return {"id": message["id"], "status": "queued", "duplicate": False}


def idle(agents_root: Path, agent_id: str) -> bool:
    state = latest_state(agents_root / agent_id)
    return state is None or state.get("status") in TERMINAL


def notify_lead(runtime_root: Path, agents_root: Path, recipient: str, messages: list[dict[str, Any]],
                reason: str) -> dict[str, Any] | None:
    """Tell the Main session that dispatched an idle agent that messages wait for it.

    Nothing restarts the agent here: only its lead decides whether to dispatch a follow-up run.
    The lead is not told about messages it sent itself; its send already reported the idle recipient."""
    lead = (latest_state(agents_root / recipient) or {}).get("parentAgentId")
    if not messages or not lead or lead == recipient or not agent_exists(agents_root, lead):
        return None
    if {(value.get("from") or {}).get("agentId") for value in messages} == {lead}:
        return None
    ids = ", ".join(str(value["id"]) for value in messages)
    text = (f"`{recipient}` is idle and {len(messages)} team message(s) wait for it ({ids}): {reason} "
            f"It reads them at the start of its next run. Dispatch a follow-up to `{recipient}` if it must act "
            "on them now; otherwise no action is needed.")
    try:
        return queue(runtime_root, agents_root, record(RUNTIME_SENDER, lead, text, None))
    except ContractError:
        return None  # A full lead queue already holds notices; the messages stay queued for the agent.


def after_queue(runtime_root: Path, agents_root: Path, message: dict[str, Any], result: dict[str, Any]) -> None:
    """A message that reaches an idle agent is reported to that agent's lead; direct messages are kept in a room."""
    if result.get("duplicate"):
        return
    if idle(agents_root, message["to"]):
        notify_lead(runtime_root, agents_root, message["to"], [message],
                    "it had already finished its work when the message arrived.")
    from conductor import rooms  # Rooms read the domain store; messages themselves do not.
    rooms.share_direct(runtime_root, agents_root, message)


def write_outbox(run_directory: Path, value: dict[str, Any]) -> Path:
    """The only write an agent run makes: a file in its own run directory for the worker to relay."""
    path = run_directory / OUTBOX / f"{value['id']}.json"
    atomic_write_json(path, value)
    return path


def outbox_items(run_directory: Path) -> list[Path]:
    directory = run_directory / OUTBOX
    if not directory.is_dir():
        return []
    reject_symlink(directory)
    return [path for path in sorted(directory.glob("*.json")) if not path.is_symlink()]


def mark_delivered(runtime_root: Path, agent_id: str, ids: list[str], run_id: str, attempt: int | None, via: str) -> list[str]:
    """Record delivery to one run; repeated deliveries to the same run attempt are not duplicated."""
    directory = inbox_directory(runtime_root, agent_id)
    if not ids or not directory.is_dir():
        return []
    marked = []
    with file_lock(directory / ".lock"):
        for message_id in ids:
            path = directory / f"{message_id}.json"
            if not MESSAGE_ID.fullmatch(message_id) or not path.is_file():
                continue
            value = safe_read_json(path)
            delivery = {"runId": run_id, "attempt": attempt, "via": via}
            if any({key: item.get(key) for key in delivery} == delivery for item in value.get("deliveries", [])):
                continue
            value.setdefault("deliveries", []).append({**delivery, "at": now()})
            value["status"] = "delivered"
            atomic_write_json(path, value)
            marked.append(message_id)
    return marked


def for_run(runtime_root: Path, agent_id: str, run_id: str) -> list[dict[str, Any]]:
    """Messages this run should see: still queued, or already delivered to this same run (a retried attempt)."""
    return [value for value in read_messages(runtime_root, agent_id)
            if value.get("status") == "queued"
            or any(item.get("runId") == run_id for item in value.get("deliveries", []))]


def public(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value.get(key) for key in ("id", "from", "to", "text", "replyTo", "createdAt", "status", "deliveries")}


def latest_state(agent_directory: Path) -> dict[str, Any] | None:
    runs = agent_directory / "runs"
    if not runs.is_dir() or runs.is_symlink():
        return None
    for item in sorted(runs.iterdir(), key=lambda path: path.name, reverse=True):
        state = item / "state.json"
        if item.is_dir() and not item.is_symlink() and state.is_file():
            try:
                return safe_read_json(state)
            except (ContractError, OSError, ValueError):
                return None
    return None


def task_title(state: dict[str, Any]) -> str | None:
    description = (state.get("taskBinding") or {}).get("description")
    if not isinstance(description, str):
        return None
    for line in description.splitlines():
        line = line.strip()
        if line:
            return line.removeprefix("Title:").strip()[:160]
    return None


def queued_count(runtime_root: Path, agent_id: str) -> int:
    try:
        return sum(1 for value in read_messages(runtime_root, agent_id) if value.get("status") == "queued")
    except (ContractError, OSError, ValueError):
        return 0


def session_record(directory: Path) -> dict[str, Any]:
    try:
        return safe_read_json(directory / "session.json")
    except (ContractError, OSError, ValueError):
        return {}


def outbox_post(identity: dict[str, Any], room: str, text: str) -> dict[str, Any]:
    return {"schemaVersion": SCHEMA_VERSION, "kind": "room-post", "id": new_id("msg"), "outbox": "post",
            "room": room, "text": text, "createdAt": now()}


def outbox_project(form: str, **fields: Any) -> dict[str, Any]:
    """A project room claim, release or change notice written by a run for the worker to relay."""
    return {"schemaVersion": SCHEMA_VERSION, "id": new_id("msg"), "outbox": form, **fields, "createdAt": now()}


def outbox_message(identity: dict[str, Any], to: str, text: str, reply_to: str | None) -> dict[str, Any]:
    return {**record(sender_identity(identity), to, text, reply_to), "outbox": "message"}


def seen_record(identity: dict[str, Any], ids: list[str]) -> dict[str, Any]:
    return {"schemaVersion": SCHEMA_VERSION, "kind": "agent-message-seen", "id": new_id("seen"),
            "outbox": "seen", "agentId": identity["agentId"], "runId": identity["runId"], "messageIds": ids,
            "createdAt": now()}
