"""Git handling of the Agent Factory-managed `docs/` tree.

Canonical Documents, Original source records and artifact deliverables are committed;
local lesson records and per-run evidence bundles are not. Agent Factory edits only its
own marked block in an ignore file and never creates a repository, commits or changes the
index. Files already tracked that the block now ignores are reported for an explicitly
authorized untrack.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

from storage import artifacts, paths

MODES = ("project", "separate", "local")
BEGIN = "# >>> agent-factory: managed block, edit outside it"
END = "# <<< agent-factory"
DOCS_RULES = (
    "# Local lesson records, including generated files.",
    "/lessons-learned/",
    "# Per-run evidence bundles (<topic>__<13-digit time>-<id>.zip).",
    "/artifact/evidence/*__" + "[0-9]" * 13 + "-*.zip",
)
ROOT_RULES = ("# The docs/ tree stays local to this machine.", "/docs/")
# Lines earlier releases wrote outside a block; migrated into the block once.
LEGACY = frozenset((
    "# Operational lesson bodies and generated record files remain local.",
    "# Per-run browser evidence bundles stay local; see rule-extension-development §15.6.",
    "/lessons-learned/",
    "/artifact/evidence/*__" + "[0-9]" * 13 + "-*.zip",
))


def write_text(path: Path, content: str) -> None:
    """Atomic project-file write keeping ordinary permissions (ignore files are shared)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def repository(path: Path) -> Path | None:
    """The top level of the repository containing `path`, if any."""
    if not path.is_dir():
        return None
    result = _git(path, "rev-parse", "--show-toplevel")
    return Path(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else None


def block(text: str, rules: tuple[str, ...] | None, legacy: frozenset[str] = frozenset()) -> str:
    """Return `text` with exactly one current managed block (none when `rules` is None); other lines keep their order."""
    kept, inside = [], False
    for line in text.splitlines():
        if line == BEGIN:
            inside = True
        elif line == END and inside:
            inside = False
        elif not inside and line not in legacy:
            kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    if rules is None:
        return "\n".join(kept) + "\n" if kept else ""
    return "\n".join([*kept, *([""] if kept else []), BEGIN, *rules, END]) + "\n"


def has_block(path: Path, rules: tuple[str, ...]) -> bool:
    paths.inspect(path, missing=True)
    if not path.is_file():
        return False
    return block(path.read_text(encoding="utf-8"), rules, LEGACY) == path.read_text(encoding="utf-8")


def ensure_block(path: Path, rules: tuple[str, ...] | None, atomic=write_text) -> bool:
    """Write the managed block when missing or stale, or remove it for None. Returns whether the file changed."""
    paths.inspect(path, missing=True)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    updated = block(text, rules, LEGACY if rules is not None else frozenset())
    if updated == text or (rules is None and not path.is_file()):
        return False
    atomic(path, updated)
    return True


def ensure_docs_block(project_root: Path, atomic=write_text) -> bool:
    return ensure_block(Path(project_root) / "docs/.gitignore", DOCS_RULES, atomic)


def _settings(runtime_root: Path) -> Path:
    return Path(runtime_root) / "docs-git.json"


def _suggested(project_root: Path, top: Path | None, docs_top: Path | None) -> str:
    if docs_top and docs_top != top:
        return "separate"
    if top and _git(project_root, "check-ignore", "-q", "docs/").returncode == 0:
        return "local"
    return "project"


def tracked_ignored(project_root: Path) -> list[str]:
    """Tracked docs files that the ignore rules now exclude, relative to docs/."""
    docs = Path(project_root) / "docs"
    if not repository(docs):
        return []
    result = _git(docs, "ls-files", "-ci", "--exclude-standard", "--", ".")
    return sorted(line for line in result.stdout.splitlines() if line) if result.returncode == 0 else []


def conflict(project_root: Path, mode: str | None) -> dict | None:
    """In project mode, a rule outside Agent Factory's block that still ignores all of docs/."""
    project_root = Path(project_root)
    if mode != "project" or not repository(project_root):
        return None
    result = _git(project_root, "check-ignore", "-v", "--no-index", "docs/")
    if result.returncode != 0 or not result.stdout.strip():
        return None
    source, line, pattern = result.stdout.split("\t", 1)[0].split(":", 2)
    if pattern.startswith("!"):
        return None
    path = (project_root / source).resolve() if not Path(source).is_absolute() else Path(source)
    # Only a project .gitignore outside the managed block is removable; global and info/exclude rules are reported.
    removable = path.name == ".gitignore" and path.is_relative_to(project_root.resolve()) and ".git" not in path.relative_to(project_root.resolve()).parts
    relative = path.relative_to(project_root.resolve()).as_posix() if path.is_relative_to(project_root.resolve()) else str(path)
    return {"file": relative, "line": int(line), "pattern": pattern, "removable": removable}


def unignore(project_root: Path, runtime_root: Path, atomic=write_text) -> dict:
    """Remove the reported conflicting line; only on an explicit request after the user agreed."""
    project_root = Path(project_root)
    found = conflict(project_root, status(project_root, runtime_root)["mode"])
    if not found or not found["removable"]:
        raise ValueError("No removable rule ignores docs/")
    path = project_root / found["file"]
    paths.inspect(path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if lines[found["line"] - 1].rstrip("\r\n") != found["pattern"]:
        raise ValueError("The ignore file changed; check docs-git status again")
    del lines[found["line"] - 1]
    atomic(path, "".join(lines))
    return status(project_root, runtime_root)


def status(project_root: Path, runtime_root: Path | None) -> dict:
    project_root = Path(project_root)
    top, docs_top = repository(project_root), repository(project_root / "docs")
    # An unregistered project has no runtime storage and therefore no recorded mode yet.
    settings = _settings(runtime_root) if runtime_root else None
    stored = paths.read(settings) if settings and settings.is_file() else {}
    mode = stored.get("mode") if stored.get("mode") in MODES else None
    managed = has_block(project_root / "docs/.gitignore", DOCS_RULES)
    if mode == "local":
        managed = managed and has_block(project_root / ".gitignore", ROOT_RULES)
    return {"schemaVersion": 1, "kind": "docs-git", "repository": bool(top),
            "docsRepository": bool(docs_top and docs_top != top), "mode": mode,
            "suggestedMode": _suggested(project_root, top, docs_top), "managed": managed,
            "trackedIgnored": tracked_ignored(project_root), "conflict": conflict(project_root, mode)}


def apply(project_root: Path, runtime_root: Path, mode: str, atomic=write_text) -> dict:
    """Record the chosen mode and prepare the docs tree for it. Idempotent."""
    if mode not in MODES:
        raise ValueError(f"Unknown docs mode: {mode}")
    project_root = Path(project_root)
    artifact_root = project_root / "docs" / "artifact"
    for domain in artifacts.DOMAINS:
        target = artifact_root / domain
        paths.inspect(target, missing=True)
        target.mkdir(parents=True, exist_ok=True)
        paths.inspect(target)
    ensure_docs_block(project_root, atomic)
    # Leaving local mode removes only Agent Factory's own root block.
    ensure_block(project_root / ".gitignore", ROOT_RULES if mode == "local" else None, atomic)
    paths.write(_settings(runtime_root), {"schemaVersion": 1, "mode": mode})
    return status(project_root, runtime_root)
