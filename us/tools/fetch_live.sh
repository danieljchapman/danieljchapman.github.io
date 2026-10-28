#!/usr/bin/env bash
# One national update: fetch results (one retry), check them, publish. Non-zero if nothing was published.
set -u
for attempt in 1 2; do
  python3 us/tools/us_live.py --out us/data && break
  if [ "$attempt" = 2 ]; then git checkout -- us/data 2>/dev/null; exit 1; fi
  sleep 30
done
rows=$(($(wc -l < us/data/live_2026.csv) - 1))
echo "rows: $rows"
if [ "$rows" -lt 1200 ]; then echo "Too few rows; not publishing"; git checkout -- us/data; exit 1; fi
# retro plain-HTML pages (us/retro/) from the same files; a failure here never blocks the main update
python3 us/tools/us_retro.py --data us/data --out us/retro || { echo "::warning::retro pages not rebuilt"; git checkout -- us/retro 2>/dev/null; }
bash tools/publish_live.sh "Update 2026 national results" us/data/live_2026.csv us/data/live_status.json us/retro
