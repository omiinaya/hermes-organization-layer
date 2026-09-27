"""Tests for orgcore (pure stdlib, cross-platform)."""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin"))

from orgcore import actions, config, index, workspace  # noqa: E402


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """A workspace rooted at a temp dir; actions._root() honours HERMES_ORG_WORKSPACE."""
    monkeypatch.setenv("HERMES_ORG_WORKSPACE", str(tmp_path))
    actions.cmd_init()
    return tmp_path


def test_init_creates_folders_and_config(ws):
    assert (ws / "projects").is_dir()
    assert (ws / "test-scripts").is_dir()
    assert (ws / "scratch").is_dir()
    assert (ws / ".org" / "config.json").exists()


def test_config_workspace_key_is_honoured_without_env(tmp_path, monkeypatch):
    """A workspace set in config.json must survive `load_config`.

    Regression: `load_config` copied only
    (folders, excludes, policy, version, language, privacy) out of the saved
    config, so a `workspace` key was silently dropped. `_root()` reads the
    config from the *default* root and then returns cfg["workspace"], so with
    no HERMES_ORG_WORKSPACE set the workspace in config.json had no effect at
    all — the only way to move the root was the env var, and the config file
    was a lie.
    """
    # No env var: exactly the situation that was broken.
    monkeypatch.delenv("HERMES_ORG_WORKSPACE", raising=False)

    saved = {"version": 1, "workspace": str(tmp_path), "language": "en"}
    org = tmp_path / ".org"
    org.mkdir(parents=True)
    (org / "config.json").write_text(json.dumps(saved))

    cfg = config.load_config(tmp_path)
    assert cfg["workspace"] == str(tmp_path)


def test_env_still_overrides_config_workspace(tmp_path, monkeypatch):
    """HERMES_ORG_WORKSPACE must keep winning over the config file."""
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.setenv("HERMES_ORG_WORKSPACE", str(other))

    org = tmp_path / ".org"
    org.mkdir(parents=True)
    (org / "config.json").write_text(json.dumps({"workspace": str(tmp_path)}))

    cfg = config.load_config(tmp_path)
    assert cfg["workspace"] == str(other)


def test_dir_size_skips_excluded_dirs(tmp_path):
    """`_dir_size` must not descend into excluded directory names.

    Regression: it used `rglob("*")` with no excludes, so indexing a workspace
    of real repos walked `target/`, `node_modules/` and `.venv/` (86 entries
    took 372s). The excluded tree must contribute zero bytes.
    """
    entry = tmp_path / "proj"
    (entry / "src").mkdir(parents=True)
    (entry / "src" / "main.py").write_text("x" * 100)

    junk = entry / "node_modules" / "pkg"
    junk.mkdir(parents=True)
    (junk / "huge.js").write_text("y" * 100_000)

    with_excludes = index._dir_size(entry, ("node_modules",))
    without = index._dir_size(entry)

    assert with_excludes == 100
    assert without == 100_100


def test_new_entry_creates_meta_and_index(ws):
    tag, data = actions.cmd_new("projects", "my-app", "A test app")
    assert tag == "NEW" and data["ok"]
    meta = json.loads((ws / "projects" / "my-app" / ".org.json").read_text())
    assert meta["kind"] == "projects"
    assert (ws / "INDEX.md").exists()
    assert (ws / "index.json").exists()


def test_new_rejects_unknown_kind(ws):
    tag, data = actions.cmd_new("nope", "x")
    assert data["ok"] is False


def test_find_matches_purpose_and_tags(ws):
    actions.cmd_new("projects", "relay", "SOCKS5 proxy rotation for LLM calls", tags=["proxy", "llm"])
    tag, hits = actions.cmd_find("proxy")
    assert any(h["name"] == "relay" for h in hits)
    tag, hits = actions.cmd_find("socks5")
    assert any(h["name"] == "relay" for h in hits)


def test_status_counts(ws):
    actions.cmd_new("test-scripts", "probe")
    actions.cmd_new("notes", "idea")
    tag, data = actions.cmd_status()
    assert data["total"] == 2


