#!/usr/bin/env python3
"""Builds the Iowa results files (2016-2024) from the county files written by extract_sources.py.

Usage: python3 build_history.py TOOLS_DIR OUT_DIR
Reads TOOLS_DIR/results/<year>_county.csv (level, office_or_district, county, candidate, party, votes) and checks every contest
against the official canvass totals in TOOLS_DIR/results/canvass_totals.json (governor: certified totals listed below).
Writes ia_statewide_results_by_county.csv, ia_ushouse_results.csv, ia_house_results.csv, ia_senate_results.csv.
"""
import csv, json, os, sys
from collections import defaultdict

LABEL = {'ushouse': 'U.S. House', 'senate': 'Senate', 'house': 'House'}
ORDER = ['President', 'Senate', 'Governor', 'Secretary of State', 'Attorney General', 'Treasurer', 'Auditor', 'Secretary of Agriculture']
# governor isn't in the canvass summary (it has its own canvass): certified totals of the two major candidates
GOVERNOR = {2018: {'Kim Reynolds': 667275, 'Fred Hubbell': 630986}, 2022: {'Kim Reynolds': 709198, 'Deidre DeJear': 482950}}


def plan(level, year):
    return {'ushouse': 'c', 'house': 'h', 'senate': 's'}[level] + ('2012' if year < 2022 else '2022')


def main(tools, out):
    fips = {v['name']: v['fips'] for v in json.load(open(os.path.join(tools, 'ia_county_fips.json'))).values()}
    checks = json.load(open(os.path.join(tools, 'results', 'canvass_totals.json')))
    sw, dist, problems = [], defaultdict(list), []
    for year in (2016, 2018, 2020, 2022, 2024):
        s, d = defaultdict(int), defaultdict(int)
        for r in csv.DictReader(open(os.path.join(tools, 'results', f'{year}_county.csv'))):
            v = int(r['votes'])
            if r['level'] == 'statewide':
                s[(r['office_or_district'], r['county'], r['candidate'], r['party'])] += v
            else:
                d[(r['level'], int(r['office_or_district']), r['candidate'], r['party'])] += v
        for (o, c, nm, p), v in s.items():
            sw.append({'race': f'{year} {o}', 'year': year, 'office': o, 'county_fips': fips[c], 'county': c, 'candidate': nm, 'party': p, 'votes': v})
        n = defaultdict(int)
        for (lvl, k, nm, p) in d:
            if p != 'W': n[(lvl, k)] += 1
        for (lvl, k, nm, p), v in d.items():
            dist[lvl].append({'year': year, 'race': f'{year} {LABEL[lvl]}', 'plan': plan(lvl, year), 'district': k, 'candidate': nm, 'party': p,
                              'votes': v, 'unopposed': int(n[(lvl, k)] == 1)})
        # checks: candidate totals (sorted, write-ins included) equal the canvass for every contest
        tot = defaultdict(list)
        for (o, c, nm, p), v in s.items(): tot[('statewide', o)].append((nm, v))
        for (lvl, k, nm, p), v in d.items(): tot[(lvl, k)].append((nm, v))
        for key, cands in tot.items():
            agg = defaultdict(int)
            for nm, v in cands: agg[nm] += v
            want = checks.get(str(year), {}).get(f'{key[0]}|{key[1]}')
            if key == ('statewide', 'Governor'):
                bad = {k: (agg.get(k), v) for k, v in GOVERNOR[year].items() if agg.get(k) != v}
                if bad: problems.append(f'{year} Governor {bad}')
            elif want is None:
                problems.append(f'{year} {key}: no canvass total to check')
            elif sorted(agg.values(), reverse=True) != sorted(want, reverse=True):
                problems.append(f'{year} {key}: {sorted(agg.values(), reverse=True)} vs canvass {sorted(want, reverse=True)}')
        want_off = {2016: 2, 2018: 6, 2020: 2, 2022: 7, 2024: 1}[year]
        if len({o for (o, *_ ) in s}) != want_off: problems.append(f'{year}: {len({o for (o, *_ ) in s})} statewide offices, expected {want_off}')
        for lvl in ('ushouse', 'house', 'senate'):
            seats = defaultdict(int)
            for k in {k for (l, k, _, _) in d if l == lvl}:
                win = max(((v, p) for (l, kk, nm, p), v in d.items() if l == lvl and kk == k and p != 'W'))
                seats[win[1]] += 1
            print(year, lvl, dict(seats))
    sw.sort(key=lambda r: (r['year'], ORDER.index(r['office']), r['county'], -r['votes']))
    write(os.path.join(out, 'ia_statewide_results_by_county.csv'), sw, ['race', 'year', 'office', 'county_fips', 'county', 'candidate', 'party', 'votes'])
    for lvl in ('ushouse', 'house', 'senate'):
        rows = sorted(dist[lvl], key=lambda r: (r['year'], r['district'], -r['votes']))
        write(os.path.join(out, f'ia_{lvl}_results.csv'), rows, ['year', 'race', 'plan', 'district', 'candidate', 'party', 'votes', 'unopposed'])
    for p in problems: print('problem:', p)
    return not problems


def write(path, rows, fields):
    with open(path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore', lineterminator='\n'); w.writeheader(); w.writerows(rows)
    print(path, len(rows))


if __name__ == '__main__':
    sys.exit(0 if main(sys.argv[1], sys.argv[2]) else 1)
