import sys, json, re
from playwright.sync_api import sync_playwright
O=sys.argv[1]
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(user_agent=UA, accept_downloads=True); pg=ctx.new_page()
    for u in ['https://www.redistricting.ohio.gov/maps','https://www.redistricting.ohio.gov/']:
        try:
            pg.goto(u,timeout=60000); pg.wait_for_timeout(6000)
            links=pg.evaluate("[...document.querySelectorAll('a')].map(a=>a.innerText.trim().slice(0,120)+' | '+a.href)")
            open(O+'/redist_links.txt','a').write(u+'\n'+'\n'.join(links)+'\n')
        except Exception as e: print(u,e)
    # live site API calls
    pg.goto('https://liveresults.ohiosos.gov/',timeout=60000); pg.wait_for_timeout(5000)
    for path in ['Api/v1/Contest/getTabs','Api/v1/Contest/getContestList','Api/v1/Contest/getCountyList','Api/v1/Contest/getStatistics','Api/v1/Contest/getReportList','Api/v1/Contest/getBallotsCastByCounty']:
        try:
            t=pg.evaluate(f"fetch('/{path}').then(r=>r.status+' '+r.headers.get('content-type')+'\\n'+r.text())")
            open(O+'/live_'+path.split('/')[-1]+'.txt','w').write(t[:400000]); print(path, t[:80].replace('\n',' '))
        except Exception as e: print(path,e)
    ck=ctx.cookies(); open(O+'/live_cookies.json','w').write(json.dumps(ck))
    b.close()
