"""Scaffold an org workspace and create managed entries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import config


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_meta(kind: str, name: str) -> dict:
    return {
        "name": name,
        "kind": kind,
        "purpose": "",
        "tags": [],
        "status": "active",          # active | stale | scratch | archived
        "entry_points": [],
        "venvs": [],                 # optional explicit list: [{"path": ".venv", "version": "3.12"}]
        "created": utcnow(),
        "notes": "",
    }


def init(root: Path) -> dict:
    """Create the workspace skeleton + config (idempotent). Returns a report."""
    root = Path(root).expanduser()
    cfg = config.load_config(root)
    created: list[str] = []
    for folder in cfg["folders"]:
        (root / folder).mkdir(parents=True, exist_ok=True)
        created.append(folder)
    org_dir = root / config.ORG_DIR_NAME
    org_dir.mkdir(parents=True, exist_ok=True)
    config.save_config(root, cfg)

    root_readme = root / "README.org.md"
    if not root_readme.exists():
        root_readme.write_text(
            "# Org workspace\n\n"
            "Managed by the hermes-organization-layer plugin.\n"
            "Run `org index` to refresh INDEX.md. See INDEX.md for a map of everything here.\n",
            encoding="utf-8",
        )
    return {
        "ok": True,
        "workspace": str(root),
        "folders": cfg["folders"],
        "created": created,
        "config_file": str(config.config_path(root)),
    }


def new_entry(root: Path, kind: str, name: str, purpose: str = "",
              status: str = "active", tags: list[str] | None = None) -> dict:
    """Create a new entry under <kind>/<name> with a metadata stub (idempotent)."""
    cfg = config.load_config(root)
    kind = (kind or "").strip().lower()
    if kind not in cfg["folders"]:
        return {"ok": False, "error": f"Unknown kind '{kind}'. Known: {', '.join(cfg['folders'])}"}
    name = (name or "").strip()
    if not name or "/" in name or "\\" in name:
        return {"ok": False, "error": "Entry name must be a single simple identifier."}

    entry_dir = root / kind / name
    entry_dir.mkdir(parents=True, exist_ok=True)

    meta = _default_meta(kind, name)
    if purpose:
        meta["purpose"] = purpose
    if tags:
        meta["tags"] = [str(t) for t in tags]
    meta.setdefault("status", "active" if kind != "scratch" else "scratch")

    meta_file = config.meta_path(entry_dir)
    if not meta_file.exists():
        meta_file.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        (entry_dir / "README.md").touch(exist_ok=True)
    return {"ok": True, "path": str(entry_dir), "meta_file": str(meta_file)}


def list_entries(root: Path, cfg: dict | None = None) -> list[dict]:
    """Enumerate managed entries (folders that look like org entries)."""
    cfg = cfg or config.load_config(root)
    entries: list[dict] = []
    for folder in cfg["folders"]:
        fdir = root / folder
        if not fdir.is_dir():
            continue
        for child in sorted(fdir.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith(".") or child.name in cfg["excludes"]:
                continue
            entries.append({
                "rel_path": str(child.relative_to(root)),
                "kind": folder,
                "name": child.name,
                "dir": child,
            })
    return entries


def _org() -> str:
    return config.ORG_DIR_NAME