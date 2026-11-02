#!/bin/bash
# round 1: probe Michigan results sites; Census shapes
O=f/out1; mkdir -p $O; cd $O
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
get(){ curl -sSL -A "$UA" -m 300 -o "$1" -w "$1 %{http_code} %{size_download}\n" "${@:2}" >> log.txt 2>>err.txt || echo "$1 FAIL $2" >> log.txt; }
for y in 2016 2018 2020 2022 2024 2026; do get mie_$y.html https://mielections.us/election/results/${y}GEN_CENR.html; done
get mie_root.html https://mielections.us/election/results/
get mvic_2024.html "https://mvic.sos.state.mi.us/votehistory/Index?type=C&electionDate=11-5-2024"
get mvic_home.html https://mvic.sos.state.mi.us/votehistory/
get boe_precinct.html https://miboecfr.nictusa.com/cgi-bin/cfr/precinct_srch.cgi
get sos_bycounty.html https://www.michigan.gov/sos/elections/election-results-and-data/candidate-listings-and-election-results-by-county
get micrc_maps.html https://www.michigan.gov/micrc/mapping-process-2021/final-maps
get micrc_home.html https://www.michigan.gov/micrc
B=https://www2.census.gov/geo/tiger/GENZ
get cb_2018_us_cd116_500k.zip ${B}2018/shp/cb_2018_us_cd116_500k.zip
get cb_2022_us_cd118_500k.zip ${B}2022/shp/cb_2022_us_cd118_500k.zip
for y in 2016 2018 2022 2024; do get cb_${y}_sldu.zip ${B}$y/shp/cb_${y}_26_sldu_500k.zip; get cb_${y}_sldl.zip ${B}$y/shp/cb_${y}_26_sldl_500k.zip; done
get tl_2025_26_sldu.zip https://www2.census.gov/geo/tiger/TIGER2025/SLDU/tl_2025_26_sldu.zip
get tl_2025_26_sldl.zip https://www2.census.gov/geo/tiger/TIGER2025/SLDL/tl_2025_26_sldl.zip
# Playwright: record requests made by the results pages
cat > pw.py <<'PY'
import json, asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(); reqs = []
        pg.on('request', lambda r: reqs.append([r.resource_type, r.method, r.url]))
        for i, u in enumerate(['https://mielections.us/election/results/2024GEN_CENR.html', 'https://mielections.us/election/results/2026GEN_CENR.html', 'https://mvic.sos.state.mi.us/votehistory/Index?type=C&electionDate=11-5-2024']):
            try:
                await pg.goto(u, wait_until='networkidle', timeout=60000); await pg.wait_for_timeout(3000)
                open(f'pw_{i}.html', 'w').write(await pg.content())
            except Exception as e: reqs.append(['err', u, str(e)])
        json.dump(reqs, open('pw_requests.json', 'w'), indent=1); await b.close()
asyncio.run(main())
PY
python3 pw.py 2>> err.txt
ls -la > ls.txt
