#!/usr/bin/env bash
# Commit data files on top of the latest main and push (default: data/live_2026.csv data/live_status.json).
# Only those files are committed, so this never conflicts with other pushes.
# Usage: publish_live.sh [message] [files...]
set -u
msg="${1:-Update 2026 election results}"; shift || true
files="${*:-data/live_2026.csv data/live_status.json}"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
for attempt in 1 2 3 4; do
  git fetch -q origin main || { sleep 5; continue; }
  git reset -q origin/main            # point at the latest main, keep the new data files in the working tree
  git add $files
  if git diff --cached --quiet; then echo "No changes"; exit 0; fi
  git commit -q -m "$msg"
  if git push -q origin HEAD:main; then echo "Published"; exit 0; fi
  echo "Push rejected (attempt $attempt); retrying"; sleep $((attempt * 5))
done
echo "Could not publish"; exit 1
