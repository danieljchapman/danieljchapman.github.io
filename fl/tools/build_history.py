#!/usr/bin/env python3
"""Builds the Florida results files (2016-2024) from the Division of Elections' official results extracts.

Usage: python3 build_history.py TOOLS_DIR OUT_DIR
Sources in TOOLS_DIR:
  results/<yyyymmdd>_general.txt   Florida Division of Elections "Election Results Data Extract" (official results), one file per
                                   general election: every race by county, tab-delimited (results.elections.myflorida.com,
                                   downloadresults.asp -> ResultsExtract.Asp with OfficialResults=Y)
  unopposed.csv                    winners elected without opposition, who are not on the general-election ballot and so are missing
                                   from the results file (from the Division's candidate list, status "Elected"; 2016 HD 33:
                                   Don Hahnfeldt, elected unopposed, listed as "Deceased" after his death in Dec. 2017)
  fl_county_fips.json              state county code -> FIPS and Census name
Writes fl_statewide_results_by_county.csv, fl_ushouse_results.csv, fl_house_results.csv, fl_senate_results.csv.
Write-in candidates are combined per county / district as 'Write-ins'.
Presidential and governor tickets are listed under the top of the ticket.
"""
import csv, json, os, sys
from collections import defaultdict

Q = dict(delimiter='\t', quoting=csv.QUOTE_NONE)
YEARS = [2016, 2018, 2020, 2022, 2024]
STATEWIDE = {'PRE': 'President', 'USS': 'Senate', 'GOV': 'Governor', 'ATG': 'Attorney General', 'CFO': 'Chief Financial Officer',
             'AGR': 'Agriculture Commissioner'}
DISTRICT = {'USR': ('ushouse', 'U.S. House'), 'STS': ('senate', 'Senate'), 'STR': ('house', 'House')}
PARTY = {'REP': 'R', 'DEM': 'D', 'LPF': 'L', 'GRE': 'G', 'CPF': 'C', 'NPA': 'I', 'IND': 'I', 'NOP': 'N', 'WRI': 'W'}  # others: O


def plan(level, year):
    if level == 'ushouse':
        return 'c2016' if year < 2022 else 'c2022'
    if level == 'house':
        return 'h2012' if year < 2022 else 'h2022'
    return 's2016' if year < 2022 else 's2022'


# Tickets (2020-2024 presidential, 2022 governor): the file gives only surnames, "Top / Running mate"
TICKET = {'Trump': 'Donald J. Trump', 'Biden': 'Joseph R. Biden', 'Jorgensen': 'Jo Jorgensen', 'Hawkins': 'Howie Hawkins',
          'Blankenship': 'Don Blankenship', 'De La Fuente': 'Roque "Rocky" De La Fuente', 'La Riva': 'Gloria La Riva',
          'Harris': 'Kamala D. Harris', 'Oliver': 'Chase Oliver', 'Stein': 'Jill Stein', 'De la Cruz': 'Claudia De la Cruz',
          'Sonski': 'Peter Sonski', 'Terry': 'Randall Terry', 'DeSantis': 'Ron DeSantis', 'Crist': 'Charlie Crist',
          'Gimenez': 'Carmen Jackie Gimenez', 'Roos': 'Hector Roos'}


def name(x):
    f, m, l = x['CanNameFirst'].strip(), x['CanNameMiddle'].strip(), x['CanNameLast'].strip()
    if m == '/':
        return TICKET.get(f, f)
    # keep middle initials and nicknames, drop full middle names
    keep = m and (len(m.rstrip('.')) <= 2 or m[0] in '\'"(')
    return ' '.join(p for p in (f, m if keep else '', l) if p)


def main(tools, out):
    cty = json.load(open(os.path.join(tools, 'fl_county_fips.json')))
    sw, dist = [], defaultdict(list)
    unopp = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(tools, 'unopposed.csv'))):
        unopp[(int(r['year']), r['level'])].append(r)
    for year in YEARS:
        fn = [f for f in os.listdir(os.path.join(tools, 'results')) if f.startswith(str(year))][0]
        rows = list(csv.DictReader(open(os.path.join(tools, 'results', fn), encoding='cp1252'), **Q))
        s = defaultdict(int); d = defaultdict(int)
        for x in rows:
            rc = x['RaceCode']
            p = PARTY.get(x['PartyCode'], 'O')
            nm = 'Write-ins' if p == 'W' else name(x)
            v = int(x['CanVotes'])
            if rc in STATEWIDE:
                s[(STATEWIDE[rc], x['CountyCode'], nm, p)] += v
            elif rc in DISTRICT:
                d[(DISTRICT[rc][0], int(x['Juris1num']), nm, p)] += v
        for (office, cc, nm, p), v in s.items():
            sw.append({'race': f'{year} {office}', 'year': year, 'office': office, 'county_fips': cty[cc]['fips'], 'county': cty[cc]['name'],
                       'candidate': nm, 'party': p, 'votes': v})
        have = set()
        for (lvl, n, nm, p), v in d.items():
            have.add((lvl, n))
            dist[lvl].append({'year': year, 'race': f'{year} {dict(DISTRICT.values())[lvl]}', 'plan': plan(lvl, year), 'district': n,
                              'candidate': nm, 'party': p, 'votes': v, 'unopposed': 0})
        # a race with one ballot candidate (plus write-ins) is shown as unopposed
        cands = defaultdict(list)
        for r in dist_rows(dist, year):
            if r['party'] != 'W':
                cands[(r['level'], r['district'])].append(r)
        for k, v in cands.items():
            if len(v) == 1:
                v[0]['unopposed'] = 1
        for lvl in ('ushouse', 'senate', 'house'):
            for r in unopp[(year, lvl)]:
                n = int(r['district'])
                assert (lvl, n) not in have, (year, lvl, n)
                dist[lvl].append({'year': year, 'race': f'{year} {dict(DISTRICT.values())[lvl]}', 'plan': plan(lvl, year), 'district': n,
                                  'candidate': r['candidate'], 'party': r['party'], 'votes': '', 'unopposed': 1})
    sw.sort(key=lambda r: (r['year'], list(STATEWIDE.values()).index(r['office']), r['county'], -r['votes']))
    write(os.path.join(out, 'fl_statewide_results_by_county.csv'), sw, ['race', 'year', 'office', 'county_fips', 'county', 'candidate', 'party', 'votes'])
    for lvl, f in (('ushouse', 'fl_ushouse_results.csv'), ('house', 'fl_house_results.csv'), ('senate', 'fl_senate_results.csv')):
        rows = sorted(dist[lvl], key=lambda r: (r['year'], r['district'], -(r['votes'] or 0)))
        for r in rows:
            r.pop('level', None)
        write(os.path.join(out, f), rows, ['year', 'race', 'plan', 'district', 'candidate', 'party', 'votes', 'unopposed'])


def dist_rows(dist, year):
    for lvl, rows in dist.items():
        for r in rows:
            if r['year'] == year:
                r['level'] = lvl
                yield r


def write(path, rows, fields):
    with open(path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    print(path, len(rows))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
