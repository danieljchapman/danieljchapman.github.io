"""Election-night results for the Key Local Races tab, read from county election offices.

Each source is read on its own; one county failing (site down, file not posted yet) never
stops the others. Rows use the same columns as live_2026.csv:
  level 'local'    one row per race, county part and choice (areas: harris, tarrant, collin, ...)
  level 'fortbend' one row per Fort Bend race, voting precinct and candidate (for the precinct map)
Sources:
  Clarity ENR (results.enr.clarityelections.com): Tarrant, Denton, Williamson, Travis, Dallas, Fort Bend
  Harris County Clerk cumulative PDF (appfiles.harrisvotes.com), read with pdftotext
  Collin County results CSV linked from collincountytx.gov/elections/election-results
"""
import csv, datetime, io, json, re, subprocess, xml.etree.ElementTree as ET, zipfile

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
CLARITY = 'https://results.enr.clarityelections.com/TX'
PARTY = {'REP': 'R', 'DEM': 'D', 'LIB': 'L', 'GRN': 'G', 'GRE': 'G', 'IND': 'I'}
HARRIS_PDF = 'https://appfiles.harrisvotes.com/harrisvotes/prd/Data/{mmyy}/cumulative.pdf'
COLLIN_PAGE = 'https://www.collincountytx.gov/elections/election-results'
# Clarity's per-county election lists can lag behind the result pages, so known ids come first,
# then the list, then any Clarity link on the county's own results page.
KNOWN_EID = {('Fort_Bend', '2026-11-03'): '127480', ('Tarrant', '2026-11-03'): '127297'}
COUNTY_PAGES = {'Travis': 'https://votetravis.gov/current-election-information/election-results-and-reconciliation-forms/',
                'Denton': 'https://www.votedenton.gov/election-results-and-maps/election-results/',
                'Dallas': 'https://www.dallascounty.org/departments/elections/results/',
                'Tarrant': 'https://www.tarrantcountytx.gov/en/elections/past-election-information/2026-archives/november-3--2026--joint-general-and-special-election-results.html',
                'Fort_Bend': 'https://www.fortbendcountytx.gov/government/departments/elections-voter-registration/2026-election-results'}
CIVIC = {('williamson', 'County Judge'): 56120, ('denton', 'County Judge'): 55904}  # fallback race ids

# area, office, [(source, county part, contest pattern)]
RACES = [
    ('harris', 'County Judge', [('harris', 'Harris', r'^County Judge$')]),
    ('tarrant', 'County Judge', [('clarity:Tarrant', 'Tarrant', r'^County Judge$')]),
    ('tarrant', 'Commissioner Pct 2', [('clarity:Tarrant', 'Tarrant', r'^County Commissioner,? Precinct (No\. )?2\b')]),
    ('tarrant', 'Commissioner Pct 4', [('clarity:Tarrant', 'Tarrant', r'^County Commissioner,? Precinct (No\. )?4\b')]),
    ('collin', 'County Judge', [('collin', 'Collin', r'^County Judge\b')]),
    ('williamson', 'County Judge', [('clarity:Williamson', 'Williamson', r'^County Judge$')]),
    ('denton', 'County Judge', [('clarity:Denton', 'Denton', r'^County Judge$')]),
    ('austin', 'Proposition A', [('clarity:Travis', 'Travis', r'City of Austin,? Proposition A\b'), ('clarity:Williamson', 'Williamson', r'City of Austin,? Proposition A\b')]),
    ('austin', 'Proposition G', [('clarity:Travis', 'Travis', r'City of Austin,? Proposition G\b'), ('clarity:Williamson', 'Williamson', r'City of Austin,? Proposition G\b')]),
    ('dallas', 'Proposition A', [('clarity:Dallas', 'Dallas', r'City of Dallas,? (Texas,? )?Proposition A\b'), ('collin', 'Collin', r'City of Dallas.*Proposition A\b'),
                                 ('clarity:Denton', 'Denton', r'City of Dallas,? (Texas,? )?Proposition A\b')]),
]
FORT_BEND = [('County Judge', r'^COUNTY JUDGE$'), ('Commissioner Pct 2', r'^COUNTY COMMISSIONER PRECINCT 2\b'), ('Commissioner Pct 4', r'^COUNTY COMMISSIONER PRECINCT 4\b')]


