#!/usr/bin/env python3
"""Builds the Kansas results files (2016-2024) from the county files written by extract_sources.py.

Usage: python3 build_history.py TOOLS_DIR OUT_DIR
Reads TOOLS_DIR/results/<year>_county.csv (level, office_or_district, county, candidate, party, votes; district contests have county
'ALL': the certified district totals) and checks every candidate against TOOLS_DIR/results/official_totals.json.
Writes ks_statewide_results_by_county.csv, ks_ushouse_results.csv, ks_house_results.csv, ks_senate_results.csv.
"""
import csv, json, os, re, sys
from collections import defaultdict

LABEL = {'ushouse': 'U.S. House', 'senate': 'Senate', 'house': 'House'}
ORDER = ['President', 'Senate', 'Governor', 'Secretary of State', 'Attorney General', 'Treasurer', 'Insurance Commissioner']


def plan(level, year):
    # the 2022 maps: U.S. House and Kansas House from 2022; the Kansas Senate, elected only in presidential years, from 2024
    new = year >= (2024 if level == 'senate' else 2022)
    return {'ushouse': 'c', 'house': 'h', 'senate': 's'}[level] + ('2022' if new else '2012')


def main(tools, out):
    fips = {v['name']: v['fips'] for v in json.load(open(os.path.join(tools, 'ks_county_fips.json'))).values()}
    checks = json.load(open(os.path.join(tools, 'results', 'official_totals.json')))
    sw, dist, problems = [], defaultdict(list), []
    for year in (2016, 2018, 2020, 2022, 2024):
        s, d = defaultdict(int), defaultdict(int)
        for r in csv.DictReader(open(os.path.join(tools, 'results', f'{year}_county.csv'))):
            v = int(r['votes'])
            if r['level'] == 'statewide': s[(r['office_or_district'], r['county'], r['candidate'], r['party'])] += v
            else: d[(r['level'], int(r['office_or_district']), r['candidate'], r['party'])] += v
        for (o, c, nm, p), v in s.items():
            sw.append({'race': f'{year} {o}', 'year': year, 'office': o, 'county_fips': fips[c], 'county': c, 'candidate': nm, 'party': p, 'votes': v})
        n = defaultdict(int)
        for (lvl, k, nm, p) in d:
            if p != 'W': n[(lvl, k)] += 1
        for (lvl, k, nm, p), v in d.items():
            dist[lvl].append({'year': year, 'race': f'{year} {LABEL[lvl]}', 'plan': plan(lvl, year), 'district': k, 'candidate': nm, 'party': p,
                              'votes': v, 'unopposed': int(n[(lvl, k)] == 1)})
        got = defaultdict(int)
        for (o, c, nm, p), v in s.items(): got[('statewide|' + o, nm)] += v
        for (lvl, k, nm, p), v in d.items(): got[(f'{lvl}|{k}', nm)] += v
        for key, cands in checks[str(year)].items():
            for nm, p, v in cands:
                n2 = re.split(r'\s*/\s*', nm)[0].strip() if key in ('statewide|President', 'statewide|Governor') else nm
                if got.get((key, n2)) != v: problems.append(f'{year} {key} {n2}: {got.get((key, n2))} vs {v}')
        for lvl in ('ushouse', 'house', 'senate'):
            seats = defaultdict(int)
            for k in sorted({k for (l, k, _, _) in d if l == lvl}):
                seats[max((v, p) for (l, kk, nm, p), v in d.items() if l == lvl and kk == k and p != 'W')[1]] += 1
            if seats: print(year, lvl, dict(seats))
        print(year, 'statewide counties', {o: len({c for (oo, c, _, _) in s if oo == o}) for o in {k[0] for k in s}})
    sw.sort(key=lambda r: (r['year'], ORDER.index(r['office']), r['county'], -r['votes']))
    write(os.path.join(out, 'ks_statewide_results_by_county.csv'), sw, ['race', 'year', 'office', 'county_fips', 'county', 'candidate', 'party', 'votes'])
    for lvl in ('ushouse', 'house', 'senate'):
        rows = sorted(dist[lvl], key=lambda r: (r['year'], r['district'], -r['votes']))
        write(os.path.join(out, f'ks_{lvl}_results.csv'), rows, ['year', 'race', 'plan', 'district', 'candidate', 'party', 'votes', 'unopposed'])
    for p in problems: print('problem:', p)
    return not problems


def write(path, rows, fields):
    with open(path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore', lineterminator='\n'); w.writeheader(); w.writerows(rows)
    print(path, len(rows))


if __name__ == '__main__':
    sys.exit(0 if main(sys.argv[1], sys.argv[2]) else 1)
