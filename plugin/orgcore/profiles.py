"""Profile domain — auto-register Hermes profiles into the org index for routing.

Hermes already creates/describes/uses profiles natively (`hermes profile create`,
`hermes profile describe`, `hermes -p <name>`). This module does NOT redefine
profiles; it *indexes* them so there is one place to answer "what profile do I
use, for what, with which tools/venv" — the routing table the org layer concept
is built on.

Conventions
-----------
- The active (default) profile home is ``$HERMES_HOME`` itself (no profile.yaml).
- A non-default profile ``<name>`` lives at ``$HERMES_HOME/profiles/<name>/`` with a
  ``profile.yaml`` carrying a free-text ``description`` (what it's good for),
  which the registry saves into the routed entry.
- Each discovered profile is registered in the workspace as a ``profiles/<name>``
  entry whose ``.org.json`` carries routing fields: model, when_to_use, launch,
  and an optional ``tools`` list tying tools to their path/venv/profile.

Everything here is pure stdlib, English-only, cross-platform, and reads live
wiring (``$HERMES_HOME`` + the Hermes registry) rather than a hardcoded root.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import config as orgconfig
from . import workspace as orgws


def _dump(obj: dict) -> str:
    return json.dumps(obj, indent=2) + "\n"


def hermes_home() -> Path:
    """Resolve $HERMES_HOME (or the platform default ~/.hermes)."""
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".hermes"


def discover() -> list[dict]:
    """Enumerate Hermes profiles (active default + every profiles/<name>).

    Returns a list of dicts: {name, home, is_active, description, launch}.
    Never raises on a missing/invalid profile home — discovery is best-effort.
    """
    root = hermes_home()
    found: list[dict] = []
    # The active profile has no name — it IS the home root. Report as "default".
    active = {
        "name": "default",
        "home": str(root),
        "is_active": True,
        "description": "",
        "launch": "hermes",
    }
    profiles_dir = root / "profiles"
    found.append(active)

    if profiles_dir.is_dir():
        for child in sorted(profiles_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            desc = _read_description(child)
            found.append({
                "name": child.name,
                "home": str(child),
                "is_active": False,
                "description": desc,
                "launch": f"hermes -p {child.name}",
            })
    return found


def _read_description(prof_dir: Path) -> str:
    pymd = prof_dir / "profile.yaml"
    if pymd.exists():
        try:
            text = pymd.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("description:"):
                    return line.split(":", 1)[1].strip().strip("'\"")
        except Exception:
            pass
    soul = prof_dir / "SOUL.md"
    if soul.exists():
        try:
            return soul.read_text(encoding="utf-8", errors="replace").strip()[:200]
        except Exception:
            pass
    return ""


def register(root: Path, cfg: dict, force: bool = False) -> dict:
    """Auto-register discovered Hermes profiles into <root>/profiles/<name>.

    Creates a ``profiles/<name>`` entry (dir + routing .org.json) for every
    profile that isn't already present, seeding it from the profile description.
    Existing entries are preserved (so user routing edits like when_to_use/tools
    survive). Returns a report.
    """
    root = Path(root).expanduser()
    created: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []

    for prof in discover():
        name = prof["name"]
        entry_dir = root / "profiles" / name
        meta_file = orgconfig.meta_path(entry_dir)

        # Seed from profile description every time we can (cheap, keeps intent
        # readable); never overwrite when_to_use/tools/model that were authored.
        seed = {
            "name": name,
            "kind": "profiles",
            "version": 1,
            "purpose": prof["description"],
            "model": "",
            "when_to_use": "",
            "launch": prof["launch"],
            "is_active": prof["is_active"],
            "tools": [],  # [{name, path, venv, profile}]
            "tags": [],
            "venvs": [],
            "status": "active",
            "entry_points": [prof["launch"]],
            "notes": "",
        }
        # NOTE: we deliberately do NOT persist the absolute home path (privacy:
        # strict mode + `org check` scan metas for absolute-path leaks). The
        # launch command is the actionable routing field.

        if not meta_file.exists():
            entry_dir.mkdir(parents=True, exist_ok=True)
            meta_file.write_text(_dump(seed), encoding="utf-8")
            created.append(name)
            continue

        # Existing entry: refresh description/purpose when it has drifted,
        # preserve user-authored routing (when_to_use, model, tools, notes).
        try:
            cur = json.loads(meta_file.read_text(encoding="utf-8")) or {}
        except Exception:
            cur = {}
        cur["name"] = name
        cur["kind"] = "profiles"
        cur["purpose"] = prof["description"]
        cur.setdefault("launch", prof["launch"])
        cur.setdefault("is_active", prof["is_active"])
        meta_file.write_text(json.dumps(cur, indent=2), encoding="utf-8")
        updated.append(name)

    return {
        "ok": True,
        "profiles": [p["name"] for p in discover()],
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }


def set_entry(root: Path, name: str, **fields) -> dict:
    """Update arbitrary routing fields on a registered profile entry."""
    root = Path(root).expanduser()
    meta_file = orgconfig.meta_path(root / "profiles" / name)
    if not meta_file.exists():
        return {"ok": False, "error": f"profile '{name}' not registered"}
    try:
        cur = json.loads(meta_file.read_text(encoding="utf-8")) or {}
    except Exception:
        cur = {}
    for k, v in fields.items():
        if v is not None:
            cur[k] = v
    meta_file.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    return {"ok": True, "name": name, "updated": list(fields.keys())}


def suggest(root: str, task: str) -> dict:
    """Pick the best profile for a task using description/workload matching."""
    root_path = Path(root).expanduser()
    q = (task or "").strip().lower()
    if not q:
        return {"ok": False, "error": "suggest: give a task/workload description"}
    scored: list[tuple] = []
    for prof in discover():
        hay = " ".join([prof["description"], _meta_text(root_path, prof["name"])]).lower()
        score = sum(1 for token in q.split() if token in hay)
        scored.append((score, prof["name"], prof["description"]))
    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[0]
    if top[0] <= 0:
        # no keyword hit -> fall back to the active profile
        return {"ok": True, "profile": "default", "match_score": 0,
                "note": "no strong match; default (active) profile suggested",
                "candidates": [{"name": n, "score": s, "description": d} for s, n, d in scored]}
    return {"ok": True, "profile": top[1], "match_score": top[0],
            "candidates": [{"name": n, "score": s, "description": d} for s, n, d in scored]}


def _meta_text(root: Path, name: str) -> str:
    meta_file = orgconfig.meta_path(root / "profiles" / name)
    if not meta_file.exists():
        return ""
    try:
        return json.dumps(json.loads(meta_file.read_text(encoding="utf-8")))
    except Exception:
        return ""


def index(profile: dict) -> dict:
    """Normalize a discovered profile into an indexable item for INDEX.md."""
    return {
        "rel_path": f"profiles/{profile['name']}",
        "kind": "profiles",
        "name": profile["name"],
        "purpose": profile["description"],
    }