def test_prune_dry_run_is_non_destructive(ws):
    actions.cmd_new("scratch", "junk")
    tag, data = actions.cmd_prune(apply=False)
    assert (ws / "scratch" / "junk").is_dir()


def test_excludes_never_indexed(ws):
    (ws / "projects" / "app" / ".git").mkdir(parents=True)
    (ws / "projects" / "app" / "node_modules").mkdir(parents=True)
    tag, data = actions.cmd_status()
    names = [it["name"] for it in data["flagged"]] + [it["name"] for it in []]
    items = index.build_items(ws, config.load_config(ws))
    # .git/node_modules live inside the entry, so the entry itself still shows;
    # ensure the index JSON excludes the hidden dirs at top level
    assert all(not p.name.startswith(".") or p.name == ".org.json"
               for it in items for p in [Path(it["rel_path"])])


def test_cross_platform_default_root_returns_path():
    assert config.default_workspace_root().is_absolute()


def test_index_records_venv_for_entry(ws):
    actions.cmd_new("projects", "weba")
    proj = ws / "projects" / "weba"
    (proj / ".venv").mkdir()
    (proj / ".venv" / "pyvenv.cfg").write_text("home = /usr/bin\nversion = 3.12.1\n")
    items = index.build_items(ws, config.load_config(ws))
    it = next(x for x in items if x["name"] == "weba")
    assert it["venvs"] == [{"path": ".venv", "version": "3.12.1"}]


def test_explicit_venv_meta_wins(ws):
    actions.cmd_new("projects", "legacy")
    (ws / "projects" / "legacy" / ".org.json").write_text(
        json.dumps({"name": "legacy", "kind": "projects", "venvs": [{"path": "custom-env", "version": "3.9"}]}))
    items = index.build_items(ws, config.load_config(ws))
    it = next(x for x in items if x["name"] == "legacy")
    assert any(v["path"] == "custom-env" and v["version"] == "3.9" for v in it["venvs"])


# -- privacy / public-readiness --------------------------------------------

_DRIVE = ("C:", "D:", "E:", "F:")


def _assert_no_abs_paths(ws: Path) -> None:
    md = (ws / "INDEX.md").read_text(encoding="utf-8")
    jd = json.loads((ws / "index.json").read_text(encoding="utf-8"))
    abs_ws = str(ws)  # e.g. /tmp/pytest-*/...  (absolute by construction)
    assert abs_ws not in md, "INDEX.md must not contain the absolute workspace path"
    assert abs_ws not in json.dumps(jd), "index.json must not contain the absolute workspace path"
    # every path-like field in the machine index is relative (rel_path, venv paths)
    for it in jd["items"]:
        assert not it["rel_path"].startswith("/") and not it["rel_path"].startswith(_DRIVE)
        for v in it.get("venvs", []):
            assert not v["path"].startswith("/") and not v["path"].startswith(_DRIVE)


def test_index_never_leaks_absolute_paths_default(ws):
    actions.cmd_new("projects", "relay", "SOCKS5 proxy rotation", tags=["proxy"])
    tag, data = actions.cmd_index()
    assert data["ok"]
    jd = json.loads((ws / "index.json").read_text())
    assert jd["privacy"] == "strict"
    assert jd["workspace"] == ws.name  # basename only, never the machine path
    assert not jd["workspace"].startswith("/")
    _assert_no_abs_paths(ws)


def test_privacy_full_opt_out_restores_abs_path(ws):
    cfg = config.load_config(ws)
    cfg["privacy"] = "full"
    config.save_config(ws, cfg)
    actions.cmd_new("projects", "app")
    jd = json.loads((ws / "index.json").read_text())
    assert jd["privacy"] == "full"
    assert jd["workspace"] == str(ws)  # explicit opt-out documents the trade-off


# -- archive lifecycle: prune -> restore -----------------------------------

def _age_scratch(ws: Path, name: str) -> None:
    """Backdate an entry's mtime so scratch_ttl_days (30) flags it expired."""
    old = 40 * 86400
    for p in (ws / "scratch" / name).rglob("*"):
        try:
            os.utime(p, (p.stat().st_mtime - old, p.stat().st_mtime - old))
        except OSError:
            pass
    root = ws / "scratch" / name
    try:
        os.utime(root, (root.stat().st_mtime - old, root.stat().st_mtime - old))
    except OSError:
        pass


