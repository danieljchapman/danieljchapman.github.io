"""Fetches Georgia source files from sites the workspace can't reach (run on GitHub Actions)."""
import io, json, os, re, subprocess, sys, time, zipfile
from playwright.sync_api import sync_playwright

OUT = 'gafetch/out'
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'a')
def log(*a):
    s = ' '.join(str(x) for x in a); print(s); LOG.write(s + '\n'); LOG.flush()

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
WANT = ['11/8/2016', '11/6/2018', '12/4/2018', '11/3/2020', '1/5/2021', '11/8/2022', '12/6/2022', '11/5/2024', '11/4/2025']

def clarity(pw):
    b = pw.chromium.launch(); ctx = b.new_context(user_agent=UA); pg = ctx.new_page()
    try:
        pg.goto('https://results.enr.clarityelections.com/GA/', timeout=60000)
    except Exception as e:
        log('clarity goto', e)
    for _ in range(20):
        pg.wait_for_timeout(1000)
        if any(c['name'] == 'aws-waf-token' for c in ctx.cookies()): break
    log('cookies', [c['name'] for c in ctx.cookies()])
    def get(url):
        r = ctx.request.get(url, headers={'User-Agent': UA}, timeout=120000)
        return r.status, r.body()
    st, body = get('https://results.enr.clarityelections.com/GA/elections.json')
    log('elections.json', st, len(body))
    elections = []
    if st == 200:
        open(os.path.join(OUT, 'clarity_elections.json'), 'wb').write(body)
        elections = json.loads(body)
    for e in elections:
        d = str(e.get('Date', '')).split(' ')[0]
        if d in WANT:
            log('match', e)
    for e in elections:
        d = str(e.get('Date', '')).split(' ')[0]
        if d not in WANT: continue
        name = e.get('ElectionName', ''); eid = str(e['EID'])
        if re.search(r'special|primary', name, re.I) and not re.search(r'general', name, re.I): continue
        st, ver = get(f'https://results.enr.clarityelections.com/GA/{eid}/current_ver.txt')
        if st != 200: log('ver', eid, st); continue
        ver = ver.decode().strip()
        tag = d.replace('/', '-') + '_' + eid
        for path, fn in [('json/en/summary.json', 'summary.json'), ('reports/detailxml.zip', 'detailxml.zip'), ('json/en/electionsettings.json', 'settings.json')]:
            st, body = get(f'https://results.enr.clarityelections.com/GA/{eid}/{ver}/{path}')
            log(tag, path, st, len(body))
            if st == 200: open(os.path.join(OUT, f'clarity_{tag}_{fn}'), 'wb').write(body)
    b.close()

def enhanced(pw):
    b = pw.chromium.launch(); ctx = b.new_context(user_agent=UA); pg = ctx.new_page()
    seen = []
    def on_resp(r):
        try:
            ct = r.headers.get('content-type', '')
            seen.append([r.status, r.request.method, r.url, ct])
            if 'json' in ct and len(seen) < 400:
                body = r.body()
                fn = re.sub(r'[^A-Za-z0-9]+', '_', r.url.split('://', 1)[1])[:150] + '.json'
                open(os.path.join(OUT, 'ev_' + fn), 'wb').write(body[:3_000_000])
        except Exception as e:
            seen.append(['err', str(e)[:100]])
    pg.on('response', on_resp)
    for url in ['https://results.sos.ga.gov/results/public/Georgia', 'https://results.sos.ga.gov/results/public/Georgia/elections']:
        try:
            pg.goto(url, timeout=60000); pg.wait_for_timeout(8000)
            log('ev page', url, pg.url, pg.title())
            open(os.path.join(OUT, 'ev_page_' + url.rsplit('/', 1)[1] + '.html'), 'w').write(pg.content())
            links = pg.eval_on_selector_all('a', 'els => els.map(e => [e.textContent.trim(), e.href])')
            json.dump(links, open(os.path.join(OUT, 'ev_links_' + url.rsplit('/', 1)[1] + '.json'), 'w'), indent=0)
        except Exception as e:
            log('ev goto', url, e)
    json.dump(seen, open(os.path.join(OUT, 'ev_network.json'), 'w'), indent=0)
    b.close()

def census():
    import shapefile
    files = {'county': 'https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_county_500k.zip',
             'cd115': 'https://www2.census.gov/geo/tiger/GENZ2016/shp/cb_2016_us_cd115_500k.zip',
             'cd118': 'https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_cd118_500k.zip',
             'cd119': 'https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_cd119_500k.zip',
             'sldl2018': 'https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_13_sldl_500k.zip',
             'sldu2018': 'https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_13_sldu_500k.zip',
             'sldl2016': 'https://www2.census.gov/geo/tiger/GENZ2016/shp/cb_2016_13_sldl_500k.zip',
             'sldu2016': 'https://www2.census.gov/geo/tiger/GENZ2016/shp/cb_2016_13_sldu_500k.zip',
             'sldl2022': 'https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_13_sldl_500k.zip',
             'sldu2022': 'https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_13_sldu_500k.zip',
             'sldl2024': 'https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_13_sldl_500k.zip',
             'sldu2024': 'https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_13_sldu_500k.zip',
             'sldl2024t': 'https://www2.census.gov/geo/tiger/TIGER2024/SLDL/tl_2024_13_sldl.zip',
             'sldu2024t': 'https://www2.census.gov/geo/tiger/TIGER2024/SLDU/tl_2024_13_sldu.zip'}
    for key, url in files.items():
        p = subprocess.run(['curl', '-sS', '-L', '-m', '300', '-A', UA, '-w', '\n%{http_code}', url], capture_output=True)
        body, _, code = p.stdout.rpartition(b'\n')
        log('census', key, code.decode(), len(body))
        if code != b'200': continue
        z = zipfile.ZipFile(io.BytesIO(body))
        base = next(n[:-4] for n in z.namelist() if n.endswith('.shp'))
        r = shapefile.Reader(shp=io.BytesIO(z.read(base + '.shp')), dbf=io.BytesIO(z.read(base + '.dbf')), shx=io.BytesIO(z.read(base + '.shx')))
        fields = [f[0] for f in r.fields[1:]]
        feats = []
        for sr in r.iterShapeRecords():
            rec = dict(zip(fields, sr.record))
            if str(rec.get('STATEFP')) != '13': continue
            feats.append({'type': 'Feature', 'properties': {k: (v if isinstance(v, (int, float, str)) else str(v)) for k, v in rec.items()}, 'geometry': sr.shape.__geo_interface__})
        json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(OUT, f'shape_{key}.geojson'), 'w'))
        log('  features', len(feats), fields)

if __name__ == '__main__':
    what = sys.argv[1:] or ['census', 'clarity', 'enhanced']
    if 'census' in what:
        try: census()
        except Exception as e: log('census failed', repr(e))
    with sync_playwright() as pw:
        for name, fn in [('clarity', clarity), ('enhanced', enhanced)]:
            if name in what:
                try: fn(pw)
                except Exception as e: log(name, 'failed', repr(e))
