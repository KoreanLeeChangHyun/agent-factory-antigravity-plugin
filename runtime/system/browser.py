"""Discover an existing Playwright installation without installing dependencies."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from storage.errors import ContractError


def managed_test_tools(home=None) -> tuple[Path, Path]:
    """The recommended Playwright package and browser folder under the Agent Factory home (Providers installs them)."""
    from storage.paths import home_path
    root = home_path(home) / "tools"
    return root / "testing" / "node_modules" / "playwright", root / "browsers"


def browser_environment(environment: dict, home=None) -> dict:
    """Use the recommended browser folder once it exists, so captures launch the Chromium Providers installed."""
    _, browsers = managed_test_tools(home)
    if browsers.is_dir():
        environment.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browsers))
    return environment


def playwright_module(project_root: Path) -> str:
    explicit = os.environ.get("PLAYWRIGHT_MODULE")
    if explicit:
        return explicit
    managed, _ = managed_test_tools()
    if (managed / "package.json").is_file():
        return str(managed)
    candidates = []
    home = Path.home().resolve()
    for directory in [project_root.resolve(), *project_root.resolve().parents]:
        candidates.append(directory / "node_modules" / "playwright")
        if directory != project_root.resolve() and directory != Path(directory.anchor):
            try:
                candidates += [child / "node_modules" / "playwright" for child in sorted(directory.iterdir()) if child.is_dir()]
            except OSError:
                pass
        if directory == home:
            break
    try:
        root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=20).stdout.strip()
        if root:
            candidates.append(Path(root) / "playwright")
    except (OSError, subprocess.SubprocessError):
        pass
    for candidate in candidates:
        if (candidate / "package.json").is_file():
            return str(candidate)
    raise ContractError("playwright_unavailable", "No installed Node Playwright was found in the project, its ancestors and their "
                        "sibling projects, or global npm. Set PLAYWRIGHT_MODULE to an installed node_modules/playwright; "
                        "this tool does not install it.")
