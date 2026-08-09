"""Org actions — the single implementation behind the CLI, slash commands, and agent tools.

Every cmd_* returns a (tag, data) pair; format with _fmt() for text output.
"""

from __future__ import annotations

import json
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from . import config
from . import index as orgindex
from . import workspace as orgws


def _root() -> Path:
    cfg = config.load_config(config.default_workspace_root())
    return Path(cfg["workspace"]).expanduser()


def cmd_init(workspace: str | None = None) -> tuple:
    root = Path(workspace).expanduser() if workspace else _root()
    return "init", orgws.init(root)


def cmd_index() -> tuple:
    root = _root()
    cfg = config.load_config(root)
    report = orgindex.write_index(root, cfg)
    return "INDEX OK", report


def cmd_new(kind: str, name: str, purpose: str = "", tags: list[str] | None = None) -> tuple:
    root = _root()
    res = orgws.new_entry(root, kind, name, purpose=purpose, tags=tags)
    if res["ok"]:
        cfg = config.load_config(root)
        orgindex.write_index(root, cfg)
    return "NEW", res


def cmd_status() -> tuple:
    root = _root()
    cfg = config.load_config(root)
    items = orgindex.build_items(root, cfg)
    counts: dict[str, int] = {}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    flagged = [it for it in items if it["status"] in ("stale", "expired-scratch")]
    return "STATUS", {"workspace": str(root), "total": len(items), "counts": counts, "flagged": flagged}


def cmd_find(query: str) -> tuple:
    root = _root()
    cfg = config.load_config(root)
    items = orgindex.build_items(root, cfg)
    q = query.strip().lower()
    hits = [it for it in items
            if q in it["name"].lower() or q in it["purpose"].lower()
            or any(q in t.lower() for t in it["tags"])]
    return "FIND", hits


def cmd_prune(dry_run: bool = True, apply: bool = False) -> tuple:
    root = _root()
    cfg = config.load_config(root)
    items = orgindex.build_items(root, cfg)
    policy = cfg["policy"]
    candidates = [it for it in items if it["status"] in ("stale", "expired-scratch")]

    if not apply:
        return "PRUNE (dry-run)", {
            "candidates": candidates,
            "note": "flag-only policy: nothing is deleted; apply moves items into _archive/",
        }

    auto = policy.get("stale_policy") == "auto"
    moved: list[str] = []
    archive_dir = root / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    for it in candidates:
        if it["status"] == "expired-scratch" or auto:
            src = root / it["rel_path"]
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            dest = archive_dir / f"{it['name']}-{stamp}.tar.gz"
            try:
                with tarfile.open(dest, "w:gz") as tar:
                    tar.add(src, arcname=it["rel_path"])
                shutil.rmtree(src)
                moved.append(str(dest))
            except Exception as e:
                return "PRUNE", {"ok": False, "error": str(e)}
    return "PRUNE (applied)", {"moved": moved}


def cmd_show_config() -> tuple:
    return "ORG CONFIG", config.load_config(_root())


def _fmt(tag: str, data) -> str:
    """Render an action report to a compact text block (English only)."""
    lines = [f"**{tag}**"]
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                lines.append(f"- {k}:")
                for kk, vv in v.items():
                    lines.append(f"  - {kk}: {vv}")
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                lines.append(f"- {k}:")
                for it in v[:20]:
                    line = f"  - `{it.get('rel_path', it.get('name', ''))}` [{it.get('status', '')}]"
                    p = it.get("purpose", "")
                    line += (f" — {p}" if p else "")
                    if it.get("venvs"):
                        venv_txt = ", ".join(
                            f"{x['path']} ({x['version']})" if x.get("version") else x["path"]
                            for x in it["venvs"])
                        line += f" · venv: {venv_txt}"
                    lines.append(line)
            else:
                lines.append(f"- {k}: {v}")
    elif isinstance(data, str):
        lines.append(data)
    elif isinstance(data, list):
        for it in data[:20]:
            if isinstance(it, dict):
                line = f"- `{it.get('rel_path', it.get('name', ''))}` [{it.get('status', '')}]"
                p = it.get("purpose", "")
                line += (f" — {p}" if p else "")
                if it.get("venvs"):
                    venv_txt = ", ".join(
                        f"{x['path']} ({x['version']})" if x.get("version") else x["path"]
                        for x in it["venvs"])
                    line += f" · venv: {venv_txt}"
                lines.append(line)
            else:
                lines.append(f"- {it}")
    return "\n".join(lines)