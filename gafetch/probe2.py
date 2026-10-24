import json, os, re, subprocess
from playwright.sync_api import sync_playwright
OUT = 'gafetch/out2'; os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'a')
def log(*a):
    s = ' '.join(str(x) for x in a); print(s); LOG.write(s + '\n'); LOG.flush()
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
SLUGS = ['2024NovGen', 'MunicipalGeneralSpecialElectionPSC11042025', '11032026GeneralAndSpecialElection']
with sync_playwright() as pw:
    b = pw.chromium.launch(); ctx = b.new_context(user_agent=UA, accept_downloads=True); pg = ctx.new_page()
    seen = []
    def on_resp(r):
        try:
            ct = r.headers.get('content-type', '')
            seen.append([r.status, r.request.method, r.url, ct, r.headers.get('content-length')])
            if 'json' in ct and '/api/' in r.url:
                body = r.body()
                fn = re.sub(r'[^A-Za-z0-9]+', '_', r.url.split('/api/', 1)[1])[:150] + '.json'
                open(os.path.join(OUT, fn), 'wb').write(body[:20_000_000])
        except Exception as e:
            seen.append(['err', str(e)[:100]])
    pg.on('response', on_resp)
    for slug in SLUGS:
        url = 'https://results.sos.ga.gov/results/public/Georgia/' + slug
        try:
            pg.goto(url, timeout=90000); pg.wait_for_timeout(10000)
            open(os.path.join(OUT, slug + '.html'), 'w').write(pg.content())
            btns = pg.eval_on_selector_all('button, a', 'els => els.map(e => [e.tagName, (e.textContent||"").trim().slice(0,60), e.getAttribute("href"), e.getAttribute("aria-label")])')
            json.dump(btns, open(os.path.join(OUT, slug + '_buttons.json'), 'w'), indent=0)
            log('page', slug, pg.title(), len(btns))
            for label in ['Export', 'Download', 'Reports']:
                loc = pg.get_by_text(label, exact=False)
                log(' text', label, loc.count())
        except Exception as e:
            log('goto fail', slug, repr(e)[:200])
    json.dump(seen, open(os.path.join(OUT, 'network.json'), 'w'), indent=0)
    # does plain curl work?
    for u in ['https://results.sos.ga.gov/results/public/api/jurisdictions/Georgia']:
        p = subprocess.run(['curl', '-s', '-A', UA, '-o', '/dev/null', '-w', '%{http_code}', u], capture_output=True, text=True)
        log('curl', u, p.stdout)
    b.close()