def test_prune_dry_run_previews_exact_tarballs(ws):
    actions.cmd_new("scratch", "junk")
    _age_scratch(ws, "junk")
    tag, data = actions.cmd_prune(apply=False)
    assert tag == "PRUNE (dry-run)"
    assert len(data["would_archive"]) == 1
    plan = data["would_archive"][0]
    assert plan["rel_path"] == "scratch/junk"
    assert plan["dest"].endswith(".tar.gz")
    assert "_archive" in plan["dest"]
    # nothing changed on disk
    assert (ws / "scratch" / "junk").is_dir()


def test_prune_apply_archives_and_refreshes_index(ws):
    actions.cmd_new("scratch", "junk")
    _age_scratch(ws, "junk")
    tag, data = actions.cmd_prune(apply=True)
    assert tag == "PRUNE"
    assert len(data["moved"]) == 1
    assert not (ws / "scratch" / "junk").exists()
    assert Path(data["moved"][0]).is_file()
    # index regenerated after the mutation: entry gone from it
    jd = json.loads((ws / "index.json").read_text())
    assert all(it["name"] != "junk" for it in jd["items"])


def _archive_junk(ws: Path) -> Path:
    actions.cmd_new("scratch", "junk")
    _age_scratch(ws, "junk")
    tag, data = actions.cmd_prune(apply=True)
    assert tag == "PRUNE"
    return Path(data["moved"][0])


def test_restore_unpacks_archived_entry(ws):
    tarball = _archive_junk(ws)
    tag, data = actions.cmd_restore("junk")
    assert tag == "RESTORE"
    assert data["ok"]
    assert (ws / "scratch" / "junk" / "README.md").exists()
    assert not tarball.exists()  # tarball consumed by a successful restore
    # index refreshed again: entry is back
    jd = json.loads((ws / "index.json").read_text())
    assert any(it["name"] == "junk" for it in jd["items"])


def test_restore_refuses_when_target_exists(ws):
    tarball = _archive_junk(ws)
    (ws / "scratch" / "junk").mkdir()  # recreate the live dir
    tag, data = actions.cmd_restore("junk")
    assert not data["ok"]
    assert "refusing to overwrite" in data["error"]
    assert tarball.exists()  # untouched on failure


def test_restore_unknown_name(ws):
    tag, data = actions.cmd_restore("nope")
    assert not data["ok"]


# -- drift check -----------------------------------------------------------

def test_check_reports_drift(ws):
    actions.cmd_new("projects", "app")
    tag, data = actions.cmd_check()
    assert data["ok"] is True
    assert data["indexed"] >= 1
    # simulate an entry whose dir vanishes behind the index's back
    shutil.rmtree(ws / "projects" / "app")
    tag, data = actions.cmd_check()
    assert not data["ok"]
    assert any("projects/app" in rp for rp in data["missing_dirs"] + data["unindexed"])


def test_check_flags_privacy_leaks_in_meta(ws):
    actions.cmd_new("projects", "app")
    (ws / "projects" / "app" / ".org.json").write_text(
        json.dumps({"name": "app", "kind": "projects", "notes": "/root/secret-box"}))
    tag, data = actions.cmd_check()
    assert "projects/app" in data["privacy_leaks"]


# -- entry_points ----------------------------------------------------------

def test_run_executes_entry_points(ws):
    actions.cmd_new("projects", "echoer")
    meta = config.load_meta(ws / "projects" / "echoer")
    meta["entry_points"] = [sys.executable + " -c \"print('hi from echoer')\""]
    config.meta_path(ws / "projects" / "echoer").write_text(json.dumps(meta))
    tag, data = actions.cmd_run("echoer")
    assert data["ok"]
    assert data["results"][0]["exit"] == 0
    assert "hi from echoer" in data["results"][0]["stdout"]


def test_run_missing_entry_points(ws):
    actions.cmd_new("projects", "quiet")
    tag, data = actions.cmd_run("quiet")
    assert not data["ok"]
    assert "no entry_points" in data["error"]



