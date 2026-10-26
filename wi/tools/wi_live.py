#!/usr/bin/env python3
"""Election-night importer for the Wisconsin page.

Wisconsin has no statewide election-night results feed: each county reports its own results, and the Elections Commission
publishes only the certified canvass weeks later. This reads CivicAPI (civicapi.org), which collects county results:
  /race/search?country=US&province=WI&startDate=2026-11-03&endDate=2026-11-03   the races
  /race/<id>                                                                     candidates, statewide and by county (region_results)
The ballot itself comes from candidates_2026.csv (built by build_candidates_2026.py from the Commission's certified primary
results and its ballot access report), so every race on the ballot is shown even when CivicAPI doesn't carry it: such races
get zero votes and stay 'pending' (as of Oct 26, 2026 CivicAPI listed the four statewide races but no Assembly or Senate races).
Before Election Day CivicAPI serves test numbers (test_data = true); those are set to zero.

Writes:
  live_2026.csv     level, race, year, office, plan, unit, unit_name, candidate, party, votes, status, reporting, reporting_total
                    statewide races by county (unit = county FIPS); Assembly ('house') and Senate by district (unit = district)
  live_status.json  phase, update time, source, problems
reporting is CivicAPI's percent of precincts reporting (reporting_total = 100).

Usage: python3 wi_live.py [--out DIR] [--keep-test]
"""
import argparse, csv, datetime, json, os, re, subprocess, sys, time, unicodedata
from collections import defaultdict

API = 'https://civicapi.org/api/v2'
DATE = '2026-11-03'
YEAR = 2026
STATEWIDE = {'Wisconsin Governor': 'Governor', 'Wisconsin Attorney General': 'Attorney General', 'Wisconsin Secretary of State': 'Secretary of State',
             'Wisconsin State Treasurer': 'Treasurer'}
DISTRICT = [(r'^Wisconsin State House (\d+)$', 'house', 'Assembly', 'a2024'), (r'^Wisconsin State Assembly (\d+)$', 'house', 'Assembly', 'a2024'),
            (r'^Wisconsin State Senate (\d+)$', 'senate', 'Senate', 's2024')]
PLAN = {'house': 'a2024', 'senate': 's2024'}
PARTY = {'republican': 'R', 'democratic': 'D', 'democrat': 'D', 'libertarian': 'L', 'green': 'G', 'wisconsin green': 'G', 'independent': 'I'}
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
    fips = json.load(open(os.path.join(HERE, 'wi_county_fips.json')))            # {county name: fips}
    by_norm = {norm(k): (k, v) for k, v in fips.items()}
    ballot = defaultdict(list)                                                     # (level, office, district) -> [(name, party)]
    for r in csv.DictReader(open(os.path.join(HERE, 'candidates_2026.csv'))):
        ballot[(r['level'], r['office'], int(r['district']) if r['district'] else None)].append((r['candidate'], r['party']))
    problems, rows, races, test_seen = [], [], {}, False
    civic = {}
    try:
        found = get(f'/race/search?country=US&province=WI&startDate={DATE}&endDate={DATE}&limit=500')['races']
        for r in found:
            c = classify(r['election_name'].strip())
            if c and not re.search(r'primary', r.get('election_type', '') + r['election_name'], re.I):
                civic[c] = r['id']
    except RuntimeError as e:
        problems.append(f'CivicAPI search: {str(e)[:160]}')
    for key in sorted(ballot, key=lambda k: (['statewide', 'senate', 'house'].index(k[0]), k[1], k[2] or 0)):
        level, office, d = key
        race = f'{YEAR} {office}'
        listed = ballot[key]
        detail = None
        if key in civic:
            try:
                detail = get(f'/race/{civic[key]}'); time.sleep(0.1)
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
                out.append((c['name'], PARTY.get(str(c.get('party') or '').lower(), 'W' if 'write' in c['name'].lower() else 'I'),
                            0 if zero else int(c.get('votes') or 0), bool(c.get('winner')) and not zero))
            return out
        all_c = merged(detail.get('candidates') if detail else [])
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
    missing = [k for k in ballot if k not in civic]
    if missing:
        lv = defaultdict(int)
        for k in missing:
            lv[k[0]] += 1
        problems.append('no live source yet for ' + ', '.join(f'{n} {"Assembly" if l == "house" else l.title()} race{"s" if n > 1 else ""}' for l, n in lv.items()))
    if test_seen and not a.keep_test:
        problems.append('CivicAPI still serves test numbers for some races (set to zero)')
    n_final = sum(s == 'final' for s in races.values()); n_count = sum(s == 'counting' for s in races.values())
    phase = 'pre-election' if not n_final and not n_count else 'final' if n_final == len(races) else 'counting'
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'live_2026.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    json.dump([{'phase': phase, 'updated_at': now, 'source': 'CivicAPI (county results), unofficial', 'races': len(races), 'called': n_final,
                'counting': n_count, 'problems': problems[:20], 'local_problems': []}], open(os.path.join(a.out, 'live_status.json'), 'w'), indent=1)
    print(json.dumps({'races': len(races), 'rows': len(rows), 'phase': phase, 'final': n_final, 'counting': n_count, 'civicapi_races': len(civic),
                      'problems': len(problems)}))
    for p in problems:
        print('problem:', p, file=sys.stderr)


if __name__ == '__main__':
    main()
