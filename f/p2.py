import sys, json, re, os
from playwright.sync_api import sync_playwright
O=sys.argv[1]
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(user_agent=UA, accept_downloads=True); pg=ctx.new_page()
    allinks={}
    for n in range(0,12):
        u='https://elections.wi.gov/elections/election-results'+(f'?page={n}' if n else '')
        try:
            r=pg.goto(u,timeout=60000); pg.wait_for_timeout(3000)
            links=pg.evaluate("""[...document.querySelectorAll('.accordion, [id^=accordion], details, .views-row')].length ? [...document.querySelectorAll('a')].map(a=>{let s=a; let h=''; for(let i=0;i<8&&s;i++){s=s.parentElement; let t=s&&s.querySelector&&s.querySelector('h2,h3,button,summary'); if(t){h=t.innerText.trim().slice(0,90);break;}} return h+' || '+a.innerText.trim().replace(/\\s+/g,' ').slice(0,160)+' || '+a.href}) : []""")
            allinks[u]=links; print(u, r.status if r else None, pg.title(), len(links))
        except Exception as e: print(u,'ERR',e)
    json.dump(allinks,open(O+'/list.json','w'),indent=1)
    want=[]
    for u,ls in allinks.items():
        for l in ls:
            h,t,href=l.split(' || ')
            if re.search(r'(November|General Election).*(2016|2018|2020|2022|2024)|(2016|2018|2020|2022|2024).*(General|November)', h+' '+t, re.I) and re.search(r'\.(xlsx|xls|csv)', href, re.I):
                want.append(href)
    want=sorted(set(want)); print('files',len(want))
    for href in want:
        fn=re.sub(r'[^A-Za-z0-9._-]+','_',href.split('/')[-1].replace('%20',' '))
        try:
            r=ctx.request.get(href,timeout=180000)
            body=r.body(); ok=r.status==200 and body[:2]==b'PK'
            print(r.status, len(body), ok, fn)
            if ok: open(f'{O}/{fn}','wb').write(body)
        except Exception as e: print('ERR',fn,e)
    b.close()
