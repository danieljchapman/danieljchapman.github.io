import json, sys, asyncio
from playwright.async_api import async_playwright
O = sys.argv[1]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36')
        pg = await ctx.new_page()
        reqs = []
        pg.on('response', lambda r: reqs.append([r.status, r.url]))
        for eid in ('122322', '127077'):
            await pg.goto(f'https://electionresults.iowa.gov/IA/{eid}/web.345435/#/summary', timeout=90000); await pg.wait_for_timeout(15000)
            base = f'https://electionresults.iowa.gov/IA/{eid}'
            r = await ctx.request.get(base + '/current_ver.txt'); ver = (await r.text()).strip(); print(eid, r.status, ver)
            for path in ['json/en/summary.json', 'json/en/electionsettings.json', 'reports/detailxml.zip', 'json/electionsettings.json', 'json/sum.json', 'json/details.json']:
                r = await ctx.request.get(f'{base}/{ver}/{path}')
                print(eid, path, r.status, len(await r.body()))
                if r.status == 200: open(f'{O}/{eid}_' + path.replace('/', '_'), 'wb').write(await r.body())
        json.dump(reqs, open(f'{O}/pw3_requests.json', 'w'), indent=0)
        await b.close()
asyncio.run(main())