def fetch(url, binary=False, tries=3):
    code = '?'
    for _ in range(tries):
        p = subprocess.run(['curl', '-s', '--compressed', '-L', '-m', '90', '-A', UA, '-w', '\n%{http_code}', url], capture_output=True)
        body, _, code = p.stdout.rpartition(b'\n')
        if code == b'200':
            return body if binary else body.decode('utf-8', 'replace')
    raise RuntimeError(f'{url}: HTTP {code.decode() if isinstance(code, bytes) else code}')


def nice(name):
    """'REP DANIEL WONG' -> 'Daniel Wong'; leaves mixed-case names alone."""
    name = re.sub(r'^(REP|DEM|LIB|GRN|GRE|IND)\s+', '', name.strip())
    if name.upper() != name:
        return name
    out = []
    for w in name.lower().split():
        w = '-'.join(p[:1].upper() + p[1:] for p in w.split('-'))
        w = re.sub(r"^(Mc|O')([a-z])", lambda m: m.group(1) + m.group(2).upper(), w)
        out.append(w)
    return ' '.join(out)


def choice_name(name):
    n = nice(name)
    if re.search(r'write-?in', n, re.I):
        return 'Write-ins'
    return {'for': 'For', 'against': 'Against', 'yes': 'For', 'no': 'Against'}.get(n.lower(), n)


# ---------- sources: each returns {contest name: {'choices': [(name, party, votes)], 'reporting': (done, total) or None, 'final': bool}}
def clarity_eid(county, date):
    if (county, date) in KNOWN_EID:
        return KNOWN_EID[(county, date)]
    d = datetime.date.fromisoformat(date)
    want = f'{d.month}/{d.day}/{d.year} '
    es = [e for e in json.loads(fetch(f'{CLARITY}/{county}/elections.json')) if e['Date'].startswith(want)]
    es.sort(key=lambda e: ('primary' in e['ElectionName'].lower() or 'runoff' in e['ElectionName'].lower(), -int(e['EID'])))
    if es:
        return es[0]['EID']
    if county in COUNTY_PAGES:  # newest election linked from the county's own page, if it is newer than any listed
        try:
            ids = [int(x) for x in re.findall(rf'clarityelections\.com/TX/{county}/(\d+)', fetch(COUNTY_PAGES[county]))]
            listed = [int(e['EID']) for e in json.loads(fetch(f'{CLARITY}/{county}/elections.json'))]
            if ids and max(ids) > max(listed or [0]):
                return str(max(ids))
        except RuntimeError:
            pass
    raise RuntimeError(f'{county}: no Clarity election on {date} yet')


def clarity(county, date):
    eid = clarity_eid(county, date)
    ver = fetch(f'{CLARITY}/{county}/{eid}/current_ver.txt').strip()
    out = {}
    for c in json.loads(fetch(f'{CLARITY}/{county}/{eid}/{ver}/json/en/summary.json')):
        pr, tp = c.get('PR') or 0, c.get('TP') or 0
        out[c['C']] = {'choices': [(choice_name(n), PARTY.get((p or '').upper(), ''), v) for n, p, v in zip(c['CH'], c.get('P') or [''] * len(c['CH']), c['V'])],
                       'reporting': (pr, tp) if tp else None, 'final': bool(tp) and pr >= tp}
    return out


HART = re.compile(r'^(\S.*?)\s{2,}(?:(REP|DEM|LIB|GRN|GRE|IND)\s+)?(?:[\d,]+\s+[\d.]+%\s+)*([\d,]+)\s+([\d.]+)%\s*$')


