#!/usr/bin/env bash
# sentinel-sync.sh — deploy hermes-host-sentinel changes to the installed clone,
# run the full test suite, and (optionally) commit + push.
#
# Usage:
#   sentinel-sync.sh            # sync plugin files to installed clone (no commit)
#   sentinel-sync.sh commit <msg>   # sync + git add/commit (omiinaya) + push
#
# The plugin is a package, not only a directory of Python modules. Sync
# pyproject.toml and the manifest too, or Hermes' plugin dependency build can
# disable the plugin while the Python-only smoke tests remain green.
set -euo pipefail
cd /root/hermes-host-sentinel
INST=/root/.hermes/plugins/hermes-host-sentinel

SYNCED=0
for f in plugin/*.py pyproject.toml plugin/plugin.yaml; do
  case "$f" in
    plugin/*.py)
      base="$(basename "$f")"
      dst="$INST/plugin/$base"
      ;;
    plugin/plugin.yaml)
      dst="$INST/plugin/plugin.yaml"
      ;;
    pyproject.toml)
      dst="$INST/pyproject.toml"
      ;;
  esac
  cp "$f" "$dst"
  diff -q "$f" "$dst" >/dev/null
  SYNCED=$((SYNCED+1))
done
echo "SYNC OK ($SYNCED files)"

/usr/local/lib/hermes-agent/venv/bin/python -m pytest -q

if [ "${1:-}" = "commit" ]; then
  msg="${2:?commit message required}"
  git add -A
  git -c user.name=omiinaya -c user.email=omiinaya@users.noreply.github.com commit -m "$msg"
  git push origin main 2>&1 | tail -2
  echo "HEAD==origin: $([ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] && echo yes || echo no)"
fi
