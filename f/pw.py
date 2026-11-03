import json, sys, asyncio
from playwright.async_api import async_playwright
O = sys.argv[1]; URLS = sys.argv[2:]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36')
        reqs = []
        for i, u in enumerate(URLS):
            pg = await ctx.new_page(); pg.on('response', lambda r: reqs.append([r.status, r.url]))
            try:
                await pg.goto(u, timeout=60000); await pg.wait_for_timeout(12000)
                open(f'{O}/pw_{i}.html', 'w').write(await pg.content())
                json.dump([u] + await pg.eval_on_selector_all('a', 'els => els.map(e => [e.textContent.trim().slice(0,150), e.href])'), open(f'{O}/pw_{i}_links.json', 'w'), indent=0)
            except Exception as e:
                open(f'{O}/pw_{i}.err', 'w').write(str(e))
        json.dump(reqs, open(f'{O}/pw_requests.json', 'w'), indent=0)
        await b.close()
asyncio.run(main())
