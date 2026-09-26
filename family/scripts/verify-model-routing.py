#!/usr/bin/env python3
"""verify-model-routing.py — prove a bare /model <name> from a session sitting on ANOTHER custom
provider hops to the provider that declares it, and that the same name does NOT become ambiguous.

Regression probe for the 2026-09-26 404 ("Model 'big-pickle' isn't available on local-qwen"):
the switch used to report success while KEEPING the current provider, so the next turn hit
local-qwen's /v1/chat/completions with a model that box has never heard of (HTTP 404).

Run: /usr/local/lib/hermes-agent/venv/bin/python verify-model-routing.py
Exit 0 = all cases route; non-zero = a case regressed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "/usr/local/lib/hermes-agent")

from gateway.run import _load_gateway_config  # noqa: E402
from hermes_cli.config import get_compatible_custom_providers  # noqa: E402
from hermes_cli.model_switch import switch_model  # noqa: E402

CONFIG = Path("/root/.hermes/config.yaml")

# (model_to_type, current_provider, current_model, current_base_url, current_key,
#  expected_provider, expected_base_url)
CASES = [
    ("big-pickle", "local-qwen", "qwen3.8-27b",
     "http://192.168.1.19:8090/v1", "local",
     "opencode-zen-proxied", "http://localhost:4002/v1"),
    ("qwen3.8-27b", "opencode-zen-proxied", "big-pickle",
     "http://localhost:4002/v1", "k",
     "local-qwen", "http://192.168.1.19:8090/v1"),
    ("big-pickle", "opencode-zen-proxied", "big-pickle",
     "http://localhost:4002/v1", "k",
     "opencode-zen-proxied", "http://localhost:4002/v1"),
    ("space-bunny-free", "local-qwen", "qwen3.8-27b",
     "http://192.168.1.19:8090/v1", "local",
     "opencode-zen-proxied", "http://localhost:4002/v1"),
]


def main() -> int:
    cfg = _load_gateway_config(config_path=CONFIG)
    up = cfg.get("providers") or {}
    cp = get_compatible_custom_providers(cfg)

    failed = 0
    for model, cur, cur_model, cur_url, cur_key, want_prov, want_url in CASES:
        res = switch_model(model, current_provider=cur, current_model=cur_model,
                           current_base_url=cur_url, current_api_key=cur_key,
                           user_providers=up, custom_providers=cp)
        ok = bool(res and res.success
                  and res.target_provider == want_prov
                  and (res.base_url or "").rstrip("/") == want_url.rstrip("/"))
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  /model {model:18s} from {cur:20s} "
              f"-> {getattr(res, 'target_provider', '?'):22s} {getattr(res, 'base_url', '') or '-':26s}")
        if not ok:
            print(f"      expected {want_prov} {want_url}; error={getattr(res, 'error_message', '')!r}")
    print(f"\n{len(CASES) - failed}/{len(CASES)} cases routed correctly")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