def harris(date):
    d = datetime.date.fromisoformat(date)
    pdf = fetch(HARRIS_PDF.format(mmyy=f'{d.month:02d}{d.year % 100:02d}'), binary=True)
    txt = subprocess.run(['pdftotext', '-layout', '-', '-'], input=pdf, capture_output=True, check=True).stdout.decode('utf-8', 'replace')
    rep = re.search(r'Precincts Reporting\s+([\d,]+)\s+of\s+([\d,]+)', txt)
    reporting = (int(rep.group(1).replace(',', '')), int(rep.group(2).replace(',', ''))) if rep else None
    if re.search(r'Zero Cumulative|L&A', txt[:2000]):
        pass  # pre-election test report: candidates with zero votes
    lines, out, cur = txt.splitlines(), {}, None
    for i, l in enumerate(lines):
        if re.match(r'^\s*Choice\s+Party', l):
            j = i - 1
            while j > 0 and not lines[j].strip():
                j -= 1
            cur = out.setdefault(re.sub(r'\s+-\s+Vote for.*$', '', lines[j].strip()), {'choices': [], 'reporting': reporting, 'final': False})
            continue
        if cur is None or re.search(r'Cast Votes:|Undervotes:|Overvotes:', l):
            continue
        m = HART.match(l.rstrip())
        if m and not any(c[0] == choice_name(m.group(1)) for c in cur['choices']):
            nm = m.group(1).strip()
            cur['choices'].append((choice_name(nm), PARTY.get(m.group(2) or '', 'W' if '(W)' in nm or 'WRITE-IN' in nm.upper() else ''), int(m.group(3).replace(',', ''))))
    return out


def collin(date):
    d = datetime.date.fromisoformat(date)
    page = fetch(COLLIN_PAGE)
    month = d.strftime('%B').lower()
    links = [h.replace('&amp;', '&') for h in re.findall(r'href="([^"]+\.csv[^"]*)"', page, re.I)]
    links = [h for h in links if re.search(rf'{month}-{d.day}(st|nd|rd|th)?-{d.year}', h, re.I) or re.search(rf'{d:%m%d%Y}|{d:%Y%m%d}', h)]
    if not links:
        raise RuntimeError(f'Collin: no results CSV for {date} posted yet')
    url = links[0] if links[0].startswith('http') else 'https://www.collincountytx.gov' + links[0]
    rows = list(csv.reader(io.StringIO(fetch(url))))
    head, cand = rows[0], rows[2]
    totals = next(r for r in rows if len(r) > 2 and r[1] == 'ZZZ')
    final = False  # the file name does not reliably say when counting is done
    out = {}
    for i, contest in enumerate(head):
        if i < 6 or not contest.strip() or re.search(r'OVER VOTES|UNDER VOTES', cand[i], re.I):
            continue
        m = re.match(r'^(REP|DEM|LIB|GRN|GRE|IND)\s+(.*)$', cand[i].strip())
        name, party = (m.group(2), PARTY[m.group(1)]) if m else (cand[i].strip(), '')
        o = out.setdefault(contest.strip(), {'choices': [], 'reporting': None, 'final': final})
        o['choices'].append((choice_name(name), party, int(totals[i] or 0)))
    return out


def civic(race_id):
    d = json.loads(fetch(f'https://civicapi.org/api/v2/race/{race_id}'))
    cands = d.get('candidates') or []
    called = any(c.get('winner') for c in cands)
    return {'choices': [(c['name'], PARTY.get(str(c.get('party') or '').upper()[:3], ''), c.get('votes') or 0) for c in cands], 'reporting': None, 'final': called,
            'pct': d.get('percent_reporting')}


