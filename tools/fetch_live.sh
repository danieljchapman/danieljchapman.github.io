#!/usr/bin/env bash
# One update: fetch results (one retry), check them, publish. Returns non-zero if nothing was published.
set -u
for attempt in 1 2; do
  python3 tools/importer.py --date 2026-11-03 --out data && break
  if [ "$attempt" = 2 ]; then git checkout -- data 2>/dev/null; exit 1; fi
  sleep 30
done
rows=$(($(wc -l < data/live_2026.csv) - 1))
echo "rows: $rows"
python3 -c "import json; s=json.load(open('data/live_status.json'))[0]; print({k: s.get(k) for k in ('phase','updated_at','races','called','counting')})"
if [ "$rows" -lt 1000 ]; then echo "Too few rows; not publishing"; git checkout -- data; exit 1; fi
bash tools/publish_live.sh
