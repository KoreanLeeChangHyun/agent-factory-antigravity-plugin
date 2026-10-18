"""Local diagnostic evidence; never an execution authority or a completion verdict.

The journal links existing request/events/result/receipt files. Prompt snapshots
capture host-observable delivery, not the provider's hidden context or reasoning.
All writes are best effort and use the run's existing private storage directory.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
from pathlib import Path
import re
import sys
import threading
import time
import traceback
import uuid
from functools import lru_cache

from storage import files
from storage.errors import ContractError
from system.transport import EventLogWriter


SECRET_KEY = re.compile(r"(?i)(?:password|passwd|secret|authorization|cookie|api[-_]?key|access[-_]?token|refresh[-_]?token|credential)")
SECRET_TEXT = re.compile(
    r"(?i)(\b(?:[\w-]*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|secret)|authorization|cookie)"
    r"[\"']?\s*[:=]\s*)(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;}]+)"
)
BEARER = re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/-]+=*")
PRIVATE_KEY = re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", re.S)
KNOWN_TOKEN = re.compile(r"\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,})\b")
SECRET_FLAG = re.compile(r"(?i)^--?(?:[\w-]*(?:password|passwd|secret|api[-_]?key|token)|authorization)$")
URL_PASSWORD = re.compile(r"(\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s/@:]+:)[^\s/@]+(@)")
OPAQUE_KEYS = {"encrypted_content", "encryptedcontent", "signature", "token", "sessiontoken"}
ENVIRONMENT_KEYS = {"env", "environment", "processenv", "environmentvariables"}


def redact(value):
    """Mask recognized credentials; do not collect environment/configuration dumps."""
    if isinstance(value, dict):
        return {key: "[REDACTED]" if SECRET_KEY.search(str(key)) or str(key).lower() in OPAQUE_KEYS | ENVIRONMENT_KEYS else redact(item)
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return ["[REDACTED]" if index and isinstance(value[index - 1], str) and SECRET_FLAG.fullmatch(value[index - 1])
                else redact(item) for index, item in enumerate(value)]
    if isinstance(value, str):
        # Tool arguments are often a JSON string inside another JSON message.
        if value.lstrip().startswith(("{", "[")):
            try:
                parsed = json.loads(value)
                sanitized = redact(parsed)
                if parsed != sanitized:
                    start = value[:len(value) - len(value.lstrip())]
                    end = value[len(value.rstrip()):]
                    return start + json.dumps(sanitized, ensure_ascii=False) + end
            except (ValueError, RecursionError):
                pass
        value = PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", value)
        value = KNOWN_TOKEN.sub("[REDACTED TOKEN]", value)
        value = BEARER.sub(r"\1[REDACTED]", value)
        value = URL_PASSWORD.sub(r"\1[REDACTED]\2", value)
        value = re.sub(r"(?i)(--?(?:[\w-]*(?:password|passwd|secret|api[-_]?key|token)|authorization)\s+)(?:\"[^\"]*\"|'[^']*'|\S+)", r"\1[REDACTED]", value)
        return SECRET_TEXT.sub(r"\1[REDACTED]", value)
    return value


class StreamRedactor:
    """Mask stderr across read boundaries, including multiline private-key blocks."""
    def __init__(self):
        self.pending = []
        self.private_key = False

    def feed(self, chunk, *, final=False):
        pieces = chunk.split("\n")
        lines = []
        for piece in pieces[:-1]:
            self.pending.append(piece + "\n")
            lines.append("".join(self.pending))
            self.pending.clear()
        if pieces[-1]:
            self.pending.append(pieces[-1])
        if final and self.pending:
            lines.append("".join(self.pending))
            self.pending.clear()
        output = []
        for line in lines:
            if self.private_key:
                end = re.search(r"-----END [^-]*PRIVATE KEY-----", line)
                if end:
                    self.private_key = False
                    output.append(redact(line[end.end():]))
                continue
            start = re.search(r"-----BEGIN [^-]*PRIVATE KEY-----", line)
            if start:
                end = re.search(r"-----END [^-]*PRIVATE KEY-----", line[start.end():])
                if end:
                    output.append(redact(line))
                else:
                    output.append(redact(line[:start.start()]) + "[REDACTED PRIVATE KEY]\n")
                    self.private_key = True
            else:
                output.append(redact(line))
        return "".join(output)


def _directory(state):
    # Legacy callers without a persisted run cannot acquire a new log location.
    path = state.get("statePath")
    return Path(path).parent if path else None


def _failure(state, operation, error):
    warning = {"schemaVersion": 1, "observedAt": files.now(), "operation": operation,
               "errorType": type(error).__name__, "code": getattr(error, "code", None),
               "errno": getattr(error, "errno", None), "message": redact(str(error)), "incomplete": True}
    directory = _directory(state)
    try:
        if directory is not None:
            files.atomic_write_json(directory / "trace-error.json", warning)
    except (OSError, ValueError, ContractError):
        pass
    # Exception text can contain credentials. The type is sufficient here.
    try:
        print(f"Agent Factory diagnostic trace incomplete ({operation}: {type(error).__name__})", file=sys.stderr)
    except OSError:
        pass


@lru_cache(maxsize=1)
def resource():
    root = Path(__file__).resolve().parents[2]
    version = None
    for path in (root / "distribution/package.json", root / ".codex-plugin/plugin.json", root / ".claude-plugin/plugin.json"):
        try:
            version = json.loads(path.read_text()).get("version")
            break
        except (OSError, ValueError):
            continue
    return {"serviceName": "agent-factory", "serviceVersion": version,
            "pythonVersion": platform.python_version(), "os": sys.platform, "architecture": platform.machine()}


def record(state, event, *, attempt=None, _journal="trace.jsonl", _severity=None, **data):
    directory = _directory(state)
    if directory is None or not directory.is_dir():
        return None
    try:
        event_id = uuid.uuid4().hex
        binding = state.get("taskBinding") or {}
        row = {"schemaVersion": 1, "eventId": event_id, "event": event,
               "observedAt": files.now(), "runId": state.get("runId"), "agentId": state.get("agentId"),
               "monotonicNs": time.perf_counter_ns(), "writerPid": os.getpid(), "writerThreadId": threading.get_ident(),
               "severity": _severity or ("ERROR" if event.endswith(("failed", "rejected")) else "INFO"),
               "resource": resource(), "projectId": (state.get("runtimeBinding") or {}).get("projectId"),
               "conversationId": state.get("conversationId"), "sessionId": state.get("sessionId"),
               "parentRunId": state.get("parentRunId"), "parentAgentId": state.get("parentAgentId"),
               "workflowId": binding.get("workflowId"), "taskId": binding.get("taskId"),
               "provider": state.get("provider"), "role": state.get("role"),
               "attempt": state.get("attempt", 0) if attempt is None else attempt,
               "data": redact(data)}
        # Parent, worker and provider bridge can write concurrently. Do not take
        # the state lock here: terminal transitions may already hold it.
        if _journal not in {"trace.jsonl", "provider.jsonl"}:
            raise ValueError("unsupported diagnostic journal")
        with files.file_lock(directory / ("." + _journal + ".lock")):
            writer = EventLogWriter(directory / _journal)
            try:
                if not writer.append(json.dumps(row, ensure_ascii=False) + "\n"):
                    raise OSError("trace append rejected")
            finally:
                writer.close()
        return event_id
    except (OSError, ValueError, TypeError, RecursionError, ContractError) as error:
        _failure(state, event, error)
        return None


def snapshot(state, stage, payload, *, attempt=None, **metadata):
    """Preserve each preparation/delivery separately, including retries and repair."""
    directory = _directory(state)
    if directory is None or not directory.is_dir():
        return None
    try:
        if callable(payload):
            payload = payload()
        original = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        sanitized = redact(payload)
        changed = json.dumps(sanitized, ensure_ascii=False, sort_keys=True).encode("utf-8") != original
        prefix = "prompt" if stage.startswith(("prompt.", "provider.delivery.")) else "evidence"
        path = directory / f"{prefix}-{uuid.uuid4().hex}.json"
        document = {"schemaVersion": 1, "stage": stage, "runId": state.get("runId"),
                    "attempt": state.get("attempt", 0) if attempt is None else attempt,
                    "observedAt": files.now(), "originalSha256": hashlib.sha256(original).hexdigest(),
                    "redacted": changed, "payload": sanitized}
        files.atomic_write_json(path, document)
        reference = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "originalSha256": document["originalSha256"], "redacted": document["redacted"]}
        record(state, stage, attempt=attempt, snapshot=reference, **metadata)
        return reference
    except (OSError, ValueError, TypeError, IndexError, RecursionError, ContractError) as error:
        _failure(state, stage, error)
        return None


def artifact(path):
    """Fingerprint existing evidence without copying its potentially sensitive text."""
    if not path:
        return None
    try:
        content = files.safe_read_bytes(Path(path), None)
        return {"path": str(path), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    except (OSError, ContractError):
        return {"path": str(path), "available": False}


def provider_message(state, direction, message, **metadata):
    """Keep every host-visible protocol message before normalization, without sampling."""
    try:
        raw = message if isinstance(message, str) else json.dumps(message, ensure_ascii=False)
        valid = True
        if isinstance(message, str):
            try:
                message = json.loads(message)
            except ValueError:
                valid = False
        severity = "ERROR" if direction == "read-error" or isinstance(message, dict) and message.get("error") else "DEBUG" if valid else "WARN"
        return record(state, "provider.message", _journal="provider.jsonl", _severity=severity,
                      direction=direction, body=message, validJson=valid,
                      originalSha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                      sourceTimestamp=message.get("timestamp") if isinstance(message, dict) else None, **metadata)
    except (OSError, ValueError, TypeError, RecursionError, ContractError) as error:
        _failure(state, "provider.message", error)
        return None


def checkpoint(state, stage, **metadata):
    fields = ("status", "taskMode", "workProfile", "taskBinding", "executionOptions", "executionPolicy",
              "humanApprovalPolicy", "executionPreflight", "workingDirectory", "runtimeBinding",
              "imageInputs", "documentContext", "documentContextAttempts", "tokenUsage", "usageAttempts",
              "contextUsage", "goal", "goalError", "decisionKind", "decisionScope", "decisionDetails",
              "error", "pendingRpc", "planProgress", "activity", "containment", "startDisposition")
    return snapshot(state, stage, {key: state[key] for key in fields if key in state}, **metadata)


def exception(state, stage, error, **metadata):
    # Stack frames and chained exception messages, never frame locals or environment.
    record(state, stage, _severity="ERROR", exceptionType=type(error).__name__,
           message=str(error), stacktrace="".join(traceback.format_exception(type(error), error, error.__traceback__)),
           **metadata)


def loop_transition(state):
    """Link committed orchestration decisions to the requesting Main run."""
    if not state.get("parentStatePath"):
        return
    try:
        parent = files.safe_read_json(Path(state["parentStatePath"]))
        record(parent, "loop.transition", **{key: state.get(key) for key in (
            "loopId", "statePath", "stateRevision", "status", "phase", "currentChild",
            "latestWorkRunId", "latestVerificationRunId", "lastVerificationDecision",
            "pendingFindingIds", "humanSkip", "terminalReason", "controlPlaneError")},
            workflowId=(state.get("workflow") or {}).get("id"),
            taskBinding=(state.get("execution") or {}).get("taskBinding"),
            taskListPath=(state.get("execution") or {}).get("taskListPath"))
    except (OSError, ValueError, TypeError, ContractError) as error:
        _failure(state, "loop.transition", error)


class DeliveryRpc:
    """Observe prompt-bearing RPC boundaries, including Goal, plan and repair turns."""
    METHODS = {"thread/start", "thread/resume", "thread/inject_items", "turn/start", "thread/goal/set"}
    FIELDS = {"developerInstructions", "input", "items", "objective", "status", "threadId",
              "model", "effort", "serviceTier", "collaborationMode", "outputSchema", "cwd", "approvalPolicy"}

    def __init__(self, rpc, state):
        object.__setattr__(self, "_rpc", rpc)
        object.__setattr__(self, "_state", state)
        # Replace our prior lease's observer instead of chaining it into this run.
        bind_protocol_observer(rpc, state)

    def __getattr__(self, key):
        return getattr(self._rpc, key)

    def __setattr__(self, key, value):
        setattr(self._rpc, key, value)

    def call(self, method, params, **kwargs):
        if method not in self.METHODS:
            return self._rpc.call(method, params, **kwargs)
        reference = snapshot(self._state, "provider.delivery.requested",
                             {key: value for key, value in params.items() if key in self.FIELDS}, method=method)
        started = time.perf_counter_ns()
        try:
            result = self._rpc.call(method, params, **kwargs)
        except Exception as error:
            exception(self._state, "provider.delivery.failed", error, method=method, snapshot=reference,
                      durationMs=(time.perf_counter_ns() - started) / 1_000_000, code=getattr(error, "code", None))
            raise
        record(self._state, "provider.delivery.acknowledged", method=method, snapshot=reference,
               durationMs=(time.perf_counter_ns() - started) / 1_000_000,
               threadId=_response_id(result, "thread"), turnId=_response_id(result, "turn"))
        return result


class ProtocolObserver:
    def __init__(self, state, previous=None):
        self.state, self.previous = state, previous

    def __call__(self, direction, value):
        provider_message(self.state, direction, value)
        if self.previous is not None:
            self.previous(direction, value)


def bind_protocol_observer(rpc, state):
    if hasattr(rpc, "observer"):
        previous = rpc.observer
        if isinstance(previous, ProtocolObserver):
            previous = previous.previous
        rpc.observer = ProtocolObserver(state, previous)


def _response_id(result, key):
    value = result.get(key) if isinstance(result, dict) else None
    return value.get("id") if isinstance(value, dict) else None
