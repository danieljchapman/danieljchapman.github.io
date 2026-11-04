#!/usr/bin/env bash
# One Arizona update: fetch results (one retry), check them, publish. Non-zero if nothing was published.
set -u
# start from the latest published files, so a race CivicAPI fails to send can keep its last published numbers
git fetch -q origin main && git checkout origin/main -- az/data/live_2026.csv az/data/live_status.json 2>/dev/null || true
for attempt in 1 2; do
  python3 az/tools/az_live.py --out az/data && break
  if [ "$attempt" = 2 ]; then git checkout -- az/data 2>/dev/null; exit 1; fi
  sleep 30
done
rows=$(($(wc -l < az/data/live_2026.csv) - 1))
echo "rows: $rows"
if [ "$rows" -lt 400 ]; then echo "Too few rows; not publishing"; git checkout -- az/data; exit 1; fi
bash tools/publish_live.sh "Update 2026 Arizona results" az/data/live_2026.csv az/data/live_status.json
