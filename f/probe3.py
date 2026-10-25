import sys, json
from playwright.sync_api import sync_playwright
out=sys.argv[1]
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
with sync_playwright() as p:
    b=p.chromium.launch(args=['--disable-blink-features=AutomationControlled']); ctx=b.new_context(user_agent=UA, accept_downloads=True)
    pg=ctx.new_page(); reqs=[]
    pg.on('request', lambda r: reqs.append(r.method+' '+r.url))
    pg.goto('https://liveresults.ohiosos.gov/',timeout=60000); pg.wait_for_timeout(6000)
    js=pg.evaluate("fetch('/bundles/all?v=JSfGTK5eih47h7E_RG-no5xAjQ36nwsCUekRiVvoXZM1').then(r=>r.text())")
    open(f'{out}/bundle.js','w').write(js)
    try:
        with pg.expect_download(timeout=90000) as d:
            pg.evaluate("downloadReport('VSSC1622XmlFileBlob')")
        dl=d.value; print('download', dl.url, dl.suggested_filename); dl.save_as(f'{out}/feed_'+dl.suggested_filename)
    except Exception as e: print('dl err', e)
    for path in ['/Home/GetStatewideOffices','/']: pass
    open(f'{out}/reqs.txt','w').write('\n'.join(reqs))
    open(f'{out}/cookies.json','w').write(json.dumps(ctx.cookies()))
    # main SOS site, wait longer
    pg2=ctx.new_page()
    try:
        pg2.goto('https://www.ohiosos.gov/elections/election-results-and-data/',timeout=60000)
        for i in range(25):
            pg2.wait_for_timeout(2000)
            if 'Just a moment' not in pg2.title(): break
        print('sos', pg2.title()); open(f'{out}/sos.html','w').write(pg2.content())
    except Exception as e: print('sos err',e)
    b.close()
