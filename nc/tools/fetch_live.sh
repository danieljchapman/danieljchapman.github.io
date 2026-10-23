#!/usr/bin/env bash
# One North Carolina update: fetch results (one retry), check them, publish. Non-zero if nothing was published.
set -u
for attempt in 1 2; do
  python3 nc/tools/nc_live.py --date 2026-11-03 --out nc/data && break
  if [ "$attempt" = 2 ]; then git checkout -- nc/data 2>/dev/null; exit 1; fi
  sleep 30
done
rows=$(($(wc -l < nc/data/live_2026.csv) - 1))
echo "rows: $rows"
if [ "$rows" -lt 1000 ]; then echo "Too few rows; not publishing"; git checkout -- nc/data; exit 1; fi
bash tools/publish_live.sh "Update 2026 North Carolina results" nc/data/live_2026.csv nc/data/live_status.json
