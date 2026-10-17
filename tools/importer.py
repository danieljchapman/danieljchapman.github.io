#!/usr/bin/env python3
"""Election-night importer for the Texas Election Results dashboard.

Pulls Texas races for one election date from CivicAPI (civicapi.org) and writes:
  live_2026.csv     one row per race, area (county or district) and candidate
  live_status.json  phase, update time, source
Usage: python3 importer.py [--date 2026-11-03] [--out DIR]
The dashboard reads these two files; uploading them is done separately.
"""
import argparse, csv, json, os, re, subprocess, sys, time, datetime, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import local_live  # county election offices, for the Key Local Races tab
except ImportError:
    local_live = None

API = 'https://civicapi.org/api/v2'
STATEWIDE = {'Texas Governor': 'Governor', 'Texas US Senate': 'Senate', 'Texas Lieutenant Governor': 'Lt. Governor', 'Texas Railroad Commissioner': 'Railroad Commissioner',
             'Texas Attorney General': 'Attorney General', 'Texas Comptroller': 'Comptroller', 'Texas Land Commissioner': 'Land Commissioner',
             'Texas Agriculture Commissioner': 'Agriculture Commissioner'}
DISTRICT = [(r'^Texas State House (\d+)$', 'house', 'House', 'planh2316'), (r'^Texas State Senate (\d+)$', 'senate', 'Senate', 'plans2168'),
            (r'^Texas US House (\d+)$', 'ushouse', 'U.S. House', 'planc2333'), (r'^Texas State Board of Education (\d+)$', 'sboe', 'SBOE', 'plane2106')]
PARTY = {'republican': 'R', 'democratic': 'D', 'democrat': 'D', 'libertarian': 'L', 'green': 'G', 'independent': 'I'}
FIELDS = ['level', 'race', 'year', 'office', 'plan', 'unit', 'unit_name', 'candidate', 'party', 'votes', 'status', 'reporting', 'reporting_total']


def get(path, tries=4):
    """GET a CivicAPI path with retries (the service sometimes times out under load)."""
    last = None
    for i in range(tries):
        p = subprocess.run(['curl', '-sS', '-m', '45', '-w', '\n%{http_code}', API + path], capture_output=True, text=True)
        body, _, code = p.stdout.rpartition('\n')
        if code == '200':
            return json.loads(body)
        last = f'HTTP {code or "?"} {p.stderr.strip()[:120]} {body[:120]}'
        time.sleep(2 + 3 * i)
    raise RuntimeError(f'{path}: {last}')


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn' and c.isalnum())


def search(date):
    """All Texas races on the date. Large queries can time out, so fall back to narrower ones."""
    base = f'/race/search?country=US&province=TX&startDate={date}&endDate={date}'
    try:
        return get(base + '&limit=500')['races']
    except RuntimeError:
        races = {}
        for q in ['Texas State House', 'Texas State Senate', 'Texas US House', 'Texas State Board of Education', 'Texas Governor', 'Texas US Senate', 'Texas Lieutenant Governor',
                  'Texas Railroad Commissioner', 'Texas Attorney General', 'Texas Comptroller', 'Texas Land Commissioner', 'Texas Agriculture Commissioner', 'Texas Supreme Court']:
            for r in get(base + '&limit=200&query=' + q.replace(' ', '%20'))['races']:
                races[r['id']] = r
        return list(races.values())


def classify(name):
    if name in STATEWIDE:
        return ('statewide', STATEWIDE[name], '', None)
    m = re.match(r'^Texas Supreme Court (?:Place (\d+)|(Chief Justice))(.*)$', name, re.I)
    if m:
        seat = f'Place {m.group(1)}' if m.group(1) else 'Chief Justice'
        return ('statewide', f'Supreme Court, {seat}' + (' (unexpired term)' if re.search('unexpired', m.group(3), re.I) else ''), '', None)
    for pat, level, label, plan in DISTRICT:
        m = re.match(pat, name)
        if m:
            return (level, label, plan, int(m.group(1)))
    return None


