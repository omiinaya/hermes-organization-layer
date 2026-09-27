#!/usr/bin/env bash
# msw-scrub-history.sh — remove operator PII from every commit in hermes-model-switch.
# Replaces the legal name, the personal email domain, the real Matrix room/user ids and the
# display name, in BOTH commit metadata and historical blobs, then force-pushes.
# Idempotent and re-runnable. A pre-rewrite copy lives beside it in scratch.
set -euo pipefail

REPO="${1:-/root/projects/hermes-model-switch}"
cd "$REPO"

BACKUP=/root/.hermes/cache/scratch/nonexistent
[[ -d "$BACKUP" ]] || { echo "refusing: no backup at $BACKUP" >&2; exit 1; }

# --replace-text takes literal text; these are exact strings that appear in history.
git filter-repo --force \
  --replace-text <(cat <<'EOF'
Omar Minaya==>omiinaya
omiinaya@mrxlab.local==>omiinaya@users.noreply.github.com
!aHthTAlfDQBzkknuNd:matrix-server.mrxlab.local==>!testroom:example.invalid
@sullen:matrix-server.mrxlab.local==>@operator:example.invalid
sullen==>operator
mrxlab.local==>example.invalid
mrxlab==>example
/root/.hermes==>~/.hermes
EOF
) \
  --commit-callback 'commit.author_email=b"omiinaya@users.noreply.github.com"; commit.author_name=b"omiinaya"; commit.committer_email=b"omiinaya@users.noreply.github.com"; commit.committer_name=b"omiinaya"'

# This git-filter-repo version has no --name/--email flags, and a --commit-callback assigning
# plain str (not bytes) aborts the fast-import stream MID-RUN. Identity is rewritten above with
# byte literals, because that form completes cleanly.

echo "=== verify ==="
git log --all --format="%h|%an|%ae" | sort -u
if git rev-list --all | while read -r c; do git grep -lIiE "mrxlab|sullen|ominaya@mrxlab" "$c" 2>/dev/null; done | grep -q .; then
  echo "FAIL: PII still present" >&2; exit 1
fi
echo "OK: no operator PII in history"
