#!/usr/bin/env bash
# One Iowa update: fetch results (one retry), check them, publish. Non-zero if nothing was published.
set -u
# start from the latest published files, so a race CivicAPI fails to send can keep its last published numbers
git fetch -q origin main && git checkout origin/main -- ia/data/live_2026.csv ia/data/live_status.json 2>/dev/null || true
for attempt in 1 2; do
  python3 ia/tools/ia_live.py --out ia/data && break
  if [ "$attempt" = 2 ]; then git checkout -- ia/data 2>/dev/null; exit 1; fi
  sleep 30
done
rows=$(($(wc -l < ia/data/live_2026.csv) - 1))
echo "rows: $rows"
if [ "$rows" -lt 2000 ]; then echo "Too few rows; not publishing"; git checkout -- ia/data; exit 1; fi
bash tools/publish_live.sh "Update 2026 Iowa results" ia/data/live_2026.csv ia/data/live_status.json
