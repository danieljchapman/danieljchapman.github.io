import sys, json, re, os
from playwright.sync_api import sync_playwright
O=sys.argv[1]
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
with sync_playwright() as p:
    b=p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    ctx=b.new_context(accept_downloads=True); pg=ctx.new_page()
    # redistricting map packages
    pg.goto('https://www.redistricting.ohio.gov/maps',timeout=60000); pg.wait_for_timeout(5000)
    info=pg.evaluate("[...document.querySelectorAll('a')].filter(a=>a.href.includes('/download')).map(a=>{let c=a.closest('div,li,tr,article');return (c?c.innerText:'').replace(/\\s+/g,' ').slice(0,300)+' || '+a.href})")
    open(O+'/redist_cards.txt','w').write('\n'.join(info))
    for n in [430,428,427,425,424]:
        try:
            r=ctx.request.get(f'https://www.redistricting.ohio.gov/api/public/districtmaps/{n}/download',timeout=120000)
            cd=r.headers.get('content-disposition',''); print(n,r.status,cd,len(r.body()))
            fn=re.findall(r'filename="?([^";]+)',cd); open(f'{O}/map{n}_'+(fn[0] if fn else 'x.bin'),'wb').write(r.body())
        except Exception as e: print(n,e)
    # official SOS results pages, headed
    for i,u in enumerate(['https://www.ohiosos.gov/elections/election-results-and-data/']):
        pg.goto(u,timeout=90000)
        for k in range(30):
            pg.wait_for_timeout(2000)
            if 'Just a moment' not in pg.title(): break
        print('sos',pg.title())
        open(f'{O}/sos{i}.html','w').write(pg.content())
        links=pg.evaluate("[...document.querySelectorAll('a')].map(a=>a.innerText.trim().slice(0,100)+' | '+a.href)")
        open(f'{O}/sos_links.txt','w').write('\n'.join(links))
    b.close()
