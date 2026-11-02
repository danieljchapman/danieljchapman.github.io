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

Usage: python3 fl_live.py [--file FILE] [--out DIR]
"""
import argparse, csv, datetime, io, json, os, sys, time, urllib.request
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


def main():
    ap = argparse.ArgumentParser()
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
    unopposed = {f"{r['race']} {r['unit']}" for r in rows if r['votes'] == ''}
    contested = [k for k in races if k not in unopposed]
    n_final = sum(races[k] == 'final' for k in contested)
    n_count = sum(races[k] == 'counting' for k in contested)
    phase = 'pre-election' if not n_final and not n_count else 'final' if n_final == len(contested) else 'counting'
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'live_2026.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    json.dump([{'phase': phase, 'updated_at': now, 'source': 'Florida Division of Elections, unofficial', 'races': len(races), 'called': n_final,
                'counting': n_count, 'precincts': prec, 'problems': problems[:20], 'local_problems': []}],
              open(os.path.join(a.out, 'live_status.json'), 'w'), indent=1)
    print(json.dumps({'races': len(races), 'contested': len(contested), 'rows': len(rows), 'phase': phase, 'final': n_final, 'counting': n_count,
                      'precincts': prec, 'problems': len(problems)}))
    for p in problems:
        print('problem:', p, file=sys.stderr)


if __name__ == '__main__':
    main()
