#!/bin/bash
# round 5: Crane A1 (2026 Senate) shapefile
O=f/out5; mkdir -p $O; cd $O
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
get(){ curl -sSL -A "$UA" -m 200 -o "$1" -w "$1 %{http_code} %{size_download}\n" "${@:2}" >> log.txt 2>>err.txt || echo "$1 FAIL $2" >> log.txt; }
B=https://www.michigan.gov/micrc/-/media/Project/Websites/MiCRC/405CraneA1
for n in 405_CraneA1_Map.pdf 405_CraneA1_Shapefile.zip 405_CraneA1_Shapefiles.zip 405_CraneA1_ShapeFiles.zip 405_CraneA1_Shape_Files.zip 405_CraneA1.zip 405_CraneA1_Shp.zip; do get g_$n $B/$n; done
cat > pw.py <<'PY'
import asyncio, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36')
        out = {}
        for u in ['https://www.michigan.gov/micrc/mapping-process-2024/final-remedial-state-senate-plan', 'https://www.michigan.gov/micrc/mapping-process-2024/final-remedial-state-house-plan']:
            try:
                r = await pg.goto(u, wait_until='networkidle', timeout=90000)
                out[u] = [r.status if r else None, await pg.eval_on_selector_all('a', 'els => els.map(e => [e.textContent.trim(), e.href])')]
            except Exception as e: out[u] = str(e)
        json.dump(out, open('links.json', 'w'), indent=1); await b.close()
asyncio.run(main())
PY
python3 pw.py 2>>err.txt
for h in $(python3 -c "
import json; d=json.load(open('links.json'))
for u,v in d.items():
  if isinstance(v,list):
    for t,h in v[1]:
      if '.zip' in h.lower(): print(h)" | sort -u); do get "pw_$(basename ${h%%\?*})" "$h"; done
ls -la > ls.txt
