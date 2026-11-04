#!/usr/bin/env python3
"""Election-night importer for the Iowa page.

The Secretary of State's results site (electionresults.iowa.gov, Clarity) sits behind a Cloudflare challenge, so this reads
CivicAPI (civicapi.org), which collects Iowa results:
  /race/search?country=US&province=IA&startDate=2026-11-03&endDate=2026-11-03&limit=1000&query=<office>   the races, one search per
       office name (a search returns at most 1,000 races and Iowa lists more, mostly township and county offices; offsets repeat)
  /race/<id>                                                                     candidates, statewide and by county (region_results)
The ballot comes from candidates_2026.csv (build_candidates_2026.py), so every race on the ballot is shown even if CivicAPI drops
one: such races get zero votes and stay 'pending'. Before Election Day CivicAPI may serve test numbers (test_data = true); those
are set to zero.

Writes:
  live_2026.csv     level, race, year, office, plan, unit, unit_name, candidate, party, votes, status, reporting, reporting_total
                    statewide races by county (unit = county FIPS); U.S. House, Iowa House ('house') and Senate by district (unit = district)
  live_status.json  phase, update time, source, problems
reporting is CivicAPI's percent of precincts reporting (reporting_total = 100).

Usage: python3 ia_live.py [--out DIR] [--keep-test]
"""
import argparse, csv, datetime, json, os, re, subprocess, sys, time, unicodedata
from collections import defaultdict

API = 'https://civicapi.org/api/v2'
DATE = '2026-11-03'
YEAR = 2026
STATEWIDE = {'Iowa Governor': 'Governor', 'Iowa US Senate': 'Senate', 'Iowa Secretary of State': 'Secretary of State',
             'Iowa Attorney General': 'Attorney General', 'Iowa State Treasurer': 'Treasurer', 'Iowa State Auditor': 'Auditor',
             'Iowa Secretary of Agriculture': 'Secretary of Agriculture'}
DISTRICT = [(r'^Iowa US House (\d+)$', 'ushouse', 'U.S. House', 'c2022'), (r'^Iowa State Senate (\d+)$', 'senate', 'Senate', 's2022'),
            (r'^Iowa State House (\d+)$', 'house', 'House', 'h2022')]
PLAN = {'ushouse': 'c2022', 'house': 'h2022', 'senate': 's2022'}
PARTY = {'republican': 'R', 'democratic': 'D', 'democrat': 'D', 'libertarian': 'L', 'green': 'G', 'independent': 'I', 'nominated by petition': 'I',
         'no party': 'I', 'nonpartisan': 'I'}
QUERIES = ['Iowa State House', 'Iowa State Senate', 'Iowa US', 'Iowa Governor', 'Iowa Secretary', 'Iowa Attorney General', 'Iowa State Auditor',
           'Iowa State Treasurer']
FIELDS = ['level', 'race', 'year', 'office', 'plan', 'unit', 'unit_name', 'candidate', 'party', 'votes', 'status', 'reporting', 'reporting_total']
HERE = os.path.dirname(os.path.abspath(__file__))


def get(path, tries=4):
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
    return ''.join(c for c in unicodedata.normalize('NFD', str(s).lower()) if unicodedata.category(c) != 'Mn' and c.isalnum())


def last_name(s):
    parts = [p for p in re.split(r'\s+', re.sub(r',?\s+(Jr\.?|Sr\.?|II|III|IV)$', '', str(s).strip())) if p]
    return norm(parts[-1]) if parts else ''


def classify(name):
    if name in STATEWIDE:
        return 'statewide', STATEWIDE[name], None
    for pat, level, label, _ in DISTRICT:
        m = re.match(pat, name)
        if m:
            return level, label, int(m.group(1))
    return None


