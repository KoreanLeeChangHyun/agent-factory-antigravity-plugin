"""Resolve a delegated role's model from the Human's registered candidates.

The Human-facing host captures each role's settings with the Main run (`executionOptions.agentModels`). A role holds
one model as before, or several candidates, each with its own model, reasoning effort and Fast. With `selection:
"conductor"` Main chooses one candidate per task and states why; otherwise the role's own model is fixed. An explicit
model Main passes always wins, so a model the Human names in a request is kept. The record is selection evidence
stored with the loop; it grants no authority and changes no permission or Verification requirement.

Image generation is a tool capability, not a property of a provider name: a task that needs an image-generation tool
records the tool's availability as unconfirmed unless the captured candidate itself was marked confirmed. Drawing with
SVG, Canvas or CSS code needs no image tool.
"""
from __future__ import annotations

ROLES = ("work", "workLight", "verification", "explore", "scribe", "designer")
EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")
SELECTIONS = ("fixed", "conductor")
IMAGE_NEEDS = ("image-tool", "code-drawing", "none")
# Explorer and Scribe use the Worker's settings until they have their own; the Worker uses the Expert's. The Designer has
# no fallback: the Worker or Expert may be an Anthropic model, which has no image generator.
FALLBACK = {"explore": "workLight", "scribe": "workLight", "workLight": "work"}


def _setting(value, where):
    if not isinstance(value, dict):
        raise ValueError(where + " must be an object")
    unknown = set(value) - {"model", "reasoningEffort", "fast", "provider", "imageGeneration"}
    if unknown:
        raise ValueError(where + " has unknown fields " + ", ".join(sorted(unknown)))
    model = value.get("model")
    if model is not None and (not isinstance(model, str) or not model.strip() or len(model) > 100):
        raise ValueError(where + " model must be a nonempty model ID")
    if value.get("reasoningEffort") is not None and value["reasoningEffort"] not in EFFORTS:
        raise ValueError(where + " reasoningEffort is invalid")
    if value.get("fast") is not None and not isinstance(value["fast"], bool):
        raise ValueError(where + " fast must be a boolean")
    if value.get("imageGeneration") is not None and value["imageGeneration"] != "confirmed":
        raise ValueError(where + " imageGeneration may only record a confirmed tool")
    return {key: value[key] for key in ("model", "reasoningEffort", "fast", "provider", "imageGeneration") if value.get(key) is not None}


def validate(models):
    """Normalize the host-captured role settings; unknown roles and malformed candidates are rejected."""
    if not isinstance(models, dict):
        raise ValueError("agent models must be an object")
    result = {}
    for role, value in models.items():
        if not isinstance(role, str) or not isinstance(value, dict):
            raise ValueError("agent models map role names to settings")
        # Chat inference rows (router, editor) and the Resolver are carried unchanged; only delegated roles are checked.
        if role not in ROLES:
            result[role] = value
            continue
        candidates = value.get("candidates")
        selection = value.get("selection")
        base = _setting({key: item for key, item in value.items() if key not in ("candidates", "selection")}, role)
        if selection is not None and selection not in SELECTIONS:
            raise ValueError(role + " selection must be fixed or conductor")
        if candidates is not None:
            if not isinstance(candidates, list):
                raise ValueError(role + " candidates must be a list")
            candidates = [_setting(item, role + " candidate") for item in candidates]
            if any("model" not in item for item in candidates):
                raise ValueError(role + " candidates each need a model")
            models_seen = [item["model"] for item in candidates]
            if len(set(models_seen)) != len(models_seen):
                raise ValueError(role + " candidates repeat a model")
            base["candidates"] = candidates
        if selection is not None:
            base["selection"] = selection
        result[role] = base
    return result


def role_setting(captured, role):
    """The captured setting a role uses, following the host's fallbacks."""
    current = role
    while current:
        setting = (captured or {}).get(current)
        if isinstance(setting, dict) and (setting.get("model") or setting.get("candidates")):
            return current, setting
        current = FALLBACK.get(current)
    return None, None


def resolve(captured, role, *, explicit=None, reason=None, image_need=None):
    """Return the selection record for one role, or None when the Human registered nothing for it."""
    source_role, setting = role_setting(captured, role)
    explicit = {key: value for key, value in (explicit or {}).items() if value is not None}
    reason = reason.strip() if isinstance(reason, str) and reason.strip() else None
    if image_need is not None and image_need not in IMAGE_NEEDS:
        raise ValueError("image need must be " + ", ".join(IMAGE_NEEDS))
    if setting is None and not explicit.get("model"):
        return None
    candidates = list((setting or {}).get("candidates") or [])
    fixed = {key: setting[key] for key in ("model", "reasoningEffort", "fast") if setting and setting.get(key) is not None}
    if setting and not candidates and fixed.get("model"):
        candidates = [dict(fixed)]
    choosing = bool(setting) and setting.get("selection") == "conductor" and len(candidates) > 1
    record = {"role": role, "settingRole": source_role, "candidates": [dict(item) for item in candidates],
              "selection": "conductor" if choosing else "fixed", "source": None, "selected": None,
              "inCandidates": None, "reason": reason, "warnings": []}
    by_model = {item["model"]: item for item in candidates}
    if explicit.get("model"):
        # A model Main passes explicitly (for example one the Human named) always wins; a registered candidate keeps
        # its own effort and Fast unless Main passed them too.
        chosen = {**by_model.get(explicit["model"], {}), **explicit}
        record.update(source="explicit", selected=chosen, inCandidates=explicit["model"] in by_model)
        if candidates and not record["inCandidates"]:
            record["warnings"].append("explicit model is not a registered candidate; kept as passed")
        if choosing and record["inCandidates"] and not reason:
            raise ValueError(role + " chooses among registered candidates; state why with the model reason")
    elif choosing:
        # Main did not choose: the first registered candidate (the Human's default) applies, recorded as such.
        record.update(source="first-candidate", selected=dict(candidates[0]), inCandidates=True)
        record["warnings"].append("conductor did not choose among the registered candidates; the first candidate applied")
    elif fixed.get("model"):
        record.update(source="human-fixed", selected=dict(fixed), inCandidates=True)
    else:
        return None
    if image_need is not None:
        record["imageNeed"] = image_need
        if image_need == "image-tool":
            confirmed = by_model.get(record["selected"]["model"], {}).get("imageGeneration") == "confirmed"
            record["imageTool"] = "confirmed" if confirmed else "unconfirmed"
            if not confirmed:
                record["warnings"].append("image-generation tool availability is unconfirmed for the selected model; a provider name is not evidence")
    return record
