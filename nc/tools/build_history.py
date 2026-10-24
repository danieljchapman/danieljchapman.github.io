#!/usr/bin/env python3
"""Builds the North Carolina history files from NCSBE results_pct files (official, post-canvass).

Usage: python3 build_history.py RESULTS_DIR OUT_DIR
RESULTS_DIR holds results_pct_YYYYMMDD.txt for each general election (from
https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/YYYY_MM_DD/results_pct_YYYYMMDD.zip).
Writes:
  nc_statewide_results_by_county.csv  race,year,office,county_fips,county,candidate,party,votes
  nc_ushouse_results.csv              year,race,plan,district,candidate,party,votes,unopposed
  nc_house_results.csv, nc_senate_results.csv   same columns, NC House and NC Senate
Plans (checked against the results: each county's districts with votes match the districts the map puts there):
  NC House  h2011 (2016), h2018 = 2017 plan with the special master's changes the Supreme Court upheld in 2018,
            h2019 = HB 1020 remedial plan (2020), h2022 = SL 2022-4, h2023 = SL 2023-149 (2024, 2026)
  NC Senate s2011, s2018, s2019 (2019 remedial), s2022 = SL 2022-2, s2023 = SL 2023-146 (2024, 2026)
"""
import csv, json, os, re, sys
from collections import defaultdict

YEARS = {2016: '20161108', 2018: '20181106', 2020: '20201103', 2022: '20221108', 2024: '20241105'}
USHOUSE_PLAN = {2016: 'c2016', 2018: 'c2016', 2020: 'c2019', 2022: 'c2022', 2024: 'c2023', 2026: 'c2025'}
HOUSE_PLAN = {2016: 'h2011', 2018: 'h2018', 2020: 'h2019', 2022: 'h2022', 2024: 'h2023', 2026: 'h2023'}
SENATE_PLAN = {2016: 's2011', 2018: 's2018', 2020: 's2019', 2022: 's2022', 2024: 's2023', 2026: 's2023'}
# district contests: (level, contest-name pattern, race label, plans)
DISTRICT_CONTESTS = [('ushouse', r'^US HOUSE OF REPRESENTATIVES DISTRICT 0*(\d+)$', 'U.S. House', USHOUSE_PLAN),
                     ('house', r'^NC HOUSE OF REPRESENTATIVES DISTRICT 0*(\d+)$', 'House', HOUSE_PLAN),
                     ('senate', r'^NC STATE SENATE DISTRICT 0*(\d+)$', 'Senate', SENATE_PLAN)]


def district_of(name):
    for level, pat, label, plans in DISTRICT_CONTESTS:
        m = re.match(pat, name)
        if m:
            return level, int(m.group(1))
    return None, None
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


def party_of(choice, p, blank='O'):
    """One-letter party. Write-ins ('Write-In (Miscellaneous)' or a named 'Jane Doe (Write-In)') are W.
    A partisan candidate with no party on the ballot is unaffiliated: pass blank='I' for district races
    (statewide, a blank party mostly means a nonpartisan race, e.g. the 2016 Supreme Court)."""
    if re.match(r'^write-?in', choice, re.I) or re.search(r'\(write-?in\)\s*$', choice, re.I):
        return 'W'
    p = (p or '').strip().upper()
    return PARTY.get(p, 'O') if p else blank


def read(path):
    with open(path, encoding='latin-1', newline='') as fh:
        for r in csv.DictReader(fh, delimiter='\t'):
            yield r


def main(src, out):
    counties = set()
    sw = defaultdict(int)       # (year, office, county, candidate, party) -> votes
    dist = {lvl: defaultdict(int) for lvl, *_ in DISTRICT_CONTESTS}   # level -> (year, district, candidate, party) -> votes
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
            lvl, d = district_of(name)
            if lvl:
                dist[lvl][(year, d, ch, party_of(ch, r['Choice Party'], blank='I'))] += v
    assert len(counties) == 100, len(counties)
    fips = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nc_county_fips.json')))  # {COUNTY NAME: fips}
    assert counties <= set(fips), counties - set(fips)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'nc_statewide_results_by_county.csv'), 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(['race', 'year', 'office', 'county_fips', 'county', 'candidate', 'party', 'votes'])
        for (y, off, c, ch, p), v in sorted(sw.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], -kv[1])):
            w.writerow([f'{y} {off}', y, off, fips[c], county_title(c), ch, p, v])
    files = {'ushouse': 'nc_ushouse_results.csv', 'house': 'nc_house_results.csv', 'senate': 'nc_senate_results.csv'}
    for lvl, pat, label, plans in DISTRICT_CONTESTS:
        rows = dist[lvl]
        n_cands = defaultdict(int)
        for (y, d, ch, p) in rows:
            if p != 'W':
                n_cands[(y, d)] += 1
        with open(os.path.join(out, files[lvl]), 'w', newline='') as fh:
            w = csv.writer(fh); w.writerow(['year', 'race', 'plan', 'district', 'candidate', 'party', 'votes', 'unopposed'])
            for (y, d, ch, p), v in sorted(rows.items(), key=lambda kv: (kv[0][0], kv[0][1], -kv[1])):
                w.writerow([y, f'{y} {label}', plans[y], d, ch, p, v, int(n_cands[(y, d)] == 1)])
    print('statewide rows', len(sw), {k: len(v) for k, v in dist.items()})


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
