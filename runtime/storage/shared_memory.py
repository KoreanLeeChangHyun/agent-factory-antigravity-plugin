"""Project memory shared by every Agent Factory session, whatever its provider.

One fact per entry, each with its source. Entries an agent writes are candidates until the
Human approves them; candidates are still shown, marked unconfirmed. A correction is a new
entry that supersedes the old one, so earlier text stays recorded. Memory is evidence from
earlier sessions, never authority: it grants no approval, permission or scope.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from storage.errors import ContractError
from storage.files import atomic_write_json, ensure_directory, file_lock, find_project_anchor, reject_symlink, safe_read_json
from storage.team_messages import SCHEMA_VERSION, new_id
from system.containment import now

TYPES = ("user", "feedback", "project", "reference")
STATUSES = ("candidate", "active", "superseded", "retired")
VISIBLE = ("active", "candidate")
MEMORY_ID = re.compile(r"mem-[0-9]{8}T[0-9]{12}Z-[a-f0-9]{8}\Z")
MAX_TITLE_CHARS = 200
# An entry is one durable fact; longer material belongs in a Document the entry's source names.
MAX_TEXT_CHARS = 20_000
# The index every run receives stays as small as Claude Code's MEMORY.md load; the rest is searchable.
INDEX_MAX_LINES = 200
INDEX_MAX_BYTES = 25 * 1024


def directory(runtime_root: Path) -> Path:
    return runtime_root / "memory"


def entry(writer: dict[str, Any], kind: str, title: str, text: str, source: str, supersedes: str | None) -> dict[str, Any]:
    if kind not in TYPES:
        raise ContractError("memory_type_invalid", "Memory type is user, feedback, project or reference")
    title = " ".join((title or "").split())
    if not title or len(title) > MAX_TITLE_CHARS:
        raise ContractError("memory_title_invalid", f"Title is one nonempty line of at most {MAX_TITLE_CHARS} characters")
    text = (text or "").strip()
    if not text or len(text) > MAX_TEXT_CHARS:
        raise ContractError("memory_text_invalid", f"Text is required and at most {MAX_TEXT_CHARS} characters; "
                            "put longer material in a Document and cite it as the source")
    source = (source or "").strip()
    if not source:
        raise ContractError("memory_provenance_required", "Every memory entry names its source (run, message, file or URL)")
    if supersedes is not None and not MEMORY_ID.fullmatch(supersedes):
        raise ContractError("memory_supersedes_invalid", "--supersedes must be a memory id")
    stamp = now()
    return {"schemaVersion": SCHEMA_VERSION, "kind": "shared-memory", "id": new_id("mem"), "type": kind,
            "title": title, "text": text, "source": source, "writer": writer, "supersedes": supersedes,
            "status": "active" if writer.get("actor") == "human" else "candidate", "createdAt": stamp, "modified": stamp}


def read_all(runtime_root: Path) -> list[dict[str, Any]]:
    root = directory(runtime_root)
    if not root.is_dir():
        return []
    reject_symlink(root)
    values = []
    for path in sorted(root.glob("mem-*.json")):
        if MEMORY_ID.fullmatch(path.stem) and not path.is_symlink():
            values.append(safe_read_json(path))
    return values


def find(runtime_root: Path, memory_id: str) -> dict[str, Any]:
    if not MEMORY_ID.fullmatch(memory_id or ""):
        raise ContractError("memory_id_invalid", "Memory id is invalid")
    path = directory(runtime_root) / f"{memory_id}.json"
    if not path.is_file():
        raise ContractError("memory_missing", f"No memory entry `{memory_id}`")
    return safe_read_json(path)


def store(runtime_root: Path, value: dict[str, Any]) -> dict[str, Any]:
    """Record a validated entry once; an active entry supersedes the one it names at the same time."""
    root = directory(runtime_root)
    ensure_directory(root, find_project_anchor(root))
    with file_lock(root / ".lock"):
        path = root / f"{value['id']}.json"
        if path.exists():
            return safe_read_json(path)
        if value.get("supersedes"):
            find(runtime_root, value["supersedes"])
        atomic_write_json(path, value)
        if value["status"] == "active" and value.get("supersedes"):
            _set_status(root, value["supersedes"], "superseded", supersededBy=value["id"])
    return value


def _set_status(root: Path, memory_id: str, status: str, **fields: Any) -> dict[str, Any]:
    path = root / f"{memory_id}.json"
    value = safe_read_json(path)
    value.update(status=status, modified=now(), **fields)
    atomic_write_json(path, value)
    return value


def approve(runtime_root: Path, memory_id: str) -> dict[str, Any]:
    root = directory(runtime_root)
    find(runtime_root, memory_id)
    with file_lock(root / ".lock"):
        value = find(runtime_root, memory_id)
        if value.get("status") != "candidate":
            raise ContractError("memory_not_candidate", f"`{memory_id}` is {value.get('status')}, not a candidate")
        value = _set_status(root, memory_id, "active", approvedAt=now())
        if value.get("supersedes"):
            _set_status(root, value["supersedes"], "superseded", supersededBy=memory_id)
    return value


def retire(runtime_root: Path, memory_id: str, reason: str) -> dict[str, Any]:
    reason = (reason or "").strip()
    if not reason:
        raise ContractError("memory_reason_required", "Say why the entry is retired")
    root = directory(runtime_root)
    find(runtime_root, memory_id)
    with file_lock(root / ".lock"):
        value = find(runtime_root, memory_id)
        if value.get("status") in ("superseded", "retired"):
            raise ContractError("memory_inactive", f"`{memory_id}` is already {value['status']}")
        return _set_status(root, memory_id, "retired", retiredReason=reason)


def visible(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Active and candidate entries, newest first."""
    return sorted((value for value in values if value.get("status") in VISIBLE),
                  key=lambda value: (str(value.get("modified", "")), str(value.get("id"))), reverse=True)


def search(runtime_root: Path, query: str, include_inactive: bool = False) -> list[dict[str, Any]]:
    terms = [term for term in (query or "").casefold().split() if term]
    if not terms:
        raise ContractError("memory_query_required", "Search needs a nonempty query")
    values = read_all(runtime_root)
    pool = values if include_inactive else visible(values)
    hits = []
    for value in pool:
        haystack = " ".join(str(value.get(key, "")) for key in ("type", "title", "text", "source")).casefold()
        if all(term in haystack for term in terms):
            hits.append(value)
    return sorted(hits, key=lambda value: str(value.get("modified", "")), reverse=True)


def index_line(value: dict[str, Any]) -> str:
    note = " (candidate: not confirmed by the user)" if value.get("status") == "candidate" else ""
    return f"- {value['id']} [{value['type']}] {value['title']}{note}"


def index(values: list[dict[str, Any]]) -> tuple[list[str], int]:
    """Index lines for the newest visible entries within the load budget, and how many were left out."""
    lines, size = [], 0
    shown = visible(values)
    for value in shown:
        line = index_line(value)
        cost = len(line.encode("utf-8")) + 1
        if len(lines) >= INDEX_MAX_LINES or size + cost > INDEX_MAX_BYTES:
            break
        lines.append(line)
        size += cost
    return lines, len(shown) - len(lines)


def public(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value.get(key) for key in ("id", "type", "title", "text", "source", "writer", "status", "supersedes",
                                            "supersededBy", "createdAt", "modified", "approvedAt", "retiredReason")
            if key in value}
