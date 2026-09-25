#!/usr/bin/env bash
# Verify the installed sentinel package matches the canonical repository.
set -euo pipefail
REPO=/root/hermes-host-sentinel
INST=/root/.hermes/plugins/hermes-host-sentinel
MISMATCH=0
for f in "$REPO"/plugin/*.py "$REPO/pyproject.toml" "$REPO/plugin/plugin.yaml"; do
  case "$f" in
    */plugin/*.py)
      b="$(basename "$f")"
      dst="$INST/plugin/$b"
      ;;
    */plugin/plugin.yaml)
      dst="$INST/plugin/plugin.yaml"
      ;;
    */pyproject.toml)
      dst="$INST/pyproject.toml"
      ;;
  esac
  if [ ! -f "$dst" ]; then echo "MISSING: ${dst#$INST/}"; MISMATCH=1; continue; fi
  if ! diff -q "$f" "$dst" >/dev/null 2>&1; then
    echo "DIFFERS: ${dst#$INST/}"
    MISMATCH=1
  fi
done
if [ "$MISMATCH" -eq 0 ]; then
  echo "ALL SENTINEL PACKAGE FILES MATCH repo HEAD"
else
  echo "MISMATCH FOUND"
fi
exit "$MISMATCH"
