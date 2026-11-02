#!/usr/bin/env bash
# One Florida update: fetch results (one retry), check them, publish. Non-zero if nothing was published.
set -u
for attempt in 1 2; do
  python3 fl/tools/fl_live.py --out fl/data && break
  if [ "$attempt" = 2 ]; then git checkout -- fl/data 2>/dev/null; exit 1; fi
  sleep 30
done
rows=$(($(wc -l < fl/data/live_2026.csv) - 1))
echo "rows: $rows"
if [ "$rows" -lt 1000 ]; then echo "Too few rows; not publishing"; git checkout -- fl/data; exit 1; fi
bash tools/publish_live.sh "Update 2026 Florida results" fl/data/live_2026.csv fl/data/live_status.json
