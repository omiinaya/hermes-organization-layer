# Hermes Organization Layer

A Hermes plugin that keeps a workspace tidy and findable over time: a canonical
cross-platform folder layout, a generated index (INDEX.md + index.json), per-entry
metadata, a stale/scratch hygiene policy, and a **profile routing table** so you
(and the agent) always know which Hermes profile to use, for what, with which tools
and venvs.

**Private for now — planned public.** Everything is built to be configurable and
cross-platform (Windows / macOS / Linux), English-only.

## What it does

- **Workspace scaffold** — one default layout for all artifacts:
  `projects/`, `test-scripts/`, `scratch/`, `data/`, `notes/`, `docs/`, `assets/`, `profiles/`, `_archive/`.
- **Index** — `org index` writes `INDEX.md` (human) + `index.json` (machine) listing what
  exists, where, its purpose, tags, status, last activity, and — crucially — any Python
  **virtual environments** (venv paths + Python version) so you (and the agent) always use
  the correct interpreter. Hidden/dep dirs are never indexed.
- **Metadata** — every entry has a small `.org.json` (name, kind, purpose, tags, status,
  entry_points; optional explicit `venvs`).
- **Profile routing** — `org index` auto-registers every Hermes profile (default + all
  `~/.hermes/profiles/*`) into `profiles/`, seeding each from its native `profile.yaml`
  description. `org profiles` lists the routing table; `org suggest "<workload>"` picks
  the best profile for a task; `org profile <name> when=...` records routing fields
  (model, when_to_use, tools, notes). The index is the one place to answer "what profile,
  for what, with which tool/venv."
- **Feature-coverage gate** — `org features` reports which Hermes capabilities are in
  use (backups, checkpoints, memory provider, cron, MCP, projects, plugins, skills,
  profiles) with a ready/not-ready verdict, turning "are we using Hermes to its fullest
  and is our data safe" into an enforceable check.
- **Hygiene** — `flag` policy (default): stale (>90 days idle) and expired-scratch (>30 days)
  are flagged in the index, nothing is deleted. `auto` policy + `org prune --apply` archives
  candidates into `_archive/` as tarballs — and `org restore <name>` unpacks one back.
  `org check` reports drift between the index and disk. Deletion is always explicit.

## Install

```bash
hermes plugins install omiinaya/hermes-organization-layer --enable
# takes effect next session: /org help
```

## Usage

```
/org init                    create the workspace scaffold (platform-default location)
/org index                   regenerate INDEX.md + index.json (auto-registers profiles)
/org new projects my-app "short purpose"
/org find proxy
/org find proxy --run      find + auto-run the top hit's entry_points
/org status
/org check                   drift check: index vs disk, privacy leaks
/org prune                   dry-run: previews the exact tarballs that would be created
/org prune --apply           archive stale/expired entries into _archive/
/org restore my-app          unpack the newest my-app tarball back into the workspace
/org run my-app              run the entry_points recorded in my-app/.org.json
/org profiles                list Hermes profiles + routing (auto-registered)
/org suggest "write tests"   which profile to use for a workload
/org profile dev when="building code"   set routing fields on a profile
/org features                feature-coverage gate (backups, cron, mcp, …)
/org config                  show resolved configuration
```

The same operations are exposed as agent tools: `org_init`, `org_index`, `org_new`,
`org_find`, `org_status`, `org_check`, `org_prune`, `org_restore`, `org_run`,
`org_profiles`, `org_suggest`, `org_set_profile`, `org_features`.

## Feature gate

`org features` probes `$HERMES_HOME` and reports each capability as ✓ / △ / ✗ with a
one-line hint, then a READY / NOT READY verdict. Critical items (backups, checkpoints,
memory provider) must all be ✓ for READY — data-safety gates; recommended/advisory
items (cron, MCP, projects, plugins, skills, profiles) steer the "fullest extent" work.

## Profiles & routing

Hermes manages profiles natively (`hermes profile create`, `hermes -p <name>`).
This plugin indexes them so routing is one lookup, not tribal knowledge:

- `org index` auto-registers every profile into `profiles/<name>/` — created on
  first index, descriptions refreshed from `profile.yaml` afterwards (your routing
  edits are preserved).
- `org profiles` — the routing table: name, model, when_to_use, launch, tools, venvs.
- `org suggest "<workload>"` — picks the best profile by matching the workload text
  against profile descriptions (falls back to the active `default`).
- `org profile <name> when="..." model="..." notes="..."` — record routing fields.

Create a profile once (`hermes profile create dev --description "..."`), and from
then on the index keeps it visible and routable — no manual registration needed.

## Entry points

Record commands in an entry's `.org.json` and run them from that entry's directory:

```json
{
  "name": "relay",
  "kind": "projects",
  "entry_points": ["python -m pytest tests/ -q", "python -m relay"]
}
```

`org run relay` executes each entry point in order (working directory = the entry's
folder) and reports the exit code, stdout, and stderr of each.

## Archive lifecycle

1. `org prune --apply` tars an eligible entry into `_archive/<name>-<stamp>.tar.gz` and
   removes the live directory. The index is refreshed automatically.
2. `org restore <name>` unpacks the most recent matching tarball back to its original
   path, refreshes the index, and deletes the tarball only after a fully successful
   extraction. It refuses to overwrite an existing live directory.

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
