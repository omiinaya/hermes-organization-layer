# Changelog

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
