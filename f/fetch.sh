#!/bin/bash
# round 2: FL DOS extract (POST), Election Watch downloads, 2026 congressional plan
O=f/out2; mkdir -p $O; cd $O
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
get(){ curl -sSL -A "$UA" -m 300 -o "$1" -w "$1 %{http_code} %{size_download}\n" "${@:2}" >> log.txt 2>>err.txt || echo "$1 FAIL $2" >> log.txt; }
for d in 11/8/2016:20161108 11/6/2018:20181106 11/3/2020:20201103 11/8/2022:20221108 11/5/2024:20241105; do
  md=${d%%:*}; ymd=${d##*:}
  get ex_$ymd.txt -X POST -d "ElectionDate=$md&OfficialResults=Y&PartyRaces=N&DataMode=&FormsButton2=Download" -e "https://results.elections.myflorida.com/downloadresults.asp?ElectionDate=$md&DATAMODE=" "https://results.elections.myflorida.com/ResultsExtract.Asp"
done
get ew_downloads.html https://floridaelectionwatch.gov/Downloads
get ew_home.html https://floridaelectionwatch.gov/
get ew_contest.html https://floridaelectionwatch.gov/ContestResultsByCounty/260872
get ew_fed.html https://floridaelectionwatch.gov/FederalOffices/USSenator
get EOGPCRP2026.zip https://www.flsenate.gov/PublishedContent/Session/Congressional/EOGPCRP2026.zip
get EOGPCRP2026.txt https://www.flsenate.gov/PublishedContent/Session/Congressional/EOGPCRP2026.txt
get bill_1D.html https://www.flsenate.gov/Session/Bill/2026D/1D
get bill_1D_ver.html https://flsenate.gov/Session/Bill/2026D/1D/ByVersion
get edr_index.html https://www.edr.state.fl.us/Content/redistricting/2026redistricting/index.cfm
get edr_memo.pdf https://www.edr.state.fl.us/Content/redistricting/2026redistricting/5.4.26JointMemotoEDRReCongressionalPlan.pdf
# grab every script referenced by Election Watch, to find its data API
for s in $(grep -oE 'src="[^"]+\.js[^"]*"' ew_home.html ew_downloads.html | sed 's/.*src="//; s/"$//' | sort -u | head -20); do
  case $s in http*) u=$s;; //*) u=https:$s;; *) u=https://floridaelectionwatch.gov/${s#/};; esac
  get "js_$(basename ${s%%\?*})" "$u"
done
# Playwright: record XHR/fetch calls the Election Watch pages make
cat > pw.py <<'PY'
import json, asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(); reqs = []
        pg.on('request', lambda r: reqs.append([r.resource_type, r.method, r.url]))
        for u in ['https://floridaelectionwatch.gov/', 'https://floridaelectionwatch.gov/Downloads', 'https://floridaelectionwatch.gov/StateOffices/Governor', 'https://floridaelectionwatch.gov/ContestResultsByCounty/260872']:
            try:
                await pg.goto(u, wait_until='networkidle', timeout=60000)
                open('pw_' + u.rstrip('/').split('/')[-1].replace('.', '_') + '.html', 'w').write(await pg.content())
            except Exception as e: reqs.append(['err', u, str(e)])
        json.dump(reqs, open('pw_requests.json', 'w'), indent=1); await b.close()
asyncio.run(main())
PY
python3 pw.py 2>> err.txt
ls -la > ls.txt
