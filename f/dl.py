import sys, asyncio, os
from playwright.async_api import async_playwright
O = sys.argv[1]; urls = [l.strip() for l in open('f/urls.txt') if l.strip()]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36')
        pg = await ctx.new_page(); await pg.goto('https://sos.ks.gov/elections/election-results.html', timeout=60000); await pg.wait_for_timeout(5000)
        for u in urls:
            n = u.split('/')[-2] + '__' + u.split('/')[-1]
            try:
                r = await ctx.request.get(u, timeout=120000); body = await r.body()
                print(r.status, len(body), n, flush=True)
                if r.status == 200: open(os.path.join(O, n), 'wb').write(body)
            except Exception as e:
                print('ERR', n, e, flush=True)
        await b.close()
asyncio.run(main())
