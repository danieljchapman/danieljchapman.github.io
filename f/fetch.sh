#!/bin/bash
# round 6: more guesses for the Crane A1 shapefile; page without www
O=f/out6; mkdir -p $O; cd $O
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
B=https://www.michigan.gov/micrc/-/media/Project/Websites/MiCRC/405CraneA1
for s in Shape Shapes SHP Shp shp ShapeFile Shape_File Shapefile_ GIS Shapefiles_ BAF BlockAssignment Block_Assignment Population Data VRA_Data PartisanFairness; do
  for e in zip csv xlsx txt; do
    c=$(curl -s -A "$UA" -m 30 -o /dev/null -w '%{http_code}' "$B/405_CraneA1_$s.$e"); [ "$c" = 200 ] && { echo "HIT 405_CraneA1_$s.$e" >> log.txt; curl -s -A "$UA" -m 120 -o "405_CraneA1_$s.$e" "$B/405_CraneA1_$s.$e"; }
  done
done
cat > pw.py <<'PY'
import asyncio, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36')
        out = {}
        for u in ['https://michigan.gov/micrc/mapping-process-2024/final-remedial-state-senate-plan', 'https://www.michigan.gov/micrc/mapping-process-2024', 'https://www.michigan.gov/micrc']:
            try:
                r = await pg.goto(u, wait_until='networkidle', timeout=90000)
                out[u] = [r.status if r else None, pg.url, await pg.eval_on_selector_all('a', 'els => els.map(e => [e.textContent.trim(), e.href])')]
            except Exception as e: out[u] = str(e)
        json.dump(out, open('links.json', 'w'), indent=1); await b.close()
asyncio.run(main())
PY
python3 pw.py 2>>err.txt
for h in $(python3 -c "
import json; d=json.load(open('links.json'))
for u,v in d.items():
  if isinstance(v,list):
    for t,h in v[2]:
      if '.zip' in h.lower(): print(h)" | sort -u | head -20); do curl -sSL -A "$UA" -m 200 -o "pw_$(basename ${h%%\?*})" "$h"; echo "got $h" >> log.txt; done
echo done >> log.txt; ls -la > ls.txt
