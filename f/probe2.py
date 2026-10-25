import sys
from playwright.sync_api import sync_playwright
out=sys.argv[1]
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36')
    pg=ctx.new_page()
    for i,u in enumerate(['https://www.ohiosos.gov/elections/election-results-and-data/','https://liveresults.ohiosos.gov/']):
        try:
            r=pg.goto(u,timeout=60000); pg.wait_for_timeout(8000)
            open(f'{out}/pw{i}.html','w').write(pg.content()); print(u, r.status if r else None, pg.title())
        except Exception as e: print(u,'ERR',e)
    b.close()