def status_of(cands):
    if any(c.get('winner') for c in cands):
        return 'final'          # CivicAPI has called the race (unofficial until the canvass)
    if any((c.get('votes') or 0) > 0 for c in cands):
        return 'counting'
    return 'pending'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='.')
    ap.add_argument('--keep-test', action='store_true', help="keep CivicAPI's test numbers (for checking the page)")
    a = ap.parse_args()
    fips = {v['name']: v['fips'] for v in json.load(open(os.path.join(HERE, 'ia_county_fips.json'))).values()}   # {county name: fips}
    by_norm = {norm(k): (k, v) for k, v in fips.items()}
    ballot = defaultdict(list)                                                     # (level, office, district) -> [(name, party)]
    for r in csv.DictReader(open(os.path.join(HERE, 'candidates_2026.csv'))):
        ballot[(r['level'], r['office'], int(r['district']) if r['district'] else None)].append((r['candidate'], r['party']))
    problems, rows, races, test_seen = [], [], {}, False
    # the last published rows: a race CivicAPI fails to send keeps them instead of dropping to zero votes
    prev, stale = [], set()
    try:
        prev = list(csv.DictReader(open(os.path.join(a.out, 'live_2026.csv'))))
    except OSError:
        pass
    civic = {}
    try:
        found = []
        for q in QUERIES:   # each office on its own, so one failed search doesn't lose the others
            try:
                found += get(f'/race/search?country=US&province=IA&startDate={DATE}&endDate={DATE}&limit=1000&query=' + q.replace(' ', '%20'))['races']
            except RuntimeError as e:
                problems.append(f'CivicAPI search ({q}): {str(e)[:120]}')
        for r in found:
            c = classify(r['election_name'].strip())
            if c and not re.search(r'primary', r.get('election_type', '') + r['election_name'], re.I):
                civic[c] = r   # the search result already has candidates, votes and percent reporting
    except RuntimeError as e:
        problems.append(f'CivicAPI search: {str(e)[:160]}')
    for key in sorted(ballot, key=lambda k: (['statewide', 'ushouse', 'senate', 'house'].index(k[0]), k[1], k[2] or 0)):
        level, office, d = key
        race = f'{YEAR} {office}'
        listed = ballot[key]
        detail = None
        if key in civic:
            try:
                # only statewide races need the full record (county results); district races use the search result,
                # which keeps each update to a few requests when CivicAPI is slow (Nov 3: 20-35 s per request)
                detail = get(f"/race/{civic[key]['id']}") if level == 'statewide' else civic[key]; time.sleep(0.1)
            except RuntimeError as e:
                problems.append(f'{race} {d or ""}: {str(e)[:120]}')
        test = bool(detail and detail.get('test_data'))
        test_seen |= test
        zero = test and not a.keep_test

        def merged(cands):
            """CivicAPI's candidates for one area, matched to the certified ballot by last name; ballot names and parties win."""
            got = {last_name(c['name']): c for c in cands or []}
            out = []
            for nm, p in listed:
                c = got.pop(last_name(nm), None)
                out.append((nm, p, 0 if zero or not c else int(c.get('votes') or 0), bool(c and c.get('winner')) and not zero))
            for c in got.values():                                                 # write-ins or candidates CivicAPI adds
                wi = 'write' in c['name'].lower()
                out.append(('Write-ins' if wi else c['name'], 'W' if wi else PARTY.get(str(c.get('party') or '').lower(), 'I'),
                            0 if zero else int(c.get('votes') or 0), bool(c.get('winner')) and not zero))
            return out
        all_c = merged(detail.get('candidates') if detail else [])
        if detail is None:
            stale.add((race, d))
        st = 'pending' if zero or not detail else status_of([{'winner': w, 'votes': v} for _, _, v, w in all_c])
        races[race + (f' {d}' if d else '')] = st
        if level == 'statewide':
            regions = {}
            for k, reg in ((detail or {}).get('region_results') or {}).items():
                f = reg.get('fips') or (by_norm.get(norm(reg.get('name', k))) or (None, None))[1]
                if reg.get('type', 'County') == 'County' and f:
                    regions[str(f)] = reg
            if detail and not regions and not zero and st != 'pending':
                problems.append(f'{race}: no county results yet')
            for cname, f in sorted(fips.items()):
                reg = regions.get(f)
                cands = merged(reg.get('candidates') if reg else [])
                rep = 0 if zero or not reg else reg.get('percent_reporting') or 0
                for nm, p, v, _ in sorted(cands, key=lambda c: -c[2]):
                    rows.append({'level': 'statewide', 'race': race, 'year': YEAR, 'office': office, 'plan': '', 'unit': f, 'unit_name': cname,
                                 'candidate': nm, 'party': p, 'votes': v, 'status': st, 'reporting': rep, 'reporting_total': 100})
            if regions and not zero:
                csum = defaultdict(int)
                for r in rows:
                    if r['race'] == race:
                        csum[last_name(r['candidate'])] += r['votes']
                off = [nm for nm, p, v, _ in all_c if csum.get(last_name(nm), 0) != v]
                if off:
                    problems.append(f'{race}: county sums differ from the statewide total for {", ".join(off[:3])}')
        else:
            rep = 0 if zero or not detail else detail.get('percent_reporting') or 0
            for nm, p, v, _ in sorted(all_c, key=lambda c: -c[2]):
                rows.append({'level': level, 'race': race, 'year': YEAR, 'office': office, 'plan': PLAN[level], 'unit': d, 'unit_name': '',
                             'candidate': nm, 'party': p, 'votes': v, 'status': st, 'reporting': rep, 'reporting_total': 100})
    kept = 0
    for race, d in stale:
        same = lambda r: r['race'] == race and (r['level'] == 'statewide' if d is None else r['level'] != 'statewide' and str(r['unit']) == str(d))
        old = [r for r in prev if same(r)]
        if not old or not any(int(r['votes'] or 0) for r in old):
            continue
        rows[:] = [r for r in rows if not same(r)] + old
        races[race + (f' {d}' if d else '')] = old[0]['status']; kept += 1
    if kept:
        problems.append(f'{kept} race{"s" if kept > 1 else ""} not sent by CivicAPI this time; kept the last published numbers')
    missing = [k for k in ballot if k not in civic]
    if missing:
        lv = defaultdict(int)
        for k in missing:
            lv[k[0]] += 1
        problems.append('no live source yet for ' + ', '.join(f'{n} {({"house": "Iowa House", "senate": "Iowa Senate", "ushouse": "U.S. House"}).get(l, l)} race{"s" if n > 1 else ""}' for l, n in lv.items()))
    if test_seen and not a.keep_test:
        problems.append('CivicAPI still serves test numbers for some races (set to zero)')
    n_final = sum(s == 'final' for s in races.values()); n_count = sum(s == 'counting' for s in races.values())
    phase = 'pre-election' if not n_final and not n_count else 'final' if n_final == len(races) else 'counting'
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'live_2026.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    json.dump([{'phase': phase, 'updated_at': now, 'source': 'CivicAPI, unofficial', 'races': len(races), 'called': n_final,
                'counting': n_count, 'problems': problems[:20], 'local_problems': []}], open(os.path.join(a.out, 'live_status.json'), 'w'), indent=1)
    print(json.dumps({'races': len(races), 'rows': len(rows), 'phase': phase, 'final': n_final, 'counting': n_count, 'civicapi_races': len(civic),
                      'problems': len(problems)}))
    for p in problems:
        print('problem:', p, file=sys.stderr)


if __name__ == '__main__':
    main()
