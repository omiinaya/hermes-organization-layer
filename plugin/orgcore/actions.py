"""Org actions — the single implementation behind the CLI, slash commands, and agent tools.

Every cmd_* returns a (tag, data) pair; format with _fmt() for text output.
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from . import config
from . import features as orgfeatures
from . import index as orgindex
from . import profiles as orgprofiles
from . import workspace as orgws

# Python 3.12+ supports tarfile.extractall(filter=...) for safe extraction.
_supports_filter = sys.version_info >= (3, 12)


def _root() -> Path:
    cfg = config.load_config(config.default_workspace_root())
    return Path(cfg["workspace"]).expanduser()


def cmd_init(workspace: str | None = None) -> tuple:
    root = Path(workspace).expanduser() if workspace else _root()
    return "init", orgws.init(root)


def cmd_index() -> tuple:
    root = _root()
    cfg = config.load_config(root)
    # Auto-register Hermes profiles into the workspace so the index always
    # reflects live wiring (new profiles appear; descriptions refresh).
    reg = orgprofiles.register(root, cfg)
    report = orgindex.write_index(root, cfg)
    report["profiles"] = {"created": reg["created"], "updated": reg["updated"]}
    return "INDEX OK", report


def cmd_profiles() -> tuple:
    """List registered Hermes profiles with their routing metadata."""
    root = _root()
    cfg = config.load_config(root)
    _maybe_refresh_index(root, cfg)  # keep the index honest before listing
    reg = orgprofiles.register(root, cfg)  # ensure all live profiles are present
    items = []
    for raw in orgws.list_entries(root, cfg):
        if raw["kind"] != "profiles":
            continue
        meta = config.load_meta(raw["dir"])
        items.append({
            "name": raw["name"],
            "rel_path": raw["rel_path"],
            "status": meta.get("status", "active"),
            "purpose": meta.get("description") or meta.get("purpose", ""),
            "model": meta.get("model", ""),
            "when_to_use": meta.get("when_to_use", ""),
            "launch": meta.get("launch", ""),
            "tools": meta.get("tools", []),
            "venvs": meta.get("venvs", []),
            "is_active": meta.get("is_active", False),
        })
    return "PROFILES", {"registered": reg["profiles"], "items": items}


def cmd_suggest(task: str) -> tuple:
    """Suggest which profile to use for a workload/task description."""
    res = orgprofiles.suggest(str(_root()), task)
    return "SUGGEST", res


def cmd_set_profile(name: str, **fields) -> tuple:
    """Update routing fields (model, when_to_use, tools, notes...) on a profile."""
    res = orgprofiles.set_entry(_root(), name, **fields)
    if res["ok"]:
        cfg = config.load_config(_root())
        orgindex.write_index(_root(), cfg)
    return "PROFILE SET", res


def cmd_features() -> tuple:
    """Feature-coverage gate: which Hermes capabilities are in use, and verdict."""
    report = orgfeatures.probe()
    return ("FEATURE GATE" if report["ok"] else "FEATURE GATE (not ready)",
            report)


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
    _maybe_refresh_index(root, cfg)
    items = orgindex.build_items(root, cfg)
    counts: dict[str, int] = {}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    flagged = [it for it in items if it["status"] in ("stale", "expired-scratch")]
    return "STATUS", {"workspace": str(root), "total": len(items), "counts": counts, "flagged": flagged}


def _find_entry(root: Path, name: str) -> dict | None:
    """Locate a managed entry by name (first match across kinds)."""
    for raw in orgws.list_entries(root):
        if raw["name"] == name:
            return raw
    return None


def _run_entry(root: Path, name: str) -> dict:
    """Run the entry_points recorded in <name>/.org.json (in the entry's dir).

    Shared by /org run and /org find --run. Returns a result dict suitable for
    the _fmt RUN renderer.
    """
    target = _find_entry(root, name)
    if target is None:
        return {"ok": False, "error": f"no entry named '{name}' in workspace"}
    meta = config.load_meta(target["dir"])
    entry_points = meta.get("entry_points") or []
    if not entry_points:
        return {"ok": False, "error": f"'{name}' has no entry_points recorded"}
    results = []
    for raw_cmd in entry_points:
        try:
            argv = shlex.split(raw_cmd)
            proc = subprocess.run(argv, cwd=target["dir"], capture_output=True, text=True)
            results.append({
                "command": raw_cmd,
                "exit": proc.returncode,
                "stdout": (proc.stdout or "").strip()[:500],
                "stderr": (proc.stderr or "").strip()[:500],
            })
        except Exception as e:
            results.append({"command": raw_cmd, "exit": None, "error": str(e)})
    ok = all(r.get("exit") == 0 for r in results)
    return {"ok": ok, "entry": name, "results": results}


def _index_is_stale(root: Path, cfg: dict) -> bool:
    """True when index.json is missing or older than the newest on-disk entry.

    Lets convenience reads (find/status/check/profiles) transparently refresh a
    stale index so the agent never has to remember `org index` by hand.
    """
    index_file = root / "index.json"
    if not index_file.exists():
        return True
    try:
        index_mtime = index_file.stat().st_mtime
    except OSError:
        return True
    for raw in orgws.list_entries(root, cfg):
        mtime = orgindex._entry_mtime_float(raw["dir"])  # entry root + 1 level
        if mtime > index_mtime:
            return True
    return False


def _maybe_refresh_index(root: Path, cfg: dict) -> bool:
    """Rebuild the index when stale; returns True if a refresh happened."""
    if not _index_is_stale(root, cfg):
        return False
    orgprofiles.register(root, cfg)
    orgindex.write_index(root, cfg)
    return True


def cmd_find(query: str, auto: bool = False) -> tuple:
    root = _root()
    cfg = config.load_config(root)
    _maybe_refresh_index(root, cfg)  # implicit refresh: search latest disk state
    items = orgindex.build_items(root, cfg)
    q = query.strip().lower()
    hits = [it for it in items
            if q in it["name"].lower() or q in it["purpose"].lower()
            or any(q in t.lower() for t in it["tags"])]
    if auto and hits:
        # Convenience: auto-run the top hit's recorded entry_points.
        run = _run_entry(root, hits[0]["name"])
        return "FIND", {"hits": hits, "auto_ran": run}
    return "FIND", hits


def cmd_prune(dry_run: bool = True, apply: bool = False) -> tuple:
    """Hygiene. dry-run (default) shows exactly which tarballs WOULD be created.

    Only ``expired-scratch`` entries move under the default ``flag`` policy;
    ``stale`` entries are flagged but kept on disk (they are only archived when
    ``stale_policy == auto``). apply=True performs the move to _archive/.
    """
    root = _root()
    cfg = config.load_config(root)
    items = orgindex.build_items(root, cfg)
    auto = cfg["policy"].get("stale_policy") == "auto"
    candidates = [it for it in items if it["status"] in ("stale", "expired-scratch")]

    # Which candidates actually move under the current policy?
    will_move = [it for it in candidates
                 if it["status"] == "expired-scratch" or (auto and it["status"] == "stale")]

    if not apply:
        archive_dir = root / "_archive"
        preview = []
        for it in will_move:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            preview.append({
                "rel_path": it["rel_path"],
                "status": it["status"],
                "dest": str(archive_dir / f"{it['name']}-{stamp}.tar.gz"),
            })
        return "PRUNE (dry-run)", {
            "flagged": candidates,
            "would_archive": preview,
            "auto_policy": auto,
            "note": ("flag-only policy: stale entries are flagged, not moved; "
                     "only expired-scratch (and stale under auto) would be archived. "
                     "Nothing was changed on disk."),
        }

    moved: list[str] = []
    failures: list[str] = []
    archive_dir = root / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    for it in will_move:
        src = root / it["rel_path"]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        dest = archive_dir / f"{it['name']}-{stamp}.tar.gz"
        try:
            with tarfile.open(dest, "w:gz") as tar:
                tar.add(src, arcname=it["rel_path"])
            shutil.rmtree(src)
            moved.append(str(dest))
        except Exception as e:
            failures.append(f"{it['rel_path']}: {e}")
            try:
                dest.unlink(missing_ok=True)
            except Exception:
                pass
    # hygiene always keeps the index honest after a mutation
    orgindex.write_index(root, cfg)
    res = {"moved": moved}
    if failures:
        res["ok"] = False
        res["failures"] = failures
    return "PRUNE", res


def _archives(root: Path) -> list[Path]:
    archive_dir = root / "_archive"
    if not archive_dir.is_dir():
        return []
    return sorted(archive_dir.glob("*.tar.gz"), key=lambda p: p.name)


def cmd_restore(name: str) -> tuple:
    """Unpack the most recent _archive/<name>-*.tar.gz back to its original path.

    Deletes the tarball only after a fully successful extraction (the entry is
    live again). If the target path already exists it is not overwritten.
    """
    root = _root()
    name = (name or "").strip()
    if not name:
        return "RESTORE", {"ok": False, "error": "Usage: restore <name>"}

    matches = [p for p in _archives(root) if p.name.startswith(f"{name}-")]
    if not matches:
        return "RESTORE", {"ok": False, "error": f"no archived tarball for '{name}' in _archive/"}
    pick = matches[-1]

    # Predict the entry's directory so we never overwrite live work.
    rel_dir = None
    try:
        with tarfile.open(pick, "r:gz") as tar:
            members = tar.getmembers()
            top = Path(next((m.name for m in members if m.name), "")).parts
            if top:
                rel_dir = str(Path(*top[:2]))  # e.g. "scratch/junk"
    except Exception as e:
        return "RESTORE", {"ok": False, "error": f"unreadable tarball {pick.name}: {e}"}

    if rel_dir and (root / rel_dir).exists():
        return "RESTORE", {"ok": False,
                           "error": f"'{rel_dir}' already exists on disk — refusing to overwrite. "
                                    f"Move or remove it, or inspect {pick.name} first."}

    try:
        with tarfile.open(pick, "r:gz") as tf:
            for m in tf.getmembers():
                target = (root / m.name).resolve()
                if not str(target).startswith(str(root.resolve())) and target != root.resolve():
                    raise ValueError(f"tarball member escapes workspace: {m.name}")
            kwargs = {}
            if hasattr(tf, "extractall") and _supports_filter:
                kwargs["filter"] = "data"  # Python 3.12+ safe extraction (rejects device files, etc.)
            tf.extractall(root, **kwargs)
        pick.unlink()
    except Exception as e:
        return "RESTORE", {"ok": False, "error": f"restore failed: {e}"}

    orgindex.write_index(root, _root_config())
    return "RESTORE", {"ok": True, "restored": rel_dir or name, "tarball": pick.name}


def _root_config() -> dict:
    return config.load_config(_root())


def cmd_check() -> tuple:
    """Drift check between the persisted index snapshot and what is on disk.

    Reads the last-saved ``index.json`` (if any) and the current directory tree,
    then reports: index records whose dir has vanished, directories on disk that
    the index never saw, and absolute-path leaks in per-entry metadata (privacy
    violations under strict mode).
    """
    root = _root()
    cfg = config.load_config(root)
    items = orgindex.build_items(root, cfg)
    on_disk = orgws.list_entries(root, cfg)
    disk_rel = {raw["rel_path"] for raw in on_disk}

    # Detached (missing on disk but listed in the last-saved index snapshot).
    saved: dict = {}
    index_file = root / "index.json"
    if index_file.exists():
        try:
            saved = json.loads(index_file.read_text(encoding="utf-8"))
        except Exception:
            saved = {}
    saved_rel = {it.get("rel_path") for it in saved.get("items", []) if it.get("rel_path")}
    missing_dirs = sorted(rp for rp in saved_rel if rp not in disk_rel)

    # Unindexed (on disk in a live local index pass, not in the snapshot).
    live_rel = {it["rel_path"] for it in items}
    unindexed = sorted(rp for rp in disk_rel if rp not in live_rel)

    # Privacy leaks inside per-entry metadata.
    leaky = sorted(raw["rel_path"] for raw in on_disk
                   if _meta_leaks_abs_path(config.load_meta(raw["dir"])))

    statuses: dict[str, int] = {}
    for it in items:
        statuses[it["status"]] = statuses.get(it["status"], 0) + 1

    report = {
        "ok": not (missing_dirs or unindexed or leaky),
        "indexed": len(items),
        "on_disk": len(on_disk),
        "missing_dirs": missing_dirs,
        "unindexed": unindexed,
        "privacy_leaks": leaky,
        "status_counts": statuses,
        "archives": [p.name for p in _archives(root)],
    }
    return "CHECK", report


def _meta_leaks_abs_path(meta: dict) -> bool:
    """True when any string value in meta is an absolute native path."""
    blob = json.dumps(meta)
    return bool(re.search(r'(?i)([a-z]:[\\/]|/(Users|home|root)/)', blob))


def cmd_run(name: str) -> tuple:
    """Run the entry_points recorded in <name>/.org.json (in the entry's dir)."""
    return "RUN", _run_entry(_root(), name)


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
                    if isinstance(vv, list) and vv and isinstance(vv[0], dict):
                        lines.append(f"  - {kk}:")
                        for it in vv[:20]:
                            lines.append(_fmt_entry_line(it, indent=2))
                    else:
                        lines.append(f"  - {kk}: {vv}")
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                lines.append(f"- {k}:")
                for it in v[:20]:
                    lines.append(_fmt_entry_line(it, indent=2))
            elif isinstance(v, list) and v:
                lines.append(f"- {k}:")
                for it in v[:20]:
                    lines.append(f"  - {it}")
            else:
                lines.append(f"- {k}: {v}")
    elif isinstance(data, str):
        lines.append(data)
    elif isinstance(data, list):
        for it in data[:20]:
            if isinstance(it, dict):
                lines.append(_fmt_entry_line(it, indent=0))
            else:
                lines.append(f"- {it}")
    return "\n".join(lines)


def _fmt_entry_line(it: dict, indent: int = 0) -> str:
    """Format one list item (index entry, run result, archive plan, profile) on a line."""
    pad = "  " * indent
    if "command" in it:  # cmd_run result
        line = f"{pad}- `{it['command']}`"
        line += f" [exit {it.get('exit')}]" if it.get("exit") is not None else " [failed to start]"
        if it.get("stdout"):
            line += f" → {it['stdout'][:200]}"
        if it.get("stderr"):
            line += f" ! {it['stderr'][:120]}"
        return line
    if "capability" in it:  # feature-gate capability
        status = str(it.get("status", ""))
        badge = {"ok": "✓", "warn": "△", "missing": "✗"}.get(status, "?")
        tier = str(it.get("tier", ""))
        line = f"{pad}- {badge} {it['capability']} [{tier}] — {it.get('detail', '')}"
        if it.get("hint"):
            line += f"  ({it['hint']})"
        return line
    if "dest" in it:  # prune preview
        line = f"{pad}- `{it.get('rel_path', it.get('name', ''))}` [{it.get('status', '')}]"
        line += f" → {it['dest']}"
        return line
    line = f"{pad}- `{it.get('rel_path', it.get('name', ''))}` [{it.get('status', '')}]"
    p = it.get("purpose") or it.get("description") or ""
    line += (f" — {p}" if p else "")
    if it.get("score") is not None:
        line += f" (score {it['score']})"
    if it.get("is_active"):
        line += " ⬢active"
    if it.get("model"):
        line += f" · model: {it['model']}"
    if it.get("when_to_use"):
        line += f" · when: {it['when_to_use']}"
    if it.get("launch"):
        line += f" · launch: {it['launch']}"
    if it.get("entry_points"):
        line += f" · entry: {', '.join(it['entry_points'])}"
    if it.get("tools"):
        tool_txt = ", ".join(
            f"{t.get('name', t)}" + (f"→{t.get('profile', '')}" if t.get("profile") else "")
            for t in it["tools"] if isinstance(t, dict))
        if tool_txt:
            line += f" · tools: {tool_txt}"
    if it.get("venvs"):
        venv_txt = ", ".join(
            f"{x['path']} ({x['version']})" if x.get("version") else x["path"]
            for x in it["venvs"])
        line += f" · venv: {venv_txt}"
    return line