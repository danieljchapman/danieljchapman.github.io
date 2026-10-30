#!/usr/bin/env python3
"""Builds az/tools/candidates_2026.csv, the Nov. 3, 2026 Arizona general-election ballot for the races the page shows.

Source: CivicAPI (civicapi.org) race records for Arizona on 2026-11-03, which list each race's general-election candidates.
Checked Oct 30, 2026 against the July 21, 2026 primary results (OpenElections county file): every Republican and Democratic
nominee matches except where a write-in or replacement nominee was named after the primary (U.S. House 3 Republican:
Jacob Parkman). Placeholder records (an "Arizona State House" / "Arizona State Senate" race without a district) and the
duplicate "Arizona Corporation Commissioner" record are skipped.

Usage: python3 build_candidates_2026.py [OUT]
"""
import csv, json, os, re, subprocess, sys, time

API = 'https://civicapi.org/api/v2'
PARTY = {'republican': 'R', 'democratic': 'D', 'libertarian': 'L', 'green': 'G', 'independent': 'I', 'no labels': 'NL', 'nonpartisan': 'I'}
STATEWIDE = {'Arizona Governor': 'Governor', 'Arizona Secretary of State': 'Secretary of State', 'Arizona Attorney General': 'Attorney General',
             'Arizona State Treasurer': 'Treasurer', 'Arizona Superintendent of Public Instruction': 'Superintendent of Public Instruction',
             'Arizona State Mine Inspector': 'Mine Inspector', 'Arizona Corporation Commission': 'Corporation Commission'}
DISTRICT = [(r'^Arizona US House (\d+)$', 'ushouse', 'U.S. House'), (r'^Arizona State Senate (\d+)$', 'senate', 'Senate'), (r'^Arizona State House (\d+)$', 'house', 'House')]


def get(path):
    for i in range(4):
        p = subprocess.run(['curl', '-sS', '-m', '60', API + path], capture_output=True, text=True)
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
    races = get('/race/search?country=US&province=AZ&startDate=2026-11-03&endDate=2026-11-03&limit=500')['races']
    rows = []
    for r in races:
        c = classify(r['election_name'].strip())
        if not c: continue
        d = get(f"/race/{r['id']}"); time.sleep(0.15)
        for cand in d['candidates']:
            rows.append({'level': c[0], 'office': c[1], 'district': c[2], 'candidate': cand['name'], 'party': PARTY.get(str(cand.get('party') or '').lower(), 'I'), 'civicapi_race': r['id']})
    rows.sort(key=lambda x: (['statewide', 'ushouse', 'senate', 'house'].index(x['level']), x['office'], x['district'] or 0, x['party'], x['candidate']))
    with open(out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(len(rows), 'candidates')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'candidates_2026.csv'))
