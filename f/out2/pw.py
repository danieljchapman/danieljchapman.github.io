import json, asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(); reqs = []
        pg.on('request', lambda r: reqs.append([r.resource_type, r.method, r.url]))
        for u in ['https://floridaelectionwatch.gov/', 'https://floridaelectionwatch.gov/Downloads', 'https://floridaelectionwatch.gov/StateOffices/Governor', 'https://floridaelectionwatch.gov/ContestResultsByCounty/260872']:
            try:
                await pg.goto(u, wait_until='networkidle', timeout=60000)
                open('pw_' + u.rstrip('/').split('/')[-1].replace('.', '_') + '.html', 'w').write(await pg.content())
            except Exception as e: reqs.append(['err', u, str(e)])
        json.dump(reqs, open('pw_requests.json', 'w'), indent=1); await b.close()
asyncio.run(main())
