#!/bin/bash
# Register a pristine GitHub Actions runner for one omiinaya/spacetime-* repo.
# Usage: register-runner.sh <repo-suffix>   e.g.  register-runner.sh kanban
set -uo pipefail
CT=103
REPO="$1"
RNAME="pve-scripts-runner-spacetime-$REPO"
TOK=""
for i in 1 2 3; do TOK=$(gh api -X POST "repos/omiinaya/spacetime-$REPO/actions/runners/registration-token" -q .token 2>/dev/null) && [ -n "$TOK" ] && break; sleep 3; done
if [ -z "$TOK" ]; then echo "TOKEN_FETCH_FAIL $REPO"; exit 1; fi

echo "=== $REPO: fetching pristine runner ==="
pct exec $CT -- bash -lc "cd /tmp && curl -fsSL -o actrunner-$REPO.tar.gz https://github.com/actions/runner/releases/download/v2.337.0/actions-runner-linux-x64-2.337.0.tar.gz" || { echo "FETCH_FAIL $REPO"; exit 1; }

echo "=== $REPO: extract + register ==="
pct exec $CT -- bash -lc "
  set -e
  rm -rf /opt/actions-runner-spacetime-$REPO
  mkdir -p /opt/actions-runner-spacetime-$REPO
  tar xzf /tmp/actrunner-$REPO.tar.gz -C /opt/actions-runner-spacetime-$REPO
  chown -R runner-spacetime-llm:runner-spacetime-llm /opt/actions-runner-spacetime-$REPO
  rm -f /opt/actions-runner-spacetime-$REPO/.runner /opt/actions-runner-spacetime-$REPO/.credentials
  runuser -u runner-spacetime-llm -- bash -c 'cd /opt/actions-runner-spacetime-$REPO && ./config.sh --url https://github.com/omiinaya/spacetime-$REPO --token $TOK --name $RNAME --labels self-hosted,Linux,X64,pve-scripts --unattended --replace 2>&1 | grep -E \"Settings Saved|error|Cannot\" '
  if [ ! -f /opt/actions-runner-spacetime-$REPO/.runner ]; then echo 'CONFIG_FAIL_NO_RUNNER $REPO'; exit 2; fi
  # runsvc may not be generated in unattended mode; copy from a known-good runner
  cp /opt/actions-runner-spacetime-llm/runsvc.sh /opt/actions-runner-spacetime-$REPO/runsvc.sh
  chmod +x /opt/actions-runner-spacetime-$REPO/runsvc.sh
"

echo "=== $REPO: systemd service ==="
pct exec $CT -- bash -lc "
  cat > /etc/systemd/system/actions.runner.omiinaya-spacetime-$REPO.pve-scripts-runner-spacetime-$REPO.service <<'EOF'
[Unit]
Description=GitHub Actions Runner (omiinaya-spacetime-$REPO.pve-scripts-runner-spacetime-$REPO)
After=network-online.target

[Service]
ExecStart=/opt/actions-runner-spacetime-$REPO/runsvc.sh
User=
WorkingDirectory=/opt/actions-runner-spacetime-$REPO
KillMode=process
KillSignal=SIGTERM
TimeoutStopSec=5min

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --quiet actions.runner.omiinaya-spacetime-$REPO.pve-scripts-runner-spacetime-$REPO.service
  systemctl restart actions.runner.omiinaya-spacetime-$REPO.pve-scripts-runner-spacetime-$REPO.service
  sleep 6
  systemctl is-active actions.runner.omiinaya-spacetime-$REPO.pve-scripts-runner-spacetime-$REPO.service
"
echo "$REPO DONE"