def status_of(race):
    cands = race.get('candidates') or []
    if any(c.get('winner') for c in cands):
        return 'final'          # CivicAPI has called the race (unofficial until canvass)
    if any((c.get('votes') or 0) > 0 for c in cands):
        return 'counting'
    return 'pending'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default='2026-11-03')
    ap.add_argument('--out', default='.')
    ap.add_argument('--county-map', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tx_county_fips.json'))
    a = ap.parse_args()
    year = int(a.date[:4])
    fips = json.load(open(a.county_map))  # {normalized county name: fips}
    keep = lambda n: classify(n) and not re.search(r'primary|runoff', n, re.I) and (not re.search(r'special', n, re.I) or 'Supreme Court' in n)
    races = [r for r in search(a.date) if keep(r['election_name'])]
    rows, problems, n_called, n_counting = [], [], 0, 0
    for r in sorted(races, key=lambda x: x['election_name']):
        level, office, plan, district = classify(r['election_name'])
        try:
            d = get(f"/race/{r['id']}")
        except RuntimeError as e:
            problems.append(str(e)); continue
        time.sleep(0.1)
        st = status_of(d)
        n_called += st == 'final'; n_counting += st == 'counting'
        party = lambda c: PARTY.get(str(c.get('party') or '').lower(), 'O')
        if level == 'statewide':
            race_id = f'{year} {office}'
            regions = d.get('region_results') or {}
            if not regions:  # before results, list candidates once per county with zero votes
                regions = {k: {'name': k, 'candidates': [dict(c, votes=0) for c in d['candidates']], 'percent_reporting': 0} for k in fips}
            for key, reg in regions.items():
                f = fips.get(norm(key)) or fips.get(norm(reg.get('name', '')))
                if not f:
                    problems.append(f'unknown county {key} in {race_id}'); continue
                for c in reg.get('candidates') or []:
                    rows.append({'level': 'statewide', 'race': race_id, 'year': year, 'office': office, 'plan': '', 'unit': f, 'unit_name': reg.get('name', key),
                                 'candidate': c['name'], 'party': party(c), 'votes': c.get('votes') or 0, 'status': st,
                                 'reporting': reg.get('percent_reporting') if reg.get('percent_reporting') is not None else '', 'reporting_total': 100})
        else:
            race_id = f'{year} {office}'
            for c in d.get('candidates') or []:
                rows.append({'level': level, 'race': race_id, 'year': year, 'office': office, 'plan': plan, 'unit': district, 'unit_name': '',
                             'candidate': c['name'], 'party': party(c), 'votes': c.get('votes') or 0, 'status': st,
                             'reporting': d.get('percent_reporting') if d.get('percent_reporting') is not None else '', 'reporting_total': 100})
    local_problems = []
    if local_live:
        try:
            local_rows, local_problems = local_live.collect(a.date)
            rows += local_rows
        except Exception as e:  # never let the local races stop the statewide update
            local_problems = [f'local races: {str(e)[:160]}']
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'live_2026.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    phase = 'pre-election' if not n_counting and not n_called else 'final' if n_called == len(races) and races else 'counting'
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    json.dump([{'phase': phase, 'updated_at': now, 'source': 'CivicAPI (civicapi.org), unofficial', 'races': len(races), 'called': n_called,
                'counting': n_counting, 'problems': problems[:20], 'local_problems': local_problems[:20]}], open(os.path.join(a.out, 'live_status.json'), 'w'), indent=1)
    print(json.dumps({'races': len(races), 'rows': len(rows), 'phase': phase, 'called': n_called, 'counting': n_counting, 'problems': len(problems), 'local_rows': sum(r['level'] in ('local', 'fortbend') for r in rows)}))
    for p in local_problems[:10]: print('local:', p, file=sys.stderr)
    for p in problems[:10]: print('problem:', p, file=sys.stderr)


if __name__ == '__main__':
    main()
