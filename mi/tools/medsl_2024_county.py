#!/usr/bin/env python3
"""Sums the MIT Election Data + Science Lab's 2024 Michigan precinct returns (mi24.csv, from the Secretary of State's official
precinct results; github.com/MEDSL/2024-elections-official, individual_states/mi24.zip) to counties, for the offices the page shows.

Usage: python3 medsl_2024_county.py mi24.csv OUT.csv
"""
import csv, sys
from collections import defaultdict

OFFICES = {'US PRESIDENT', 'US SENATE', 'US HOUSE', 'STATE HOUSE'}
t = defaultdict(int)
for x in csv.DictReader(open(sys.argv[1])):
    if x['office'] in OFFICES:
        d = '' if x['district'] == 'STATEWIDE' else str(int(x['district']))
        t[(x['office'], d, x['county_fips'], x['candidate'], x['party_detailed'], x['writein'])] += int(x['votes'] or 0)
with open(sys.argv[2], 'w', newline='') as fh:
    w = csv.writer(fh, lineterminator='\n'); w.writerow(['office', 'district', 'county_fips', 'candidate', 'party', 'writein', 'votes'])
    for k in sorted(t):
        w.writerow([*k, t[k]])
print(len(t))
