# Changelog

## [0.3.0] - 2026-08-09

Profile routing — the org layer now knows *who to use for what*.

- **Profile domain (`profiles/` kind)**: `org index` auto-registers every Hermes
  profile (active default + all `$HERMES_HOME/profiles/*`) into the workspace,
  seeding each routing entry from the profile's native `profile.yaml` description.
  Absolute home paths are deliberately NOT persisted (privacy strict mode).
- **`org profiles`** — the routing table: name, model, when_to_use, launch, tools,
  venvs, active flag.
- **`org suggest "<workload>"`** — picks the best profile by keyword-matching the
  workload against profile descriptions, with a scored candidate list and a
  safe fallback to the active profile when nothing matches.
- **`org profile <name> when=... model=... tools=... notes=...`** — record routing
  fields on a profile (preserved across re-indexes).
- New agent tools: `org_profiles`, `org_suggest`, `org_set_profile` (total 12).

## [0.2.0] - 2026-08-09

Lifecycle and drift tooling.

- **`org restore <name>`** — unpack the most recent `_archive/<name>-*.tar.gz` back to its
  original workspace path. Refuses to overwrite an existing live directory; deletes the
  tarball only after a fully successful extraction; refreshes the index.
- **`org prune` dry-run preview** — now shows the exact tarballs that WOULD be created
  (rel_path, status, destination path), and distinguishes flagged-only entries from the
  ones that would actually move under the current policy (expired-scratch always; stale
  only under `stale_policy: auto`).
- **`org check`** — drift check: compares the persisted index snapshot to disk (detached
  records, unindexed dirs) and flags absolute-path leaks in per-entry metadata
  (privacy violations under strict mode). Also lists `_archive/` contents.
- **`org run <name>`** — execute the `entry_points` recorded in an entry's `.org.json`,
  from the entry's directory, reporting exit code / stdout / stderr per command.
- Index is now regenerated automatically after `prune --apply` and `restore` mutations,
  so INDEX.md never lists entries that were archived away (or misses restored ones).
- New agent tools: `org_check`, `org_restore`, `org_run` (total 9).
- **CI (GitHub Actions)** — pytest on ubuntu/macos/windows × Python 3.10/3.11/3.12 plus a
  dedicated privacy-invariant step (no absolute paths in index artifacts).

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
