O=f/out2; mkdir -p $O
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
g(){ curl -sSL -A "$UA" -m 300 -o "$O/$1" -w "$1 %{http_code} %{size_download} %{content_type} %{url_effective}\n" "$2" >> $O/log.txt 2>>$O/err.txt; }
g node248.html https://azsos.gov/node/248
g node875.html https://azsos.gov/node/875
g elec_results.html https://azsos.gov/elections/results-data
g elec_hist.html https://azsos.gov/elections/election-results
g canvass2026ev.html https://azsos.gov/events/official-statewide-canvass-november-3-2026-general/921
for u in docs/2024_General_State_Canvass.pdf 2024_General_State_Canvass.pdf 2022_General_State_Canvass.pdf 2022_General_Canvass.pdf docs/2022_General_State_Canvass.pdf 2020_General_State_Canvass.pdf 2020_1130_General_Canvass.pdf 2018_General_State_Canvass.pdf 2018_1203_Signed_Official_Canvass.pdf 2016_General_State_Canvass.pdf 2016_general_state_canvass.pdf; do g "try_$(basename $u)" "https://azsos.gov/sites/default/files/$u"; done
for u in 'azsos.gov/sites/default/files/*' 'azsos.gov/elections/*' 'azsos.gov/sites/default/files/docs/*'; do
  n=$(echo "$u"|tr '/*' '__'); for t in 1 2 3; do curl -sS -m 300 "https://web.archive.org/cdx/search/cdx?url=$u&output=txt&fl=original,statuscode,timestamp,mimetype&collapse=urlkey&filter=statuscode:200&limit=60000" > $O/cdx_$n.txt 2>>$O/err.txt; grep -q 'Temporarily Offline' $O/cdx_$n.txt || break; sleep 60; done; sleep 5; done
cat > /tmp/pw.py <<'P'
import sys
from playwright.sync_api import sync_playwright
out=sys.argv[1]; reqs=[]
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'); pg=ctx.new_page()
    def onresp(r):
        reqs.append(f'{r.status} {r.url}')
        try:
            if any(k in r.url for k in ['.json','api','data','Data']) and r.status==200:
                n=out+'/pwresp_'+str(len(reqs))+'.txt'; open(n,'wb').write(r.body()[:3000000]); reqs.append('  saved '+n)
        except Exception as e: pass
    pg.on('response', onresp)
    for u in ['https://results.arizona.vote/', 'https://results.arizona.vote/#/featured/47/0']:
        try:
            pg.goto(u, timeout=90000); pg.wait_for_timeout(15000)
            open(out+'/pw_'+str(len(reqs))+'.html','w').write(pg.content())
        except Exception as e: reqs.append('ERR '+u+' '+str(e)[:300])
    b.close()
open(out+'/pw_requests.txt','w').write('\n'.join(reqs))
P
python3 /tmp/pw.py $O 2>>$O/err.txt
