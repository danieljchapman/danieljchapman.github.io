#!/usr/bin/env python3
"""Builds ia/tools/candidates_2026.csv, the Nov. 3, 2026 Iowa general-election ballot for the races the page shows.

Source: CivicAPI (civicapi.org) race records for Iowa on 2026-11-03 (one search per office name). Every one of the 100 House,
25 Senate (odd-numbered districts) and 4 U.S. House races and the seven statewide races is listed. Write-in placeholders and the
party-total records ("Iowa State House" / "Iowa State Senate" without a district) are skipped.

Usage: python3 build_candidates_2026.py [OUT]
"""
import csv, json, os, re, subprocess, sys, time

API = 'https://civicapi.org/api/v2'
PARTY = {'republican': 'R', 'democratic': 'D', 'libertarian': 'L', 'green': 'G', 'independent': 'I', 'nominated by petition': 'I', 'no party': 'I'}
STATEWIDE = {'Iowa Governor': 'Governor', 'Iowa US Senate': 'Senate', 'Iowa Secretary of State': 'Secretary of State',
             'Iowa Attorney General': 'Attorney General', 'Iowa State Treasurer': 'Treasurer', 'Iowa State Auditor': 'Auditor',
             'Iowa Secretary of Agriculture': 'Secretary of Agriculture'}
# CivicAPI returns at most 1,000 races per search and Iowa lists more than that (township and county offices), so the page's races are
# found with one search per office name
QUERIES = ['Iowa State House', 'Iowa State Senate', 'Iowa US', 'Iowa Governor', 'Iowa Secretary', 'Iowa Attorney General', 'Iowa State Auditor',
           'Iowa State Treasurer']
DISTRICT = [(r'^Iowa US House (\d+)$', 'ushouse', 'U.S. House'), (r'^Iowa State Senate (\d+)$', 'senate', 'Senate'),
            (r'^Iowa State House (\d+)$', 'house', 'House')]


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
    races = [r for q in QUERIES for r in get('/race/search?country=US&province=IA&startDate=2026-11-03&endDate=2026-11-03&limit=1000&query='
                                                 + q.replace(' ', '%20'))['races']]
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
