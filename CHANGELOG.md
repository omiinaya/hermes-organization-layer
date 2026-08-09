# Changelog

## [0.5.0] - 2026-08-09

Convenience pass (last roadmap item — P4).

- **`org find --run`** (also `org_find` with `auto=true`): finds the top matching
  entry and auto-runs its recorded `entry_points` in one step — the "find and
  launch" flow. Run logic is now a shared `_run_entry()` helper used by both
  `org run` and `org find --run` (single implementation, no drift).
- **Implicit index refresh**: `find`, `status`, and `profiles` now detect a stale
  index (newer on-disk entry than `index.json`) and rebuild it transparently —
  the index can never silently lag the workspace. `check` deliberately does NOT
  auto-refresh: its whole job is comparing the *persisted* snapshot against disk,
  so it stays the honest drift detector.
- Display layer: nested run-results render through the entry-line formatter
  (exit codes + stdout) instead of raw dict dumps.
- Suite: 43 tests (was 36).

## [0.4.0] - 2026-08-09

Production-hardening pass.

- **Feature-coverage gate (`org features` / `org_features` tool)** — probes
  `$HERMES_HOME` and reports backups (zip + state-snapshots), checkpoints, memory
  provider, cron, MCP, projects, plugins, skills, profiles as ✓/△/✗ with hints and a
  READY/NOT READY verdict. Critical tiers gate on data safety; recommended/advisory
  tiers steer "fullest extent" adoption. Memory provider extraction is scoped to the
  `memory:` block (fixed a bug where it read the model provider).
- **CI now runs on a self-hosted GitHub Actions runner** (`pve-scripts-runner` in
  LXC 100 / pve-scripts-local, labels self-hosted,linux,x64,pve-scripts) with a
  py3.10/3.11/3.12 matrix + the privacy-invariant step — no longer blocked by the
  account's hosted-runners budget.
- **Display-layer coverage**: tests for `_fmt`/`_fmt_entry_line` (run results, prune
  previews, capabilities, profiles, venvs) and the feature gate. Suite: 36 tests,
  ~84% line coverage.
- **plugin.yaml** description now reflects the full feature set (was stale).
- **Python 3.14 readiness**: restore now uses `tarfile.extractall(filter="data")`
  on Python 3.12+ (flagged by CI's DeprecationWarning).
- Backup/checkpoint rehearsal: a real `hermes backup` zip was created, integrity-tested,
  and verified to restore (config.yaml + state.db present).
- **CI verified green** on the self-hosted runner: 36 passed + register() 13 tools +
  privacy invariant.

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
