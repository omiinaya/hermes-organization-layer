"""Feature-coverage gate — report which Hermes capabilities are in use.

The org layer indexes the workspace and the profiles; this module answers the
"are we using Hermes to its fullest / are we production-safe" question. It
probes live state under ``$HERMES_HOME`` (never hardcoded) and reports each
capability as ok / warn / missing with a one-line hint, then computes an overall
``ready`` verdict.

Purpose: turn the team's "fullest extent" intent into an enforceable gate, the
same way ``org check`` enforces the privacy invariant. Pure stdlib, English-only,
cross-platform; never raises on a missing/invalid path.
"""

from __future__ import annotations

import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from . import profiles as orgprofiles


def _env_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".hermes"


def _config_text(home: Path) -> str:
    try:
        return (home / "config.yaml").read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _memory_provider(cfg_text: str) -> str:
    # Find the `memory:` block, then read its provider/backend/store key.
    mem = re.search(r"(?ms)^\s*memory:\s*\n((?:[ \t]+.*\n?)*)", cfg_text)
    if not mem:
        return ""
    block = mem.group(1)
    m = re.search(r"(?m)^\s*(?:provider|backend|store):\s*(\S+)", block)
    return m.group(1).strip() if m else ""


def _cap(name: str, status: str, detail: str, hint: str, tier: str = "advisory") -> dict:
    if "deadline" in hint and status != "ok":
        hint = hint + " — the feature is installed but not yet enabled/used."
    return {
        "capability": name,
        "status": status,  # ok | warn | missing
        "detail": detail,
        "hint": hint,
        "tier": tier,      # critical | recommended | advisory
    }


