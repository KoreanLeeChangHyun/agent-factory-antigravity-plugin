"""Fixed artifact domains; validation never creates or repairs directories."""
from __future__ import annotations

import os
from pathlib import Path

DOMAINS = ("output", "media", "data", "model", "software", "interactive", "evidence", "release", "other")
CONTROL_FILES = ("index.json",)


def _unlinked(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f"Artifact paths cannot use symlinks: {part}")


def artifact_output(value: Path, project_root: Path, *, required: bool = False) -> Path:
    """Validate flat output when under docs/artifact; allow named external outputs."""
    raw = value.expanduser() if value.is_absolute() else project_root / value
    roots = [p for p in raw.parents if p.name == "artifact" and p.parent.name == "docs"]
    resolved = Path(os.path.realpath(raw))
    roots += [p for p in resolved.parents if p.name == "artifact" and p.parent.name == "docs"]
    expected = project_root / "docs" / "artifact"
    if required:
        roots.append(expected)
    if not roots:
        return raw
    if ".." in raw.parts:
        raise ValueError("Artifact paths cannot contain '..'.")
    path = Path(os.path.abspath(raw))
    _unlinked(path)
    artifact = expected if required else roots[0]
    if not path.is_relative_to(artifact):
        raise ValueError("Output must stay inside the project docs/artifact directory.")
    parts = path.relative_to(artifact).parts
    if len(parts) != 2 or parts[0] not in DOMAINS:
        raise ValueError("Output must be docs/artifact/<fixed-domain>/<filename>; nested directories are forbidden.")
    if not path.parent.is_dir():
        raise ValueError("Artifact domain directory must already exist.")
    return path


def layout_errors(root: Path) -> list[str]:
    """Return structural violations, including empty or symlinked extra directories."""
    try:
        _unlinked(root)
    except ValueError as error:
        return [str(error)]
    if not root.is_dir():
        return [f"Missing artifact root: {root}"]
    errors = []
    for name in DOMAINS:
        if not (root / name).is_dir():
            errors.append(f"Missing domain: {name}")
    for entry in sorted(root.iterdir()):
        if entry.is_symlink():
            errors.append(f"Symlink forbidden: {entry.name}")
        elif entry.name in DOMAINS and entry.is_dir():
            for child in sorted(entry.iterdir()):
                if child.is_symlink() or not child.is_file():
                    errors.append(f"Only regular files allowed: {entry.name}/{child.name}")
        elif entry.name not in CONTROL_FILES or not entry.is_file():
            errors.append(f"Unexpected root entry: {entry.name}")
    return errors
