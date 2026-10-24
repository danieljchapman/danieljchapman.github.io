#!/usr/bin/env bash
# One Georgia update: fetch results (one retry), check them, publish. Non-zero if nothing was published.
set -u
for attempt in 1 2; do
  python3 ga/tools/ga_live.py --out ga/data && break
  if [ "$attempt" = 2 ]; then git checkout -- ga/data 2>/dev/null; exit 1; fi
  sleep 30
done
rows=$(($(wc -l < ga/data/live_2026.csv) - 1))
echo "rows: $rows"
if [ "$rows" -lt 1000 ]; then echo "Too few rows; not publishing"; git checkout -- ga/data; exit 1; fi
bash tools/publish_live.sh "Update 2026 Georgia results" ga/data/live_2026.csv ga/data/live_status.json