# -- feature-coverage gate -------------------------------------------------

@pytest.fixture
def features_fixed(tmp_path, monkeypatch):
    """A fake HERMES_HOME with a recent backup + checkpoint + memory provider
    so the gate reports READY (except the explicitly-off recommended items)."""
    hh = tmp_path / ".hermes"
    (hh / "checkpoints").mkdir(parents=True)
    (hh / "checkpoints" / "cp-1").write_text("snapshot")
    (hh / "config.yaml").write_text("memory:\n  provider: memory_tencentdb\n")
    # a fresh, valid backup zip inside the fake HERMES_HOME
    import zipfile
    bzip = hh / "hermes-backup-20260801-000000.zip"
    with zipfile.ZipFile(bzip, "w") as zf:
        zf.writestr("config.yaml", "x")
    monkeypatch.setenv("HERMES_HOME", str(hh))
    return tmp_path


def test_feature_gate_ready_when_critical_present(features_fixed):
    os.utime(next(Path(features_fixed, ".hermes").glob("hermes-backup-*.zip")),
             (time.time(), time.time()))
    from orgcore import features
    rep = features.probe(Path(features_fixed) / ".hermes", user_home=Path(features_fixed))
    # critical all ok -> ready
    crit = {c["capability"]: c["status"] for c in rep["capabilities"] if c["tier"] == "critical"}
    assert set(crit) == {"backups", "checkpoints", "memory_provider"}
    assert all(v == "ok" for v in crit.values()), crit
    assert rep["ready"] is True


def test_feature_gate_not_ready_without_backup(tmp_path, monkeypatch):
    hh = tmp_path / ".hermes"
    (hh / "checkpoints").mkdir(parents=True)
    (hh / "checkpoints" / "cp-1").write_text("x")
    (hh / "config.yaml").write_text("memory:\n  provider: memory_tencentdb\n")
    monkeypatch.setenv("HERMES_HOME", str(hh))
    from orgcore import features
    rep = features.probe(hh, user_home=tmp_path)
    b = next(c for c in rep["capabilities"] if c["capability"] == "backups")
    assert b["status"] == "missing"
    assert rep["ready"] is False


def test_feature_gate_renders(features_fixed):
    os.utime(next(Path(features_fixed, ".hermes").glob("hermes-backup-*.zip")),
             (time.time(), time.time()))
    tag, rep = actions.cmd_features()
    text = actions._fmt(tag, rep)
    assert "FEATURE GATE" in text
    assert "backups" in text and "checkpoints" in text
    assert text.splitlines()[0].startswith("**FEATURE GATE")


def test_memory_provider_scoped_to_memory_block():
    from orgcore import features
    cfg = ("providers:\n    provider: custom:opencode-zen-free-proxied\n"
           "memory:\n  provider: memory_tencentdb\n  backend: local\n")
    assert features._memory_provider(cfg) == "memory_tencentdb"
    assert features._memory_provider("providers:\n    provider: xyz\n") == ""


def test_gate_warn_does_not_block_ready(features_fixed):
    # Delete the checkpoint files so checkpoints=warn (empty store) but backups
    # and memory are fine -> READY still (warn is amber, not a blocker).
    shutil.rmtree(Path(features_fixed) / ".hermes" / "checkpoints")
    from orgcore import features
    rep = features.probe(Path(features_fixed) / ".hermes", user_home=Path(features_fixed))
    cp = next(c for c in rep["capabilities"] if c["capability"] == "checkpoints")
    assert cp["status"] == "warn"
    assert rep["ready"] is True


# -- display layer (_fmt) -------------------------------------------------------

def test_fmt_scalars_dict_list_str():
    assert actions._fmt("T", {"a": 1, "b": "x"}) == "**T**\n- a: 1\n- b: x"
    assert actions._fmt("T", "plain") == "**T**\nplain"
    out = actions._fmt("T", ["c", "d"])
    assert "- c" in out and "- d" in out


