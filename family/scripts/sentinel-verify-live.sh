#!/usr/bin/env bash
# sentinel-verify-live.sh — verify the hermes-host-sentinel v0.3.7 fixes are
# actually LIVE in the running gateway, not just on disk/synced.
#
# Checks, mapped to the fix each proves:
#   [9]  reload actually reloads  — loaded_version equals the installed __version__
#   [10] deploy_drift tripwire   — a DRIFT finding exists when they mismatch
#   [6]  _bounded_state data     — a disk history entry carries data.pct (was None)
#   [8]  sentinel_self staleness — last_run is fresh (daemon ticking)
#
# Usage: ./sentinel-verify-live.sh
# Exit 0 = ALL live checks pass; 1 = at least one fix not live.
set -u

STATE_DIR="${HOST_SENTINEL_STATE_DIR:-/root/.hermes/host-sentinel}"
STATE="$STATE_DIR/state.json"
WEBUI_TOKEN=$(python3 -c "import json;print(json.load(open('$STATE_DIR/config.json'))['webui']['token'])" 2>/dev/null || echo "")
REPO="${REPO:-/root/hermes-host-sentinel}"

fail=0
note() { printf '  [%s] %s\n' "$1" "$2"; }

echo "── sentinel live-fix verification ─────────────────────────"

# installed version from the synced plugin source
INSTALLED=$(grep -m1 '__version__' "$REPO/plugin/sentinel_core.py" | grep -oE '"[0-9.]+"' | tr -d '"')
LOADED=$(python3 -c "import json;print(json.load(open('$STATE')).get('loaded_version',''))" 2>/dev/null)
echo "installed __version__ : $INSTALLED"
echo "loaded_version (live) : $LOADED"

# [9] reload actually reloads → loaded == installed
if [ -n "$INSTALLED" ] && [ "$LOADED" = "$INSTALLED" ]; then
    note PASS "fix[9] reload in effect — loaded $LOADED == installed $INSTALLED"
else
    note STALE "fix[9] NOT live — loaded $LOADED vs installed $INSTALLED (gateway needs restart)"
    fail=1
fi

# [10] deploy_drift tripwire fires (loaded != installed) or is cleanly absent
DRIFT=$(python3 -c "
import json
d=json.load(open('$STATE'))
fl=d.get('findings',{}).get('deploy_drift',[])
print(';'.join(f.get('message','') for f in fl if isinstance(f,dict)))" 2>/dev/null)
if [ "$LOADED" = "$INSTALLED" ]; then
    note PASS "fix[10] deploy_drift consistent (loaded == installed)"
elif [ -n "$DRIFT" ]; then
    note PASS "fix[10] deploy_drift FIRING as expected: ${DRIFT:0:70}"
else
    note FAIL "fix[10] deploy_drift SILENT while loaded!=installed — tripwire dead"
    fail=1
fi

# [6] _bounded_state preserves data.pct in disk history (was stripped to None)
PCT=$(python3 -c "
import json
d=json.load(open('$STATE'))
h=d.get('history',{}).get('disk',[])
vals=[]
for e in h:
    if not isinstance(e,dict) or not e.get('findings'):
        continue
    for f in e['findings']:
        if isinstance(f,dict) and isinstance(f.get('data'),dict) and f['data'].get('pct') is not None:
            vals.append(f['data']['pct'])
print(','.join(str(v) for v in vals[-5:]))" 2>/dev/null)
if [ -n "$PCT" ]; then
    note PASS "fix[6] disk trend data LIVE — data.pct present: ${PCT:0:40}"
else
    note FAIL "fix[6] NOT live — disk history has no data.pct (old _bounded_state still running?)"
    fail=1
fi

# [8] sentinel_self staleness — last_run fresh = daemon ticking
LAST_RUN=$(python3 -c "import json;print(json.load(open('$STATE')).get('last_run',''))" 2>/dev/null)
NOW=$(date '+%Y-%m-%d %H:%M:%S')
if [[ "$LAST_RUN" > "$(date -d '10 minutes ago' '+%Y-%m-%d %H:%M:%S')" ]]; then
    note PASS "fix[8] sentinel ticking — last_run $LAST_RUN (recent)"
else
    note WARN "fix[8] last_run $LAST_RUN not within 10min — daemon may be idle"
fi

echo "────────────────────────────────────────────────────────────"
if [ "$fail" -eq 0 ]; then
    echo "RESULT: ALL live checks pass — v$INSTALLED fully live."
else
    echo "RESULT: fixes still dormant — gateway restart required to load v$INSTALLED."
fi
exit "$fail"