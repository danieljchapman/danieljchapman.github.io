#!/usr/bin/env python3
"""Election-night importer for the Florida page.

Source: the Florida Division of Elections' election-night results file, posted with Florida Election Watch
(floridaelectionwatch.gov/Downloads): a tab-delimited file of every race by county, with precincts and precincts
reporting per race and county:
  https://flelectionfiles.floridados.gov/enightfilespublic/20261103_ElecResultsFL.txt
It is a plain download (no bot check). Before polls close it lists every candidate with zero votes.

Winners with no opponent are not on the general-election ballot and so not in the file; they are added from
unopposed.csv (the Division's candidate list, status "Unopposed") as decided races without vote totals.

Writes:
  live_2026.csv     level, race, year, office, plan, unit, unit_name, candidate, party, votes, status, reporting, reporting_total
                    statewide races by county (unit = county FIPS); U.S. House, Florida House and Senate by district (unit = district)
  live_status.json  phase, update time, source, problems
reporting / reporting_total are precincts reported / precincts for that race (a county's, or summed over a district's counties).
A race is final when every precinct has reported. Write-in candidates are combined as 'Write-ins'.

Fallback (election night, Nov 3 2026, owner's choice): while the Division's file still has no votes at all, the vote counts come
from CivicAPI (civicapi.org), which collects county results sooner. The state file still supplies the ballot, counties and
precinct totals; CivicAPI's votes are matched to it by last name, and its percent reporting is turned into precincts
(percent x the race's precincts). Once the state file has any votes, it is used alone again. --no-civic turns this off.

Usage: python3 fl_live.py [--file FILE] [--out DIR] [--no-civic]
"""
import argparse, csv, datetime, io, json, os, re, sys, time, unicodedata, urllib.request
from collections import defaultdict

URL = 'https://flelectionfiles.floridados.gov/enightfilespublic/20261103_ElecResultsFL.txt'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36'
FIELDS = ['level', 'race', 'year', 'office', 'plan', 'unit', 'unit_name', 'candidate', 'party', 'votes', 'status', 'reporting', 'reporting_total']
STATEWIDE = {'USS': 'Senate', 'GOV': 'Governor', 'ATG': 'Attorney General', 'CFO': 'Chief Financial Officer', 'AGR': 'Agriculture Commissioner',
             'PRE': 'President'}
DISTRICT = {'USR': ('ushouse', 'U.S. House', 'c2026', 28), 'STS': ('senate', 'Senate', 's2022', 21), 'STR': ('house', 'House', 'h2022', 120)}
PARTY = {'REP': 'R', 'DEM': 'D', 'LPF': 'L', 'GRE': 'G', 'CPF': 'C', 'NPA': 'I', 'IND': 'I', 'NOP': 'N', 'WRI': 'W'}  # others: O
# governor tickets: the file gives the surnames only ("Donalds" / "Avila"); full names from the Division's candidate list
TICKET = {'Donalds': 'Byron Donalds', 'Jolly': 'David Jolly', 'Jewett': 'Scott Jewett', 'Abrams': 'Dean Abrams', 'Burkett': 'Charles Burkett',
          'Datto': 'Jeffrey "Dr. Jeff" Datto', 'Dimanche': 'Moliere "Moe" Dimanche', 'Russo': 'Frank J. Russo'}
YEAR = 2026
ORDER = {'R': 0, 'D': 1}   # before votes come in, list Republican and Democrat first, write-ins last


def key(kv):
    (nm, p), v = kv
    return (-v, ORDER.get(p, 3 if p == 'W' else 2), nm)


