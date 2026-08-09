# Changelog

## [0.1.1] - 2026-08-09

Public-readiness hardening.

- **Index privacy (default `strict`)**: INDEX.md and index.json never contain an
  absolute machine path anymore — the workspace root is emitted as its basename
  only. Opt out with `"privacy": "full"` in `.org/config.json` (local debugging).
- Regression tests assert no absolute path ever lands in the index artifacts.
- `.gitignore` now covers per-entry `.org.json`; added `workspace-skel/.gitignore.example`
  template for workspaces that are git repos.

## [0.1.0] - 2026-08-09

Initial release (private).

- Org workspace scaffold with cross-platform default root (Windows/macOS/Linux).
- Index generation: INDEX.md (human) + index.json (machine), with excludes.
- Per-entry `.org.json` metadata (purpose, tags, status, entry_points).
- **venv tracking**: index records each entry's virtual environment(s) path + Python version
  (auto-detected from `pyvenv.cfg`, bounded 2-level scan, `.venv` honored; explicit `venvs`
  in `.org.json` override) and surfaces them in INDEX.md and find/status output, so the
  correct interpreter is never in doubt.
- Hygiene: flag-only stale policy by default; `auto` policy + `prune --apply` archive path.
- Hermes plugin: `/org` slash command + `org_*` agent tools.
- Pure-stdlib core (no third-party dependencies), English-only.
