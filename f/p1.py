import sys, json
from playwright.sync_api import sync_playwright
O=sys.argv[1]
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
pages=['https://elections.wi.gov/elections/election-results','https://elections.wi.gov/elections/election-results/results-all']
for y,slug in [(2016,'2016-general-election'),(2018,'2018-general-election'),(2020,'2020-general-election'),(2022,'2022-general-election'),(2024,'2024-general-election')]:
    pages.append(f'https://elections.wi.gov/elections/election-results/{slug}')
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_context(user_agent=UA).new_page()
    out={}
    for u in pages:
        try:
            r=pg.goto(u,timeout=60000); pg.wait_for_timeout(4000)
            links=pg.evaluate("[...document.querySelectorAll('a')].map(a=>a.innerText.trim().replace(/\\s+/g,' ').slice(0,150)+' | '+a.href)")
            out[u]={'status':r.status if r else None,'title':pg.title(),'links':links}
            print(u, r.status if r else None, pg.title(), len(links))
        except Exception as e: print(u,'ERR',e)
    json.dump(out,open(O+'/pages.json','w'),indent=1)
    b.close()