def test_fmt_entry_line_run_result():
    line = actions._fmt_entry_line({"command": "pytest", "exit": 0, "stdout": "ok"}, indent=1)
    assert "`pytest`" in line and "exit 0" in line and "ok" in line
    line = actions._fmt_entry_line({"command": "bogus", "exit": None})
    assert "failed to start" in line


def test_fmt_entry_line_prune_preview():
    line = actions._fmt_entry_line({"rel_path": "x/y", "status": "stale", "dest": "/tmp/a.tar.gz"}, indent=0)
    assert "→ /tmp/a.tar.gz" in line


def test_fmt_entry_line_capability():
    line = actions._fmt_entry_line(
        {"capability": "backups", "status": "ok", "tier": "critical", "detail": "bk-1.zip", "hint": "refresh"}, indent=0)
    assert "✓" in line and "backups" in line and "refresh" in line


def test_fmt_entry_line_profile():
    line = actions._fmt_entry_line(
        {"name": "dev", "status": "active", "purpose": "code", "launch": "hermes -p dev",
         "tools": [{"name": "pytest", "profile": "dev"}]}, indent=0)
    assert "dev" in line and "hermes -p dev" in line and "pytest" in line


def test_fmt_entry_line_venv():
    line = actions._fmt_entry_line(
        {"rel_path": "proj", "status": "active", "venvs": [{"path": ".venv", "version": "3.12"}]})
    assert ".venv (3.12)" in line


# -- P4 convenience: run-on-find + implicit index refresh -----------------------

def test_find_auto_runs_entry_points(ws):
    actions.cmd_new("test-scripts", "probe")
    (ws / "test-scripts" / "probe" / ".org.json").write_text(json.dumps({
        "name": "probe", "kind": "test-scripts",
        "entry_points": [sys.executable + " -c \"import sys; print('RUN_OK')\""]}))
    tag, data = actions.cmd_find("probe", auto=True)
    assert isinstance(data, dict) and "hits" in data and "auto_ran" in data
    assert data["auto_ran"]["ok"] is True
    assert "RUN_OK" in data["auto_ran"]["results"][0]["stdout"]


def test_find_auto_run_no_entry_points_reports_error(ws):
    actions.cmd_new("notes", "note1")
    tag, data = actions.cmd_find("note1", auto=True)
    assert data["auto_ran"]["ok"] is False
    assert "no entry_points" in data["auto_ran"]["error"]


def test_find_auto_no_hits_returns_plain_list(ws):
    tag, data = actions.cmd_find("nomatch", auto=True)
    assert isinstance(data, list) and data == []


def test_cmd_run_uses_shared_helper(ws):
    actions.cmd_new("test-scripts", "probe2")
    (ws / "test-scripts" / "probe2" / ".org.json").write_text(json.dumps({
        "name": "probe2", "kind": "test-scripts",
        "entry_points": [sys.executable + " -c \"import sys; print('ALSO_OK')\""]}))
    tag, data = actions.cmd_run("probe2")
    assert data["ok"] and "ALSO_OK" in data["results"][0]["stdout"]


def test_stale_index_refreshed_on_find(ws):
    # build a fresh index, then add an entry OUTSIDE the plugin and touch it so
    # index.json becomes older than the newest on-disk entry
    actions.cmd_new("projects", "one")
    newdir = ws / "projects" / "injected"
    newdir.mkdir()
    (newdir / ".org.json").write_text(json.dumps({"name": "injected", "kind": "projects"}))
    assert actions._index_is_stale(ws, config.load_config(ws)) is True
    tag, hits = actions.cmd_find("injected")   # implicit refresh happens
    assert any(h["name"] == "injected" for h in hits)
    jd = json.loads((ws / "index.json").read_text())
    assert any(it["rel_path"] == "projects/injected" for it in jd["items"])
    assert actions._index_is_stale(ws, config.load_config(ws)) is False


def test_fresh_index_not_refreshed_on_read(ws):
    actions.cmd_new("projects", "app")
    assert actions._index_is_stale(ws, config.load_config(ws)) is False
    before = (ws / "index.json").read_text()
    actions.cmd_find("app")
    assert (ws / "index.json").read_text() == before  # no spurious rewrite