def fetch():
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(f'{URL}?t={int(time.time())}', headers={'User-Agent': UA, 'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except Exception as e:
            last = e; time.sleep(10)
    raise RuntimeError(f'feed: {last}')


def name(x, ticket):
    f, m, l = (x.get('CanNameFirst') or '').strip(), (x.get('CanNameMiddle') or '').strip(), (x.get('CanNameLast') or '').strip()
    if ticket:   # "Top-of-ticket surname" in the first-name field, running mate's surname in the last-name field
        return TICKET.get(f, f)
    keep = m and (len(m.rstrip('.')) <= 2 or m[0] in '\'"(')
    return ' '.join(p for p in (f, m if keep else '', l) if p)


def build(text, cty, unopp):
    problems = []
    rd = list(csv.DictReader(io.StringIO(text), delimiter='\t', quoting=csv.QUOTE_NONE))
    if not rd or 'CanVotes' not in rd[0]:
        raise RuntimeError('unexpected file layout')
    dates = {x['ElectionDate'] for x in rd}
    if dates != {'11/03/2026'}:
        problems.append(f'election dates in file: {sorted(dates)}')
    sw = defaultdict(lambda: defaultdict(int))          # (office, county) -> (cand, party) -> votes
    sw_prec = {}                                        # (office, county) -> (reporting, total)
    di = defaultdict(lambda: defaultdict(int))          # (level, district) -> (cand, party) -> votes
    di_prec = defaultdict(dict)                         # (level, district) -> county -> (reporting, total)
    for x in rd:
        rc = x['RaceCode'].strip()
        if rc not in STATEWIDE and rc not in DISTRICT:
            continue
        cc = x['CountyCode'].strip()
        if cc not in cty:
            problems.append(f'unknown county {cc}'); continue
        p = PARTY.get(x['PartyCode'].strip(), 'O')
        nm = 'Write-ins' if p == 'W' else name(x, rc in ('GOV', 'PRE'))
        v = int(x['CanVotes'] or 0)
        prec = (int(x['PrecinctsReporting'] or 0), int(x['Precincts'] or 0))
        if rc in STATEWIDE:
            k = (STATEWIDE[rc], cc); sw[k][(nm, p)] += v; sw_prec[k] = prec
        else:
            try:
                d = int(x['Juris1num'])
            except ValueError:
                problems.append(f'{rc}: no district number'); continue
            k = (DISTRICT[rc][0], d); di[k][(nm, p)] += v; di_prec[k][cc] = prec
    rows, races = [], {}
    offices = sorted({o for o, _ in sw})
    for office in offices:
        cs = sorted([c for o, c in sw if o == office], key=lambda c: cty[c]['name'])
        if len(cs) != len(cty):
            problems.append(f'{office}: {len(cs)} of {len(cty)} counties')
        got = sum(sw_prec[(office, c)][0] for c in cs); tot = sum(sw_prec[(office, c)][1] for c in cs)
        votes = sum(v for c in cs for v in sw[(office, c)].values())
        st = 'final' if votes and tot and got >= tot else 'counting' if votes else 'pending'
        race = f'{YEAR} {office}'; races[race] = st
        for c in cs:
            g, t = sw_prec[(office, c)]
            for (nm, p), v in sorted(sw[(office, c)].items(), key=key):
                rows.append({'level': 'statewide', 'race': race, 'year': YEAR, 'office': office, 'plan': '', 'unit': cty[c]['fips'], 'unit_name': cty[c]['name'],
                             'candidate': nm, 'party': p, 'votes': v, 'status': st, 'reporting': g, 'reporting_total': t})
    for (lvl, d) in sorted(di):
        label, plan = next((L, P) for l, L, P, n in DISTRICT.values() if l == lvl)
        got = sum(g for g, t in di_prec[(lvl, d)].values()); tot = sum(t for g, t in di_prec[(lvl, d)].values())
        votes = sum(di[(lvl, d)].values())
        st = 'final' if votes and tot and got >= tot else 'counting' if votes else 'pending'
        race = f'{YEAR} {label}'; races[f'{race} {d}'] = st
        for (nm, p), v in sorted(di[(lvl, d)].items(), key=key):
            rows.append({'level': lvl, 'race': race, 'year': YEAR, 'office': label, 'plan': plan, 'unit': d, 'unit_name': '',
                         'candidate': nm, 'party': p, 'votes': v, 'status': st, 'reporting': got, 'reporting_total': tot})
    # unopposed winners (not on the ballot)
    for r in unopp:
        lvl, d = r['level'], int(r['district'])
        label, plan = next((L, P) for l, L, P, n in DISTRICT.values() if l == lvl)
        if (lvl, d) in di:
            problems.append(f'{lvl} {d}: listed as unopposed but on the ballot'); continue
        races[f'{YEAR} {label} {d}'] = 'final'
        rows.append({'level': lvl, 'race': f'{YEAR} {label}', 'year': YEAR, 'office': label, 'plan': plan, 'unit': d, 'unit_name': '',
                     'candidate': r['candidate'], 'party': r['party'], 'votes': '', 'status': 'final', 'reporting': '', 'reporting_total': ''})
    for l, L, P, n in DISTRICT.values():
        have = len({r['unit'] for r in rows if r['level'] == l})
        if have != n:
            problems.append(f'{l}: {have} of {n} districts')
    if len(offices) != 5:
        problems.append(f'{len(offices)} statewide races (expected 5)')
    gov = [sw_prec[k] for k in sw_prec if k[0] == 'Governor']
    prec = [sum(g for g, t in gov), sum(t for g, t in gov)]
    return rows, races, problems, prec


CIVIC = 'https://civicapi.org/api/v2'
CIVIC_STATEWIDE = {'Florida Governor': 'Governor', 'Florida US Senate Special': 'Senate', 'Florida US Senate': 'Senate',
                   'Florida Attorney General': 'Attorney General', 'Florida Chief Financial Officer': 'Chief Financial Officer',
                   'Florida Commissioner of Agriculture': 'Agriculture Commissioner'}
CIVIC_DISTRICT = [(r'^Florida US House (\d+)$', 'ushouse'), (r'^Florida State Senate (\d+)(?: Special)?$', 'senate'), (r'^Florida State House (\d+)$', 'house')]


def civic_get(path):
    last = None
    for i in range(3):
        try:
            req = urllib.request.Request(CIVIC + path, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            last = e; time.sleep(3 + 3 * i)
    raise RuntimeError(f'CivicAPI {path}: {last}')


def _norm(x):
    return ''.join(c for c in unicodedata.normalize('NFD', str(x).lower()) if unicodedata.category(c) != 'Mn' and c.isalnum())


def _last(x):
    parts = [p for p in re.split(r'\s+', re.sub(r',?\s+(Jr\.?|Sr\.?|II|III|IV)$', '', str(x).strip())) if p]
    return _norm(parts[-1]) if parts else ''


def civic_overlay(rows, cty, problems):
    """Fill the state file's rows with CivicAPI's votes. Returns the number of races filled."""
    found = civic_get('/race/search?country=US&province=FL&startDate=2026-11-03&endDate=2026-11-03&limit=1000')['races']
    sw, di = {}, {}
    for r in found:
        nm = r['election_name'].strip()
        if nm in CIVIC_STATEWIDE:
            sw[CIVIC_STATEWIDE[nm]] = r
            continue
        for pat, lvl in CIVIC_DISTRICT:
            m = re.match(pat, nm)
            if m:
                di[(lvl, int(m.group(1)))] = r
    if any(r.get('test_data') for r in list(sw.values()) + list(di.values())):
        problems.append('CivicAPI marks some races as test data; not used')
        return 0
    by_name = {_norm(v['name']): v['fips'] for v in cty.values()}

    def fill(rs, cands, pct):
        got = {}
        for c in cands or []:
            k = 'writeins' if 'write' in c['name'].lower() else _last(c['name'])
            got[k] = got.get(k, 0) + int(c.get('votes') or 0)
        win = {('writeins' if 'write' in c['name'].lower() else _last(c['name'])) for c in cands or [] if c.get('winner')}
        any_votes = sum(got.values()) > 0
        for r in rs:
            k = 'writeins' if r['candidate'] == 'Write-ins' else _last(r['candidate'])
            r['votes'] = got.get(k, 0)
            t = int(r['reporting_total'] or 0)
            r['reporting'] = min(t, round((pct or 0) / 100 * t))
            r['status'] = 'final' if win else 'counting' if any_votes else 'pending'
        return any_votes

    n = 0
    groups = defaultdict(list)
    for r in rows:
        if r['votes'] == '':
            continue   # unopposed
        groups[(r['level'], r['office'] if r['level'] == 'statewide' else int(r['unit']))].append(r)
    for office, race in sw.items():
        try:
            det = civic_get(f"/race/{race['id']}")
        except RuntimeError as e:
            problems.append(str(e)[:160]); continue
        regions = {}
        for k, reg in (det.get('region_results') or {}).items():
            f = reg.get('fips') or by_name.get(_norm(re.sub(r'\s+County$', '', reg.get('name', k))))
            if f:
                regions[str(f)] = reg
        rs = groups.get(('statewide', office), [])
        if not regions:
            problems.append(f'{office}: CivicAPI has no county results'); continue
        filled = False
        for f in {r['unit'] for r in rs}:
            reg = regions.get(str(f))
            filled |= fill([r for r in rs if r['unit'] == f], reg.get('candidates') if reg else [], reg.get('percent_reporting') if reg else 0)
        win = any(c.get('winner') for c in det.get('candidates') or [])
        if win:
            for r in rs:
                r['status'] = 'final'
        n += filled
    for key, race in di.items():
        rs = groups.get(key)
        if rs:
            n += fill(rs, race.get('candidates'), race.get('percent_reporting'))
    # statewide status is per race, not per county: counting if any county has votes
    for (lvl, k), rs in groups.items():
        if lvl == 'statewide' and any(r['status'] != 'final' for r in rs):
            st = 'counting' if any(r['votes'] for r in rs) else 'pending'
            for r in rs:
                r['status'] = st
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-civic', action='store_true', help="don't fall back to CivicAPI while the state file has no votes")
    ap.add_argument('--file', help='read this results file instead of downloading')
    ap.add_argument('--out', default='.')
    a = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    cty = json.load(open(os.path.join(here, 'fl_county_fips.json')))
    unopp = [r for r in csv.DictReader(open(os.path.join(here, 'unopposed.csv'))) if r['year'] == str(YEAR)]
    raw = open(a.file, 'rb').read() if a.file else fetch()
    rows, races, problems, prec = build(raw.decode('cp1252', errors='replace'), cty, unopp)
    if not races:
        raise SystemExit('no statewide or district races found; not writing')
    source = 'Florida Division of Elections, unofficial'
    if not a.no_civic and not any(r['votes'] for r in rows if r['votes'] != ''):
        try:
            if civic_overlay(rows, cty, problems):
                source = "CivicAPI, unofficial (until the Division of Elections' file has votes)"
                for r in rows:
                    key = r['race'] if r['level'] == 'statewide' else f"{r['race']} {r['unit']}"
                    if r['votes'] != '':
                        races[key] = r['status']
                gov = {r['unit']: (r['reporting'], r['reporting_total']) for r in rows if r['office'] == 'Governor'}
                prec = [sum(int(g) for g, t in gov.values()), sum(int(t) for g, t in gov.values())]
        except Exception as e:
            problems.append(f'CivicAPI fallback: {str(e)[:160]}')
    unopposed = {f"{r['race']} {r['unit']}" for r in rows if r['votes'] == ''}
    contested = [k for k in races if k not in unopposed]
    n_final = sum(races[k] == 'final' for k in contested)
    n_count = sum(races[k] == 'counting' for k in contested)
    phase = 'pre-election' if not n_final and not n_count else 'final' if n_final == len(contested) else 'counting'
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'live_2026.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    json.dump([{'phase': phase, 'updated_at': now, 'source': source, 'races': len(races), 'called': n_final,
                'counting': n_count, 'precincts': prec, 'problems': problems[:20], 'local_problems': []}],
              open(os.path.join(a.out, 'live_status.json'), 'w'), indent=1)
    print(json.dumps({'races': len(races), 'contested': len(contested), 'rows': len(rows), 'phase': phase, 'final': n_final, 'counting': n_count,
                      'precincts': prec, 'problems': len(problems)}))
    for p in problems:
        print('problem:', p, file=sys.stderr)


if __name__ == '__main__':
    main()
