"""Build the org index: index.json (machine) + INDEX.md (human)."""

from __future__ import annotations

import fnmatch
import json
from datetime import datetime, timezone
from pathlib import Path

from . import config
from . import workspace


def _is_excluded(name: str, cfg: dict) -> bool:
    if name.startswith("."):
        return True
    if name in cfg["excludes"]:
        return True
    return any(fnmatch.fnmatch(name, p) for p in cfg["excludes"])


def _entry_mtime_float(entry: Path) -> float:
    """Most recent mtime among the entry root and one level of children."""
    try:
        mtimes = [entry.stat().st_mtime]
        for child in entry.iterdir():
            try:
                mtimes.append(child.stat().st_mtime)
            except OSError:
                pass
        return max(mtimes)
    except OSError:
        return 0.0


def _entry_mtime_iso(entry: Path) -> str:
    m = _entry_mtime_float(entry)
    if not m:
        return ""
    return datetime.fromtimestamp(m, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _days_ago(mtime: float) -> int | None:
    if not mtime:
        return None
    return int((datetime.now(timezone.utc).timestamp() - mtime) // 86400)


def _dir_size(entry: Path) -> int:
    total = 0
    try:
        for p in entry.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except OSError:
                pass
    except Exception:
        pass
    return total


# -- venv detection ---------------------------------------------------------
# A directory containing `pyvenv.cfg` is a Python virtual environment.
# We scan the entry root plus two levels of subdirectories (bounded, so huge
# project trees stay cheap) and record each venv's relative path + Python version.

def _pyvenv_version(pyvenv_cfg: Path) -> str:
    try:
        for line in pyvenv_cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("version") and "=" in line:
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def _scan_venvs(dir_path: Path, rel: str, depth: int, max_depth: int, out: list) -> None:
    if depth > max_depth:
        return
    try:
        for child in sorted(dir_path.iterdir()):
            if child.name in ("node_modules", "__pycache__"):
                continue
            if child.name.startswith(".") and child.name != ".venv":
                continue
            if child.is_dir():
                _scan_venvs(child, f"{rel}/{child.name}" if rel else child.name, depth + 1, max_depth, out)
            elif child.name == "pyvenv.cfg":
                out.append({"path": rel or ".", "version": _pyvenv_version(child)})
    except OSError:
        pass


def detect_venvs(entry: Path, max_depth: int = 2) -> list[dict]:
    out: list[dict] = []
    _scan_venvs(entry, "", 0, max_depth, out)
    return out


def merge_venvs(detected: list[dict], explicit: list) -> list[dict]:
    """Explicit .org.json `venvs` entries win; auto-detected ones fill gaps."""
    by_path = {str(v.get("path", "")): v for v in explicit if isinstance(v, dict) and v.get("path")}
    for v in detected:
        by_path.setdefault(str(v.get("path", "")), v)
    return list(by_path.values())


def build_items(root: Path, cfg: dict) -> list[dict]:
    policy = cfg["policy"]
    items: list[dict] = []
    for raw in workspace.list_entries(root, cfg):
        entry: Path = raw["dir"]
        meta: dict = {}
        meta_file = config.meta_path(entry)
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8")) or {}
            except Exception:
                meta = {}

        mtime = _entry_mtime_float(entry)
        age_days = _days_ago(mtime)

        status = str(meta.get("status", "active"))
        if raw["kind"] == "scratch":
            status = "expired-scratch" if age_days is not None and age_days > int(
                policy.get("scratch_ttl_days", 30)) else "scratch"
        elif age_days is not None and age_days > int(policy.get("stale_after_days", 90)):
            if status not in ("stale", "archived"):
                status = "stale"

        items.append({
            "rel_path": raw["rel_path"],
            "kind": raw["kind"],
            "name": raw["name"],
            "purpose": str(meta.get("purpose", "") or ""),
            "tags": meta.get("tags", []) or [],
            "status": status,
            "last_activity": _entry_mtime_iso(entry),
            "entry_points": meta.get("entry_points", []) or [],
            "venvs": merge_venvs(detect_venvs(entry), meta.get("venvs") or []),
            "size_bytes": _dir_size(entry),
        })
    return items


def generate_payload(items: list[dict], cfg: dict) -> dict:
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "workspace": cfg["workspace"],
        "language": cfg.get("language", "en"),
        "policy": cfg["policy"],
        "items": items,
    }


def write_index(root: Path, cfg: dict) -> dict:
    items = build_items(root, cfg)
    (root / "index.json").write_text(
        json.dumps(generate_payload(items, cfg), indent=2) + "\n", encoding="utf-8")
    (root / "INDEX.md").write_text(render_markdown(items, cfg), encoding="utf-8")
    counts: dict[str, int] = {}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    return {"ok": True, "items": len(items), "counts": counts, "files": ["INDEX.md", "index.json"]}


def render_markdown(items: list[dict], cfg: dict) -> str:
    lines = [
        "# Org Index",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} · "
        f"Workspace: `{cfg['workspace']}`",
        f"Language: {cfg.get('language', 'en')} · {len(items)} entries",
        "",
    ]
    by_kind: dict[str, list[dict]] = {}
    for it in items:
        by_kind.setdefault(it["kind"], []).append(it)

    for kind in cfg["folders"]:
        if kind not in by_kind:
            continue
        lines.append(f"## {kind}/")
        for it in sorted(by_kind[kind], key=lambda x: x["name"]):
            purpose = f" — {it['purpose']}" if it.get("purpose") else ""
            badge = f" `[{it['status']}]`" if it["status"] != "active" else ""
            lines.append(f"- **{it['name']}**{badge}{purpose}")
            if it.get("tags"):
                lines.append(f"  tags: {', '.join(it['tags'])}")
            if it.get("entry_points"):
                lines.append(f"  entry: {', '.join(it['entry_points'])}")
            if it.get("venvs"):
                venv_txt = " · ".join(f"{v['path']} ({v['version']})" if v.get("version")
                                      else v["path"] for v in it["venvs"])
                lines.append(f"  venv: {venv_txt}")
        lines.append("")

    flagged = [it for it in items if it["status"] in ("stale", "expired-scratch")]
    if flagged:
        lines.append("## Needs attention")
        for it in flagged:
            lines.append(f"- `{it['rel_path']}` — {it['status']}")
        lines.append("")
    return "\n".join(lines) + "\n"