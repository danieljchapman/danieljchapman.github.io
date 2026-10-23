#!/usr/bin/env python3
"""Builds the North Carolina history files from NCSBE results_pct files (official, post-canvass).

Usage: python3 build_history.py RESULTS_DIR OUT_DIR
RESULTS_DIR holds results_pct_YYYYMMDD.txt for each general election (from
https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/YYYY_MM_DD/results_pct_YYYYMMDD.zip).
Writes:
  nc_statewide_results_by_county.csv  race,year,office,county_fips,county,candidate,party,votes
  nc_ushouse_results.csv              year,race,plan,district,candidate,party,votes,unopposed
"""
import csv, json, os, re, sys
from collections import defaultdict

YEARS = {2016: '20161108', 2018: '20181106', 2020: '20201103', 2022: '20221108', 2024: '20241105'}
USHOUSE_PLAN = {2016: 'c2016', 2018: 'c2016', 2020: 'c2019', 2022: 'c2022', 2024: 'c2023', 2026: 'c2025'}
PARTY = {'REP': 'R', 'DEM': 'D', 'LIB': 'L', 'GRE': 'G', 'CST': 'C', 'UNA': 'I', 'JFA': 'O', 'WTP': 'O'}
OFFICES = {'US PRESIDENT': 'President', 'US SENATE': 'Senate', 'NC GOVERNOR': 'Governor', 'NC LIEUTENANT GOVERNOR': 'Lt. Governor',
           'NC ATTORNEY GENERAL': 'Attorney General', 'NC SECRETARY OF STATE': 'Secretary of State', 'NC AUDITOR': 'Auditor', 'NC TREASURER': 'Treasurer',
           'NC SUPERINTENDENT OF PUBLIC INSTRUCTION': 'Superintendent', 'NC COMMISSIONER OF AGRICULTURE': 'Agriculture Commissioner',
           'NC COMMISSIONER OF INSURANCE': 'Insurance Commissioner', 'NC COMMISSIONER OF LABOR': 'Labor Commissioner'}
# 2016 contests were named after the incumbent instead of a seat number
SEAT_2016 = {'NC SUPREME COURT ASSOCIATE JUSTICE': 'Supreme Court, Seat 6'}


def office_of(name, year):
    if name in OFFICES:
        return OFFICES[name]
    if year == 2016 and name in SEAT_2016:
        return SEAT_2016[name]
    m = re.match(r'^NC SUPREME COURT (CHIEF JUSTICE|ASSOCIATE JUSTICE) SEAT 0?(\d+)$', name)
    if m:
        return 'Supreme Court, Chief Justice' if m.group(1) == 'CHIEF JUSTICE' else f'Supreme Court, Seat {m.group(2)}'
    m = re.match(r'^NC COURT OF APPEALS JUDGE SEAT 0?(\d+)$', name)
    if m:
        return f'Court of Appeals, Seat {m.group(1)}'
    m = re.match(r'^NC COURT OF APPEALS JUDGE \((\w+)\)$', name)
    if m:
        return f'Court of Appeals, {m.group(1).title()} seat'
    return None


def county_title(c):
    return ' '.join('McDowell' if w == 'MCDOWELL' else w.title() for w in c.split())


def party_of(choice, p):
    if re.match(r'^write-?in', choice, re.I):
        return 'W'
    return PARTY.get(p.strip().upper(), 'O')


def read(path):
    with open(path, encoding='latin-1', newline='') as fh:
        for r in csv.DictReader(fh, delimiter='\t'):
            yield r


def main(src, out):
    counties = set()
    sw = defaultdict(int)       # (year, office, county, candidate, party) -> votes
    us = defaultdict(int)       # (year, district, candidate, party) -> votes
    for year, d in YEARS.items():
        for r in read(os.path.join(src, f'results_pct_{d}.txt')):
            if r['Contest Type'] != 'S':
                continue
            name, cty = r['Contest Name'].strip(), r['County'].strip()
            counties.add(cty)
            ch = r['Choice'].strip()
            v = int(r['Total Votes'] or 0)
            off = office_of(name, year)
            if off:
                sw[(year, off, cty, ch, party_of(ch, r['Choice Party']))] += v
                continue
            m = re.match(r'^US HOUSE OF REPRESENTATIVES DISTRICT (\d+)$', name)
            if m:
                us[(year, int(m.group(1)), ch, party_of(ch, r['Choice Party']))] += v
    assert len(counties) == 100, len(counties)
    fips = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nc_county_fips.json')))  # {COUNTY NAME: fips}
    assert counties <= set(fips), counties - set(fips)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'nc_statewide_results_by_county.csv'), 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(['race', 'year', 'office', 'county_fips', 'county', 'candidate', 'party', 'votes'])
        for (y, off, c, ch, p), v in sorted(sw.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], -kv[1])):
            w.writerow([f'{y} {off}', y, off, fips[c], county_title(c), ch, p, v])
    n_cands = defaultdict(int)
    for (y, dist, ch, p) in us:
        if p != 'W':
            n_cands[(y, dist)] += 1
    with open(os.path.join(out, 'nc_ushouse_results.csv'), 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(['year', 'race', 'plan', 'district', 'candidate', 'party', 'votes', 'unopposed'])
        for (y, dist, ch, p), v in sorted(us.items(), key=lambda kv: (kv[0][0], kv[0][1], -kv[1])):
            w.writerow([y, f'{y} U.S. House', USHOUSE_PLAN[y], dist, ch, p, v, int(n_cands[(y, dist)] == 1)])
    print('statewide rows', len(sw), 'ushouse rows', len(us))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
