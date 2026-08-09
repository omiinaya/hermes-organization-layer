"""Tests for orgcore (pure stdlib, cross-platform)."""

from __future__ import annotations

import json
import sys
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
