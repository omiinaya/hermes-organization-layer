# Org workspace skeleton

When `org init` runs it creates the following layout at the workspace root
(platform default unless overridden):

```
<workspace>/
  INDEX.md                  human-readable index (generated)
  index.json                machine-readable index (generated)
  README.org.md             workspace readme
  .org/
    config.json             org configuration (folders, policy, excludes)
  projects/                 cloned repos and active project work
  test-scripts/             ad-hoc scripts written while testing/debugging
  scratch/                  throwaway; TTL-flagged (default 30 days)
  data/                     datasets, dumps, downloaded artifacts
  notes/                    markdown notes not bound to a project
  docs/                     documentation not bound to a project
  assets/                   images, media, binaries
  _archive/                 pruned items land here (tarballed) — never hard-deleted
```

Every managed entry carries a `.org.json` metadata file:

```json
{
  "name": "my-thing",
  "kind": "projects",
  "purpose": "Short description shown in the index",
  "tags": ["tag1", "tag2"],
  "status": "active",
  "entry_points": ["README.md", "src/main.py"],
  "created": "2026-08-09T00:00:00Z",
  "notes": ""
}
```

Policy (configurable in `.org/config.json`):
- `stale_policy`: `flag` (default; only flags in INDEX.md) or `auto` (prune --apply archives).
- `scratch_ttl_days`: scratch older than this is flagged `expired-scratch`.
- `stale_after_days`: entries with no activity beyond this are flagged `stale`.
- `excludes`: paths never indexed (.git, node_modules, venv, caches, ...).
