#!/usr/bin/env python3
"""Builds mi/tools/candidates_2026.csv, the Nov. 3, 2026 Michigan general-election ballot for the races the page shows.

Source: CivicAPI (civicapi.org) race records for Michigan on 2026-11-03 (one search with limit=1000; paging with offset repeats
and skips races). Every one of the 110 House, 38 Senate and 13 U.S. House races and the four statewide races is listed. Write-in
placeholders and the party-total records ("Michigan State House" / "Michigan State Senate" without a district) are skipped.

Usage: python3 build_candidates_2026.py [OUT]
"""
import csv, json, os, re, subprocess, sys, time

API = 'https://civicapi.org/api/v2'
PARTY = {'republican': 'R', 'democratic': 'D', 'libertarian': 'L', 'green': 'G', 'u.s. taxpayers': 'T', 'no party affiliation': 'I',
         'independent': 'I', 'working class': 'O', 'natural law': 'O'}
STATEWIDE = {'Michigan Governor': 'Governor', 'Michigan US Senate': 'Senate', 'Michigan Secretary of State': 'Secretary of State',
             'Michigan Attorney General': 'Attorney General'}
DISTRICT = [(r'^Michigan US House (\d+)$', 'ushouse', 'U.S. House'), (r'^Michigan State Senate (\d+)$', 'senate', 'Senate'),
            (r'^Michigan State House (\d+)$', 'house', 'House')]


def get(path):
    for i in range(4):
        p = subprocess.run(['curl', '-sS', '-m', '120', API + path], capture_output=True, text=True)
        try:
            return json.loads(p.stdout)
        except ValueError:
            time.sleep(3 + 3 * i)
    raise RuntimeError(path)


def classify(name):
    if name in STATEWIDE: return 'statewide', STATEWIDE[name], ''
    for pat, level, office in DISTRICT:
        m = re.match(pat, name)
        if m: return level, office, int(m.group(1))
    return None


def main(out):
    races = get('/race/search?country=US&province=MI&startDate=2026-11-03&endDate=2026-11-03&limit=1000')['races']
    rows, seen = [], set()
    for r in races:
        c = classify(r['election_name'].strip())
        if not c or r['id'] in seen: continue
        seen.add(r['id'])
        for cand in r['candidates']:
            if 'write' in cand['name'].lower(): continue
            rows.append({'level': c[0], 'office': c[1], 'district': c[2], 'candidate': cand['name'], 'party': PARTY.get(cand['party'].lower(), 'O'),
                         'civicapi_race': r['id']})
    order = ['statewide', 'ushouse', 'senate', 'house']
    rows.sort(key=lambda r: (order.index(r['level']), r['office'], r['district'] or 0, {'R': 0, 'D': 1}.get(r['party'], 2), r['candidate']))
    with open(out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator='\n'); w.writeheader(); w.writerows(rows)
    n = {l: len({r['district'] for r in rows if r['level'] == l}) for l in order}
    print(len(rows), 'candidates', n)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'candidates_2026.csv'))
