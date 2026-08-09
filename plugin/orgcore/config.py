"""Org workspace configuration — cross-platform defaults, overridable."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Default folder layout. Order matters for INDEX.md rendering.
DEFAULT_FOLDERS: list[str] = [
    "projects",       # cloned repos and active project work
    "test-scripts",   # ad-hoc scripts written while testing/debugging
    "scratch",        # throwaway; TTL-flagged, never auto-deleted by default
    "data",           # datasets, dumps, downloaded artifacts
    "notes",          # markdown notes/knowledge not bound to a project
    "docs",           # documentation not bound to a project
    "assets",         # images, media, binaries
    "_archive",       # pruned items land here (tarballed) — never hard-deleted
]

# Paths never indexed (git, deps, caches).
DEFAULT_EXCLUDES: list[str] = [
    ".git", "node_modules", "__pycache__", ".pytest_cache",
    ".venv", "venv", "env", ".env", "dist", "build", "target",
    ".hermes", ".org", "_archive", ".DS_Store", "*.egg-info", "*.pyc",
]

DEFAULT_POLICY = {
    "stale_policy": "flag",        # "flag" (default) | "auto" (auto-archive)
    "scratch_ttl_days": 30,        # scratch older than this -> flagged expired
    "stale_after_days": 90,        # no activity longer than this -> flagged stale
    "auto_archive_after_days": 120,  # used only when stale_policy == "auto"
}

CONFIG_FILENAME = ".org.json"
META_FILENAME = ".org.json"
ORG_DIR_NAME = ".org"


def default_workspace_root() -> Path:
    """Platform-idiomatic default workspace location.

    Windows: %USERPROFILE%\\Documents\\hermes-org
    macOS:   ~/Documents/hermes-org
    Linux:   ~/Documents/hermes-org if it exists, else ~/hermes-org
    Override with HERMES_ORG_WORKSPACE or the org config.
    """
    env = os.environ.get("HERMES_ORG_WORKSPACE")
    if env:
        return Path(env).expanduser()

    if sys.platform.startswith("win"):
        base = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents"
        return base / "hermes-org"
    if sys.platform == "darwin":
        return Path.home() / "Documents" / "hermes-org"
    # Linux and everything else
    docs = Path.home() / "Documents"
    return (docs if docs.exists() else Path.home()) / "hermes-org"


def default_config() -> dict:
    return {
        "version": 1,
        "workspace": str(default_workspace_root()),
        "folders": list(DEFAULT_FOLDERS),
        "excludes": list(DEFAULT_EXCLUDES),
        "policy": dict(DEFAULT_POLICY),
        "language": "en",
        "privacy": "strict",   # "strict" (default) scrubs absolute machine paths from
                               # index artifacts; "full" keeps absolute paths for debugging.
    }


def load_config(root: Path) -> dict:
    """Load <root>/.org/config.json, merging over defaults (env override wins)."""
    cfg = default_config()
    cfg_path = root / ORG_DIR_NAME / "config.json"
    if cfg_path.exists():
        try:
            saved = json.loads(cfg_path.read_text(encoding="utf-8"))
            for key in ("folders", "excludes", "policy", "version", "language", "privacy"):
                if key in saved:
                    cfg[key] = saved[key]
        except Exception:
            pass  # corrupt config -> fall back to defaults
    env = os.environ.get("HERMES_ORG_WORKSPACE")
    if env:
        cfg["workspace"] = str(Path(env).expanduser())
    return cfg


def save_config(root: Path, cfg: dict) -> None:
    org_dir = root / ORG_DIR_NAME
    org_dir.mkdir(parents=True, exist_ok=True)
    (org_dir / "config.json").write_text(
        json.dumps(cfg, indent=2) + "\n", encoding="utf-8"
    )


def config_path(root: Path) -> Path:
    return root / ORG_DIR_NAME / "config.json"


def meta_path(entry_dir: Path) -> Path:
    """Per-entry metadata file (`.org.json` inside the entry folder)."""
    return entry_dir / META_FILENAME
