import asyncio, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36')
        out = {}
        for u in ['https://michigan.gov/micrc/mapping-process-2024/final-remedial-state-senate-plan', 'https://www.michigan.gov/micrc/mapping-process-2024', 'https://www.michigan.gov/micrc']:
            try:
                r = await pg.goto(u, wait_until='networkidle', timeout=90000)
                out[u] = [r.status if r else None, pg.url, await pg.eval_on_selector_all('a', 'els => els.map(e => [e.textContent.trim(), e.href])')]
            except Exception as e: out[u] = str(e)
        json.dump(out, open('links.json', 'w'), indent=1); await b.close()
asyncio.run(main())
