#!/usr/bin/env python3
"""sync-provider-models.py — pin each custom provider's live /v1/models catalog into its
`models:` block in ~/.hermes/config.yaml.

WHY (2026-09-26, Omar): typing `/model big-pickle` while a session sits on a DIFFERENT custom
provider (local-qwen :8090) did not hop to the provider that actually serves it. Hermes
(hermes_cli/model_switch.py) only routes a typed model to another provider via
_configured_provider_matches(), which matches EXACTLY against models DECLARED in a
`providers.<slug>` block. opencode-zen-proxied had `discover_models: true` and no `models:` block,
so no match existed, step-e detection has no static catalog entry for a relay-only free model, and
the switch "succeeded" while keeping local-qwen (:8090). The next turn got HTTP 404
"The model `big-pickle` does not exist." A dict-shaped `models:` block is metadata, not a pin
(discovery still probes live), so declaring the catalog is safe and keeps the picker live.

Usage:
  sync-provider-models.py                      # sync ONLY the ACTIVE provider (model.provider)
  sync-provider-models.py --only <slug>        # sync one row (repeatable)
  sync-provider-models.py --all                # sync every row that has an endpoint
  sync-provider-models.py --dry-run            # print the diff, write nothing
  sync-provider-models.py --prune              # drop declared ids the endpoint no longer lists

WHY NOT --all: two configured rows can serve the SAME catalog (e.g. opencode-zen-normal :4002/v1n
and opencode-zen-proxied :4002/v1). Declaring an id on both makes _route_configured_provider()
report it as "declared by multiple configured providers" and the bare-name switch HARD FAILS
instead of routing. Only the ACTIVE row needs the declarations; a session already sitting on the
other row keeps its own provider because the model resolves there anyway.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

CONFIG = os.path.expanduser("~/.hermes/config.yaml")


def load_cfg() -> dict:
    sys.path.insert(0, "/usr/local/lib/hermes-agent")
    from hermes_cli.config import load_config  # noqa: E402

    return load_config() or {}


def endpoint(row: dict) -> str:
    for key in ("api", "base_url", "url"):
        val = str(row.get(key) or "").strip()
        if val:
            return val.rstrip("/")
    return ""


def fetch(base: str, key: str) -> list[str]:
    req = urllib.request.Request(f"{base}/models", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 - configured endpoint
        data = json.load(resp)
    return sorted({m["id"] for m in data.get("data", []) if isinstance(m.get("id"), str)})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune", action="store_true")
    ap.add_argument("--all", action="store_true", help="sync every provider row with an endpoint")
    ap.add_argument("--only", action="append", default=[], help="sync this row (repeatable)")
    args = ap.parse_args()

    cfg = load_cfg()
    rows = {k: v for k, v in (cfg.get("providers") or {}).items() if isinstance(v, dict)}
    if not rows:
        print("no providers.* rows in config", file=sys.stderr)
        return 1

    if args.only:
        targets = list(dict.fromkeys(args.only))
        unknown = [t for t in targets if t not in rows]
        if unknown:
            print(f"unknown provider slug(s): {', '.join(unknown)}", file=sys.stderr)
            return 2
    elif args.all:
        targets = list(rows)
    else:
        active = str((cfg.get("model") or {}).get("provider") or "").strip()
        targets = [active] if active in rows else []
        if not targets:
            print(f"model.provider {active!r} is not a providers.* row; pass --all or --only", file=sys.stderr)
            return 2

    from utils import atomic_roundtrip_yaml_update  # noqa: E402

    def write_block(slug: str, ids: list[str]) -> None:
        """Replace a provider's WHOLE ``models:`` sub-block in one write.

        Never write per-id keys: ``atomic_roundtrip_yaml_update`` treats dots in the KEY PATH as
        separators, so ``providers.<slug>.models.jev-1.13-free`` silently shreds a dotted model id
        into ``jev-1: {13-free: {}}`` (#146776) and the switch then stops matching it.
        """
        atomic_roundtrip_yaml_update(CONFIG, f"providers.{slug}.models", {i: {} for i in ids})

    changed = False
    for slug in targets:
        row = rows[slug]
        base = endpoint(row)
        if not base or row.get("discover_models") is False:
            print(f"- {slug}: skipped (no endpoint or discover_models: false)")
            continue
        key = str(row.get("api_key") or "").strip() or "none"
        try:
            live = fetch(base, key)
        except (urllib.error.URLError, OSError, ValueError) as err:
            print(f"! {slug}: probe failed ({err}); leaving block untouched")
            continue

        declared = list((row.get("models") or {}).keys()) if isinstance(row.get("models"), dict) else []
        if args.prune:
            target = live
        else:
            target = sorted(set(declared) | set(live))
        if target == declared:
            print(f"= {slug}: {len(live)} live, already declared")
            continue

        if args.dry_run:
            print(f"* {slug}: would declare {len(target)} ids "
                  f"(+{sorted(set(target) - set(declared))} -{sorted(set(declared) - set(target))})")
        else:
            write_block(slug, target)
            print(f"* {slug}: declared {len(target)} ids (+{len(set(target) - set(declared))} "
                  f"-{len(set(declared) - set(target))})")
        changed = True

    if not changed:
        print("config already in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
