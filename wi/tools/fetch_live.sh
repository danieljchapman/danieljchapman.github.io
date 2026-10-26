#!/usr/bin/env bash
# One Wisconsin update: fetch results (one retry), check them, publish. Non-zero if nothing was published.
set -u
for attempt in 1 2; do
  python3 wi/tools/wi_live.py --out wi/data && break
  if [ "$attempt" = 2 ]; then git checkout -- wi/data 2>/dev/null; exit 1; fi
  sleep 30
done
rows=$(($(wc -l < wi/data/live_2026.csv) - 1))
echo "rows: $rows"
if [ "$rows" -lt 800 ]; then echo "Too few rows; not publishing"; git checkout -- wi/data; exit 1; fi
bash tools/publish_live.sh "Update 2026 Wisconsin results" wi/data/live_2026.csv wi/data/live_status.json
