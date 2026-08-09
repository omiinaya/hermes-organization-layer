# Hermes Organization Layer

A Hermes plugin that keeps a workspace tidy and findable over time: a canonical
cross-platform folder layout, a generated index (INDEX.md + index.json), per-entry
metadata, and a stale/scratch hygiene policy.

**Private for now — planned public.** Everything is built to be configurable and
cross-platform (Windows / macOS / Linux), English-only.

## What it does

- **Workspace scaffold** — one default layout for all artifacts:
  `projects/`, `test-scripts/`, `scratch/`, `data/`, `notes/`, `docs/`, `assets/`, `_archive/`.
- **Index** — `org index` writes `INDEX.md` (human) + `index.json` (machine) listing what
  exists, where, its purpose, tags, status, last activity, and — crucially — any Python
  **virtual environments** (venv paths + Python version) so you (and the agent) always use
  the correct interpreter. Hidden/dep dirs are never indexed.
- **Metadata** — every entry has a small `.org.json` (name, kind, purpose, tags, status,
  entry_points; optional explicit `venvs`).
- **Hygiene** — `flag` policy (default): stale (>90 days idle) and expired-scratch (>30 days)
  are flagged in the index, nothing is deleted. `auto` policy + `org prune --apply` archives
  candidates into `_archive/` as tarballs. Deletion is always explicit.

## Install

```bash
hermes plugins install omiinaya/hermes-organization-layer --enable
# takes effect next session: /org help
```

## Usage

```
/org init                    create the workspace scaffold (platform-default location)
/org index                   regenerate INDEX.md + index.json
/org new projects my-app "short purpose"
/org find proxy
/org status
/org prune                   dry-run hygiene report
/org prune --apply           archive stale/expired entries into _archive/
/org config                  show resolved configuration
```

The same operations are exposed as agent tools: `org_init`, `org_index`, `org_new`,
`org_find`, `org_status`, `org_prune`.

## Configuration

- Workspace root: platform default (`%USERPROFILE%\Documents\hermes-org` on Windows,
  `~/Documents/hermes-org` on macOS/Linux, falling back to `~/hermes-org` when no Documents
  dir exists), overridable via `HERMES_ORG_WORKSPACE` or `.org/config.json`.
- `.org/config.json`: folders, excludes, and policy (stale_policy, scratch_ttl_days,
  stale_after_days, auto_archive_after_days).

## Repository layout

```
plugin/            Hermes plugin (plugin.yaml, __init__.py, orgcore/)
workspace-skel/    default skeleton + example config
tests/             pytest suite (stdlib-only core)
docs/              design docs
```

## Development

```bash
python3 -m pytest tests/ -v
```

The core (`orgcore/`) is pure Python stdlib — no third-party dependencies — so it runs
identically on Windows, macOS, and Linux, with or without Hermes.

## License

MIT
