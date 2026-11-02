#!/usr/bin/env bash
# One Michigan update: fetch results (one retry), check them, publish. Non-zero if nothing was published.
set -u
for attempt in 1 2; do
  python3 mi/tools/mi_live.py --out mi/data && break
  if [ "$attempt" = 2 ]; then git checkout -- mi/data 2>/dev/null; exit 1; fi
  sleep 30
done
rows=$(($(wc -l < mi/data/live_2026.csv) - 1))
echo "rows: $rows"
if [ "$rows" -lt 1000 ]; then echo "Too few rows; not publishing"; git checkout -- mi/data; exit 1; fi
bash tools/publish_live.sh "Update 2026 Michigan results" mi/data/live_2026.csv mi/data/live_status.json
