#!/usr/bin/env python3
"""Builds the Michigan results files (2016-2024).

Usage: python3 build_history.py TOOLS_DIR OUT_DIR
Sources in TOOLS_DIR/results:
  <year>GEN_MI_CENR_BY_COUNTY.txt  2016-2022: the Secretary of State's official results by county (mielections.us/election/results/
                                   DATA/<year>GEN_MI_CENR_BY_COUNTY.xls, a tab-delimited text file despite the name). The state site
                                   doesn't answer automated downloads, so the files are the Internet Archive's copies saved after
                                   certification (2016: Jan 2024, 2018: Dec 2024, 2020: Jan 2024, 2022: Jan 2025).
  2024_medsl_county.csv            2024: MIT Election Data + Science Lab's precinct returns from the official results, summed to counties
                                   (medsl_2024_county.py). They have no write-ins, and names are upper-case without punctuation, so
                                   names are matched to the spelling in the state's files or the 2026 ballot (names_2026.txt) where possible.
Writes mi_statewide_results_by_county.csv, mi_ushouse_results.csv, mi_house_results.csv, mi_senate_results.csv.
Partial-term (special) races held with the general election are left out. Write-ins are combined as 'Write-ins'.
"""
import csv, json, os, re, sys
from collections import defaultdict

Q = dict(delimiter='\t', quoting=csv.QUOTE_NONE)
STATEWIDE = {'01': 'President', '02': 'Governor', '03': 'Secretary of State', '04': 'Attorney General', '05': 'Senate'}
DISTRICT = {'06': ('ushouse', 'U.S. House'), '07': ('senate', 'Senate'), '08': ('house', 'House')}
PARTY = {'REP': 'R', 'DEM': 'D', 'LIB': 'L', 'GRN': 'G', 'UST': 'T', 'NPA': 'I', 'WCP': 'O', 'NLP': 'O'}
PARTY24 = {'REPUBLICAN': 'R', 'DEMOCRAT': 'D', 'LIBERTARIAN': 'L', 'GREEN': 'G', 'US TAXPAYERS': 'T', 'NO PARTY AFFILIATION': 'I',
           'NATURAL LAW': 'O', 'WORKING CLASS': 'O'}
OFF24 = {'US PRESIDENT': 'President', 'US SENATE': 'Senate'}
DIST24 = {'US HOUSE': 'ushouse', 'STATE HOUSE': 'house'}
LABEL = {'ushouse': 'U.S. House', 'senate': 'Senate', 'house': 'House'}


def plan(level, year):
    if level == 'ushouse':
        return 'c2012' if year < 2022 else 'c2022'
    if level == 'house':
        return 'h2012' if year < 2022 else 'h2022' if year == 2022 else 'h2024'
    return 's2012' if year < 2022 else 's2022'


def name(f, m, l):
    keep = m and (len(m.rstrip('.')) <= 2 or m[0] in '\'"(')
    return ' '.join(p for p in (f.strip(), m.strip() if keep else '', l.strip()) if p)


key = lambda s: re.sub(r'[^a-z]', '', s.lower())


def titled(s):
    """'AMOS ONEAL' -> 'Amos Oneal', 'ADAM A STATHAKIS' -> 'Adam A. Stathakis' (fallback when no spelling is known)."""
    out = []
    for w in s.split():
        if len(w) == 1: out.append(w + '.')
        elif w in ('II', 'III', 'IV'): out.append(w)
        elif w == 'JR': out.append('Jr.')
        elif w.startswith('MC') and len(w) > 3: out.append('Mc' + w[2:].capitalize())
        else: out.append('-'.join(p.capitalize() for p in w.split('-')))
    return ' '.join(out)


def main(tools, out):
    cty = json.load(open(os.path.join(tools, 'mi_county_fips.json')))
    fips_name = {v['fips']: v['name'] for v in cty.values()}
    sw, dist = [], defaultdict(list)
    known = {}
    for l in open(os.path.join(tools, 'names_2026.txt')):
        if l.strip(): known[key(l)] = l.strip()
    for year in (2016, 2018, 2020, 2022):
        rows = list(csv.reader(open(os.path.join(tools, 'results', f'{year}GEN_MI_CENR_BY_COUNTY.txt'), encoding='cp1252'), **Q))
        h = rows[0]; R = [dict(zip(h, x)) for x in rows[1:] if len(x) >= len(h) - 3]
        s = defaultdict(int); d = defaultdict(int)
        for x in R:
            oc, desc = x['OfficeCode(Text)'], x['OfficeDescription']
            if 'Partial Term' in desc or (oc not in STATEWIDE and oc not in DISTRICT):
                continue
            w = x.get('WriteIn(W)/Uncommitted(Z)', '').strip() == 'W'
            p = 'W' if w else PARTY.get(x['PartyName'].strip(), 'O')
            nm = 'Write-ins' if w else name(x['CandidateFirstName'], x['CandidateMiddleName'], x['CandidateLastName'])
            if not w: known.setdefault(key(nm), nm)
            v = int(x['CandidateVotes'] or 0)
            c = cty[str(int(x['CountyCode']))]
            if oc in STATEWIDE:
                s[(STATEWIDE[oc], c['fips'], nm, p)] += v
            else:
                d[(DISTRICT[oc][0], int(x['DistrictCode(Text)']) // 100, nm, p)] += v
        add(year, s, d, sw, dist, fips_name)
    s = defaultdict(int); d = defaultdict(int)
    for x in csv.DictReader(open(os.path.join(tools, 'results', '2024_medsl_county.csv'))):
        p = PARTY24.get(x['party'], 'O')
        nm = known.get(key(x['candidate']), titled(x['candidate']))
        v = int(x['votes'])
        if x['office'] in OFF24:
            s[(OFF24[x['office']], x['county_fips'], nm, p)] += v
        else:
            d[(DIST24[x['office']], int(x['district']), nm, p)] += v
    add(2024, s, d, sw, dist, fips_name)
    order = ['President', 'Senate', 'Governor', 'Secretary of State', 'Attorney General']
    sw.sort(key=lambda r: (r['year'], order.index(r['office']), r['county'], -r['votes']))
    write(os.path.join(out, 'mi_statewide_results_by_county.csv'), sw, ['race', 'year', 'office', 'county_fips', 'county', 'candidate', 'party', 'votes'])
    for lvl in ('ushouse', 'house', 'senate'):
        rows = sorted(dist[lvl], key=lambda r: (r['year'], r['district'], -r['votes']))
        write(os.path.join(out, f'mi_{lvl}_results.csv'), rows, ['year', 'race', 'plan', 'district', 'candidate', 'party', 'votes', 'unopposed'])


def add(year, s, d, sw, dist, fips_name):
    for (office, f, nm, p), v in s.items():
        sw.append({'race': f'{year} {office}', 'year': year, 'office': office, 'county_fips': f, 'county': fips_name[f], 'candidate': nm, 'party': p, 'votes': v})
    tot = defaultdict(int)
    for (lvl, n, nm, p), v in d.items():
        tot[(lvl, n, nm, p)] += v
    cands = defaultdict(int)
    for (lvl, n, nm, p) in tot:
        if p != 'W': cands[(lvl, n)] += 1
    for (lvl, n, nm, p), v in tot.items():
        dist[lvl].append({'year': year, 'race': f'{year} {LABEL[lvl]}', 'plan': plan(lvl, year), 'district': n, 'candidate': nm, 'party': p,
                          'votes': v, 'unopposed': int(cands[(lvl, n)] == 1)})


def write(path, rows, fields):
    with open(path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    print(path, len(rows))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
