import json, asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(); reqs = []
        pg.on('request', lambda r: reqs.append([r.resource_type, r.method, r.url]))
        for i, u in enumerate(['https://mielections.us/election/results/2024GEN_CENR.html', 'https://mielections.us/election/results/2026GEN_CENR.html', 'https://mvic.sos.state.mi.us/votehistory/Index?type=C&electionDate=11-5-2024']):
            try:
                await pg.goto(u, wait_until='networkidle', timeout=60000); await pg.wait_for_timeout(3000)
                open(f'pw_{i}.html', 'w').write(await pg.content())
            except Exception as e: reqs.append(['err', u, str(e)])
        json.dump(reqs, open('pw_requests.json', 'w'), indent=1); await b.close()
asyncio.run(main())
