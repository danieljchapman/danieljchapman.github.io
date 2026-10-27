"""Probe pollresults.org: save the OpenAPI schema and every 2026 Senate/House/governor poll (all pages)."""
import json, subprocess, time, sys
BASE = 'https://api.pollresults.org/v1.0'
def get(url):
    p = subprocess.run(['curl', '-sS', '-m', '60', '-w', '\n%{http_code}', '-D', '/tmp/h', url], capture_output=True, text=True)
    body, _, code = p.stdout.rpartition('\n')
    return code, body
code, body = get(BASE + '/openapi.json'); open('probe/openapi.json', 'w').write(body); print('openapi', code, len(body))
code, body = get(BASE + '/politics/results'); open('probe/root.json', 'w').write(body); print('root', code, body[:300])
print(open('/tmp/h').read())
for office in ['senate', 'house', 'governor']:
    pages, cursor, n = [], None, 0
    while True:
        url = f'{BASE}/politics/results/{office}?limit=100' + (f'&cursor={cursor}' if cursor else '')
        code, body = get(url)
        if code != '200':
            print(office, 'HTTP', code, body[:300]); break
        d = json.loads(body); pages.append(d)
        # find the cursor wherever it is
        nxt = None
        for k in ('next_cursor', 'cursor', 'next'):
            if isinstance(d, dict) and d.get(k): nxt = d[k]
        if isinstance(d, dict) and isinstance(d.get('pagination'), dict):
            pg = d['pagination']; nxt = pg.get('next_cursor') or pg.get('cursor') or pg.get('next')
        n += 1
        if not nxt or n > 200: break
        cursor = nxt; time.sleep(0.3)
    json.dump(pages, open(f'probe/{office}_pages.json', 'w'))
    print(office, 'pages', len(pages), 'keys', list(pages[0].keys()) if pages and isinstance(pages[0], dict) else type(pages[0]) if pages else None)
