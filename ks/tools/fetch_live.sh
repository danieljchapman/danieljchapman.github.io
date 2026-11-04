#!/usr/bin/env bash
# One Kansas update: fetch results (one retry), check them, publish. Non-zero if nothing was published.
set -u
# start from the latest published files, so a race CivicAPI fails to send can keep its last published numbers
git fetch -q origin main && git checkout origin/main -- ks/data/live_2026.csv ks/data/live_status.json 2>/dev/null || true
for attempt in 1 2; do
  python3 ks/tools/ks_live.py --out ks/data && break
  if [ "$attempt" = 2 ]; then git checkout -- ks/data 2>/dev/null; exit 1; fi
  sleep 30
done
rows=$(($(wc -l < ks/data/live_2026.csv) - 1))
echo "rows: $rows"
if [ "$rows" -lt 1500 ]; then echo "Too few rows; not publishing"; git checkout -- ks/data; exit 1; fi
bash tools/publish_live.sh "Update 2026 Kansas results" ks/data/live_2026.csv ks/data/live_status.json
