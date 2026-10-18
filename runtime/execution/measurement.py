"""Content-free, per-attempt observations; never estimate model tokens or calls."""
from __future__ import annotations

import hashlib
import json

from runs import trace


class AttemptMeasurement:
    def __init__(self, fixed, dynamic, *, model=None, provider=None):
        self.prompt = {
            "version": hashlib.sha256(fixed.encode("utf-8")).hexdigest(),
            "fixedCharacters": len(fixed), "fixedUtf8Bytes": len(fixed.encode("utf-8")),
            "dynamicCharacters": len(dynamic), "dynamicUtf8Bytes": len(dynamic.encode("utf-8")),
        }
        self.model, self.provider = model, provider
        self.events = self.event_bytes = self.output_bytes = self.output_characters = 0
        self.turns, self.tools, self.results = set(), set(), set()
        self.saw_tools = self.saw_turns = False
        self.active_turn = None
        self.outputs = 0
        self.missing_output = False

    def observe(self, event, event_bytes):
        self.events += 1
        self.event_bytes += event_bytes
        kind, turn = event.get("type"), event.get("turn_id")
        changed = False
        if kind in {"turn.started", "turn.completed"} and isinstance(turn, str):
            if kind == "turn.started":
                self.active_turn = turn
            self.saw_turns = True
            changed = turn not in self.turns
            self.turns.add(turn)
        item = event.get("item")
        if kind not in {"item.started", "item.completed"} or not isinstance(item, dict):
            return changed
        if item.get("type") not in {"command_execution", "mcp_tool_call", "web_search", "file_change", "tool_call"}:
            return changed
        identity = item.get("id")
        if not isinstance(identity, (str, int)) or isinstance(identity, bool):
            return changed
        self.saw_tools = True
        key = (self.active_turn, item.get("type"), identity)
        changed = changed or key not in self.tools
        self.tools.add(key)
        if kind == "item.completed" and key not in self.results:
            self.results.add(key)
            # Count the normalized result once, not progress snapshots or deltas.
            output = next((item[name] for name in ("aggregated_output", "output", "result", "content")
                           if item.get(name) is not None), None)
            if output is None:
                self.missing_output = True
            else:
                self.outputs += 1
                text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, sort_keys=True)
                self.output_characters += len(text)
                self.output_bytes += len(text.encode("utf-8"))
            changed = True
        return changed

    def snapshot(self):
        return {"schemaVersion": 1, "model": self.model, "provider": self.provider,
                "prompt": dict(self.prompt), "events": self.events, "eventUtf8Bytes": self.event_bytes,
                "providerTurns": len(self.turns) if self.saw_turns else None,
                "toolCalls": len(self.tools) if self.saw_tools else None,
                "toolOutputCharacters": self.output_characters if self.outputs and not self.missing_output else None,
                "toolOutputUtf8Bytes": self.output_bytes if self.outputs and not self.missing_output else None,
                "inferenceCalls": None,
                "scope": "normalized-provider-events; prompt bytes are not model tokens"}


def save(runtime, state_path, state, attempt, measurement):
    """Instrumentation failure must not replace the work's result or cancellation."""
    try:
        snapshot = {**measurement.snapshot(), "observedAt": runtime.now()}
        def update(value):
            attempts = dict(value.get("measurementAttempts") or {})
            attempts[str(attempt)] = snapshot
            value["measurementAttempts"] = attempts
        runtime.update_json(state_path, state_path.parent / ".state.lock", update)
    except Exception as error:
        trace.exception(state, "measurement.persist.failed", error, attempt=attempt)
