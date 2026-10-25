#!/usr/bin/env bash
# One Ohio update: fetch results (one retry), check them, publish. Non-zero if nothing was published.
set -u
for attempt in 1 2; do
  python3 oh/tools/oh_live.py --out oh/data && break
  if [ "$attempt" = 2 ]; then git checkout -- oh/data 2>/dev/null; exit 1; fi
  sleep 30
done
rows=$(($(wc -l < oh/data/live_2026.csv) - 1))
echo "rows: $rows"
if [ "$rows" -lt 1000 ]; then echo "Too few rows; not publishing"; git checkout -- oh/data; exit 1; fi
bash tools/publish_live.sh "Update 2026 Ohio results" oh/data/live_2026.csv oh/data/live_status.json
