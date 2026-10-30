O=f/out1; mkdir -p $O
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
g(){ curl -sSL -A "$UA" -m 240 -o "$O/$1" -w "$1 %{http_code} %{size_download} %{url_effective}\n" "$2" >> $O/log.txt 2>>$O/err.txt; }
# results.arizona.vote
g arv_home.html https://results.arizona.vote/
g arv_robots.txt https://results.arizona.vote/robots.txt
for p in results/public/api/jurisdictions/Arizona api/elections api/v1/elections electionResults/ api/election; do g "arv_$(echo $p|tr / _).json" "https://results.arizona.vote/$p"; done
# azsos
g azsos_results.html https://azsos.gov/elections/results-data
g azsos_home.html https://azsos.gov/
g azsos_2024.html https://azsos.gov/elections/results-data/2024-election-results
# Archive CDX lists
for pat in 'azsos.gov/sites/default/files/*' 'apps.azsos.gov/election/*' 'results.arizona.vote/*'; do
  n=$(echo "$pat"|tr '/*' '__'); curl -sS -m 300 "https://web.archive.org/cdx/search/cdx?url=$pat&output=txt&fl=original,statuscode,timestamp,mimetype&collapse=urlkey&filter=statuscode:200&limit=60000" > $O/cdx_$n.txt 2>>$O/err.txt; sleep 4; done
# Census shapes
C=https://www2.census.gov/geo/tiger/GENZ
g cb_2020_county.zip $C2020/shp/cb_2020_us_county_500k.zip
g cb_2018_sldu.zip ${C}2018/shp/cb_2018_04_sldu_500k.zip
g cb_2022_sldu.zip ${C}2022/shp/cb_2022_04_sldu_500k.zip
g cb_2024_sldu.zip ${C}2024/shp/cb_2024_04_sldu_500k.zip
g cb_2018_cd116.zip ${C}2018/shp/cb_2018_us_cd116_500k.zip
g cb_2022_cd118.zip ${C}2022/shp/cb_2022_us_cd118_500k.zip
g cb_2020_county.zip ${C}2020/shp/cb_2020_us_county_500k.zip
# headless look at results site
cat > /tmp/pw.py <<'P'
import sys, json
from playwright.sync_api import sync_playwright
out=sys.argv[1]; reqs=[]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page()
    pg.on('request', lambda r: reqs.append(r.url))
    for u in ['https://results.arizona.vote/', 'https://azsos.gov/elections/results-data']:
        try:
            pg.goto(u, timeout=60000); pg.wait_for_timeout(8000)
            open(out+'/pw_'+u.split('/')[2]+'.html','w').write(pg.content())
        except Exception as e: reqs.append('ERR '+u+' '+str(e)[:200])
    b.close()
open(out+'/pw_requests.txt','w').write('\n'.join(reqs))
P
python3 /tmp/pw.py $O 2>>$O/err.txt
ls -la $O >> $O/log.txt