def probe(home: Path | None = None, user_home: Path | None = None) -> dict:
    """Probe Hermes capability coverage and return the gate report.

    ``home`` = HERMES_HOME (defaults to the live env/`~/.hermes`).
    ``user_home`` = where `hermes backup` zips land (defaults to `Path.home()`);
    injectable so tests are hermetic.
    """
    home = home or _env_home()
    user_home = user_home or Path.home()
    cfg = _config_text(home)
    caps: list[dict] = []
    now = datetime.now(timezone.utc)

    # ── CRITICAL (hard gate: keep your data safe across restarts) ──────────
    # Backups: latest hermes-backup-*.zip valid zip, recent (<=60 days);
    # also recognize <home>/state-snapshots/ (hermes backup -q output).
    backups = sorted(
        [p for p in user_home.glob("hermes-backup-*.zip")]
        + [p for p in home.glob("hermes-backup-*.zip")],
        key=lambda p: p.stat().st_mtime, reverse=True)
    snap_dir = home / "state-snapshots"
    snap_count = len(list(snap_dir.glob("*/"))) if snap_dir.is_dir() else 0
    if backups:
        latest = backups[0]
        age_d = (now.timestamp() - latest.stat().st_mtime) / 86400
        ok_zip = False
        try:
            with zipfile.ZipFile(latest) as zf:
                ok_zip = zf.testzip() is None
        except Exception:
            ok_zip = False
        if ok_zip and age_d <= 30:
            caps.append(_cap("backups", "ok",
                             f"{latest.name} ({age_d:.1f}d old, valid zip)",
                             "Have backups; refresh monthly or before risky changes.", "critical"))
        elif ok_zip:
            caps.append(_cap("backups", "warn",
                             f"{latest.name} exists but is {age_d:.1f}d old",
                             "Refresh the backup — older than 30 days.", "critical"))
        else:
            caps.append(_cap("backups", "warn",
                             f"{latest.name} is present but not a valid zip",
                             "re-run `hermes backup` and verify with `unzip -t`.", "critical"))
    elif snap_count:
        caps.append(_cap("backups", "ok",
                         f"{snap_count} state snapshot(s) in state-snapshots/",
                         "Quick snapshot exists; consider a full `hermes backup` zip too.", "critical"))
    else:
        caps.append(_cap("backups", "missing", "no hermes-backup-*.zip or state snapshot found",
                         "run `hermes backup` to create one", "critical"))

    # Checkpoints: shadow-git rollback snapshots fill as files get edited.
    cps = home / "checkpoints"
    cp_files = list(cps.rglob("*")) if cps.is_dir() else []
    if cp_files:
        caps.append(_cap("checkpoints", "ok", f"{len(cp_files)} checkpoint file(s)",
                     "file-edit rollback history available", "critical"))
    else:
        caps.append(_cap("checkpoints", "warn", "checkpoint store is empty",
                     "rollback history fills automatically as workspace files are edited; "
                     "empty now means no edits have been checkpointed yet", "critical"))

    # Memory provider is wired (data must survive restart via the managed store).
    prov = _memory_provider(cfg)
    if prov and prov not in ("none", "local"):
        caps.append(_cap("memory_provider", "ok", f"provider={prov}",
                     "managed memory store active", "critical"))
    else:
        caps.append(_cap("memory_provider", "missing" if not prov else "warn",
                     f"provider={prov or 'unset'}",
                     "configure a persistent memory provider (memory-tencentdb)", "critical"))

    # ── Recommended (fullest-extent, medium value) ─────────────────────────
    cron_files = list(home.glob("cron/*.json")) if (home / "cron").is_dir() else []
    if cron_files:
        caps.append(_cap("cron", "ok", f"{len(cron_files)} cron job(s)",
                     "scheduled jobs present", "recommended"))
    else:
        caps.append(_cap("cron", "missing", "no cron jobs configured",
                     "schedule watchdogs/briefings with `cronjob`", "recommended"))

    # MCP servers (external tool/networking surface).
    mcp = home / "mcp"
    mcp_n = len(list(mcp.glob("**/*.json"))) if mcp.is_dir() else 0
    mcp_cfg = re.search(r"(?m)^\s*mcp[_:]?\s*[::]?(\S*)", cfg)
    if mcp_n or (mcp_cfg and mcp_cfg.group(1).strip() and mcp_cfg.group(1).strip() not in ("{}", ": {}")):
        caps.append(_cap("mcp", "ok", f"{mcp_n} server config(s)",
                     "MCP servers configured", "recommended"))
    else:
        caps.append(_cap("mcp", "missing", "no MCP servers configured",
                     "`hermes mcp add <name> --url <endpoint>` to add one", "recommended"))

    # Projects: named multi-folder workspaces.
    if (home / "projects.db").exists():
        caps.append(_cap("projects", "ok", "projects.db present",
                     "named workspaces configured", "recommended"))
    else:
        caps.append(_cap("projects", "missing", "no `hermes project` state",
                     "`hermes project create <name>` for named multi-folder workspaces", "recommended"))

    # Plugins / skills surface.
    pl = list(home.glob("plugins/*")) if home.is_dir() else []
    sk = list(home.glob("skills/*")) if home.is_dir() else []
    caps.append(_cap("plugins", "ok" if pl else "missing",
                 f"{len(pl)} plugin(s)", "`hermes plugins` manage them", "advisory"))
    caps.append(_cap("skills", "ok" if sk else "missing",
                 f"{len(sk)} skill(s)", "`hermes skills` manage them", "advisory"))

    # Profiles (routing hygiene).
    profs = orgprofiles.discover()
    if len(profs) > 1:
        caps.append(_cap("profiles", "ok", f"{len(profs)} profile(s)",
                     "`org profiles` routes work; `hermes -p <name>` to switch", "advisory"))
    else:
        caps.append(_cap("profiles", "warn", "only the default profile",
                     "consider `hermes profile create` for distinct workloads", "advisory"))

    # ── Verdict ────────────────────────────────────────────────────────────
    critical = [c for c in caps if c["tier"] == "critical"]
    ready = all(c["status"] == "ok" for c in critical)
    return {
        "ok": ready,
        "home": str(home),
        "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "capabilities": caps,
        "ready": ready,
        "summary": (f"{sum(c['status']=='ok' for c in caps)} ok / "
                    f"{sum(c['status']=='warn' for c in caps)} warn / "
                    f"{sum(c['status']=='missing' for c in caps)} missing"),
    }


def render_gate(report: dict) -> str:
    """Human-readable gate text from the report dict."""
    lines = [f"**FEATURE GATE**  {'READY' if report['ok'] else 'NOT READY'}  ({report['summary']})"]
    for c in report["capabilities"]:
        badge = {"ok": "✓", "warn": "△", "missing": "✗"}[c["status"]]
        tier = {"critical": "[critical]", "recommended": "[recommended]", "advisory": "[advisory]"}[c["tier"]]
        lines.append(f"- {badge} {c['capability']} {tier} — {c['detail']}")
        lines.append(f"    … {c['hint']}")
    lines.append(f"Checked {report['checked_at']} · home: `{report['home']}`")
    return "\n".join(lines)