def fort_bend_precincts(date, year):
    eid = clarity_eid('Fort_Bend', date)
    ver = fetch(f'{CLARITY}/Fort_Bend/{eid}/current_ver.txt').strip()
    z = zipfile.ZipFile(io.BytesIO(fetch(f'{CLARITY}/Fort_Bend/{eid}/{ver}/reports/detailxml.zip', binary=True)))
    root = ET.fromstring(z.read(z.namelist()[0]))
    rows = []
    for office, pat in FORT_BEND:
        c = next((c for c in root.iter('Contest') if re.search(pat, c.get('text', ''), re.I)), None)
        if c is None:
            continue
        done, total = int(c.get('precinctsReported') or 0), int(c.get('precinctsReporting') or 0)
        status = 'final' if total and done >= total else 'counting' if any(int(ch.get('totalVotes') or 0) for ch in c.iter('Choice')) else 'pending'
        for ch in c.iter('Choice'):
            per = {}
            for vt in ch.findall('VoteType'):
                for p in vt.findall('Precinct'):
                    per[p.get('name')] = per.get(p.get('name'), 0) + int(p.get('votes') or 0)
            for prec, v in per.items():
                rows.append({'level': 'fortbend', 'race': f'{year} {office}', 'year': year, 'office': office, 'plan': 'p26', 'unit': prec, 'unit_name': '',
                             'candidate': nice(ch.get('text')), 'party': PARTY.get((ch.get('party') or '').upper(), ''), 'votes': v, 'status': status,
                             'reporting': done, 'reporting_total': total})
    return rows


def collect(date):
    """All local rows plus a list of problems (sources that could not be read)."""
    year = int(date[:4])
    cache, problems, rows = {}, [], []

    def source(key):
        if key not in cache:
            try:
                cache[key] = clarity(key.split(':')[1], date) if key.startswith('clarity:') else harris(date) if key == 'harris' else collin(date)
            except Exception as e:  # noqa: BLE001 - a county being unreachable is expected
                cache[key] = None
                problems.append(f'{key}: {str(e)[:160]}')
        return cache[key]

    for area, office, parts in RACES:
        got = 0
        for key, part, pat in parts:
            data = source(key)
            hit = next((v for k, v in (data or {}).items() if re.search(pat, k, re.I)), None)
            if not hit:
                if data is not None:
                    problems.append(f'{key}: no contest matching {pat}')
                continue
            got += 1
            votes = sum(v for _, _, v in hit['choices'])
            status = 'final' if hit['final'] and votes else 'counting' if votes else 'pending'
            rep = hit['reporting']
            for name, party, v in hit['choices']:
                rows.append({'level': 'local', 'race': f'{year} {area} {office}', 'year': year, 'office': office, 'plan': area, 'unit': part, 'unit_name': part,
                             'candidate': name, 'party': party, 'votes': v, 'status': status,
                             'reporting': rep[0] if rep else '', 'reporting_total': rep[1] if rep else ''})
        if not got and (area, office) in CIVIC:
            try:
                hit = civic(CIVIC[(area, office)])
                votes = sum(v for _, _, v in hit['choices'])
                part = area.title()
                for name, party, v in hit['choices']:
                    rows.append({'level': 'local', 'race': f'{year} {area} {office}', 'year': year, 'office': office, 'plan': area, 'unit': part, 'unit_name': part,
                                 'candidate': name, 'party': party, 'votes': v, 'status': 'final' if hit['final'] else 'counting' if votes else 'pending',
                                 'reporting': hit['pct'] if hit['pct'] is not None else '', 'reporting_total': 100 if hit['pct'] is not None else ''})
            except Exception as e:  # noqa: BLE001
                problems.append(f'civicapi {area} {office}: {str(e)[:120]}')
    try:
        rows += fort_bend_precincts(date, year)
    except Exception as e:  # noqa: BLE001
        problems.append(f'fort bend: {str(e)[:160]}')
    return rows, problems


if __name__ == '__main__':
    import sys
    rows, problems = collect(sys.argv[1] if len(sys.argv) > 1 else '2026-11-03')
    seen = {}
    for r in rows:
        if r['level'] == 'local':
            seen.setdefault((r['race'], r['unit'], r['status'], r['reporting'], r['reporting_total']), []).append((r['candidate'], r['party'], r['votes']))
    for k, v in seen.items():
        print(k, v)
    print('fortbend rows', sum(r['level'] == 'fortbend' for r in rows))
    for p in problems:
        print('problem:', p)
