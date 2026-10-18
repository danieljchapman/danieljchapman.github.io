import json, subprocess, urllib.parse, re, time, unicodedata
UA = 'TXElectionDashboard/1.0 (https://danieljchapman.github.io; election results site)'
WP = 'https://en.wikipedia.org/w/api.php'


def api(**p):
    p.update(format='json', formatversion='2', maxlag='5')
    url = WP + '?' + urllib.parse.urlencode(p)
    for i in range(25):
        r = subprocess.run(['curl', '-s', '-m', '40', '-A', UA, '-w', '\n%{http_code}', url], capture_output=True)
        body, _, code = r.stdout.rpartition(b'\n')
        if code == b'200':
            try:
                d = json.loads(body)
                if 'error' not in d:
                    return d
            except Exception:
                pass
        time.sleep(min(180, 5 * 2 ** i))
    raise RuntimeError('wikipedia unavailable')


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')


SUF = {'jr', 'sr', 'ii', 'iii', 'iv'}


def toks(name):
    name = re.sub(r'\(.*?\)', '', norm(name))
    nick = re.findall(r'["“]([^"”]+)["”]', name)
    name = re.sub(r'["“][^"”]+["”]', ' ', name)
    return [w for w in re.split(r'[\s.,]+', name) if w and w not in SUF], nick


def name_ok(cand, title):
    ct, nick = toks(cand)
    tt, _ = toks(title)
    if not ct or not tt:
        return False
    firsts = {ct[0]} | set(nick) | ({ct[1]} if len(ct) > 2 and len(ct[0]) <= 2 else set())
    return ct[-1].replace('-', ' ') in ' '.join(tt).replace('-', ' ') and any(f in tt for f in firsts)


OFF = re.compile(r'texas|congress|representative|senator|governor|attorney general|comptroller|commissioner|board of education|judge|mayor|council|legislat', re.I)


def good(n, p):
    ext = p.get('extract') or ''
    desc = p.get('description') or ''
    return (not p.get('missing')) and name_ok(n, p['title']) and re.search('texas', ext + desc, re.I) and OFF.search(ext + ' ' + desc) \
        and 'disambiguation' not in desc.lower() and 'may refer to' not in ext


def clean(n):
    return re.sub(r'\s+', ' ', re.sub(r'["“][^"”]+["”]|\b[A-Z]\.?(?=\s)', '', n)).strip()


cands = json.load(open('cands.json'))
out = {c['name']: {'cand': c, 'title': None, 'image': None} for c in cands}


def take(n, p):
    out[n].update(title=p['title'], image=p.get('pageimage'), desc=p.get('description'), extract=(p.get('extract') or '')[:300])


def batch_titles(variants):
    for i in range(0, len(variants), 20):
        chunk = variants[i:i + 20]
        d = api(action='query', titles='|'.join(t for _, t in chunk), redirects='1', prop='pageimages|description|extracts', piprop='name',
                exintro='1', explaintext='1', exsentences='3', exlimit='20')
        q = d.get('query', {})
        m = {}
        for x in q.get('normalized', []) + q.get('redirects', []):
            m[x['from']] = x['to']
        pages = {p['title']: p for p in q.get('pages', [])}
        for n, t in chunk:
            tt = m.get(m.get(t, t), m.get(t, t))
            p = pages.get(tt)
            if p and out[n]['title'] is None and good(n, p):
                take(n, p)
        time.sleep(3)


for suffix in ('', '(politician)', '(Texas politician)', '(American politician)'):
    todo = [n for n, v in out.items() if v['title'] is None]
    vs = []
    for n in todo:
        for base in {n, clean(n)}:
            vs.append((n, (base + ' ' + suffix).strip()))
    batch_titles(vs)
    print(suffix or 'exact', '->', sum(1 for v in out.values() if v['title']), flush=True)

todo = [n for n, v in out.items() if v['title'] is None]
print('searching', len(todo), flush=True)
for k, n in enumerate(todo):
    d = api(action='query', generator='search', gsrsearch=f'{clean(n)} Texas', gsrlimit='3', prop='pageimages|description|extracts', piprop='name',
            exintro='1', explaintext='1', exsentences='3', exlimit='3')
    for p in sorted(d.get('query', {}).get('pages', []), key=lambda p: p.get('index', 9)):
        if good(n, p):
            take(n, p)
            break
    if k % 40 == 0:
        json.dump(out, open('found.json', 'w'))
        print(k, flush=True)
    time.sleep(3)
json.dump(out, open('found.json', 'w'), indent=0)
print('articles', sum(1 for v in out.values() if v['title']), 'with image', sum(1 for v in out.values() if v['image']))
