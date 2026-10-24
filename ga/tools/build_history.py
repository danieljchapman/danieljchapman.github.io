#!/usr/bin/env python3
"""Builds the Georgia history files from the Secretary of State's official results exports.

Usage: python3 build_history.py EXPORT_DIR OUT_DIR
EXPORT_DIR holds export_<slug>.json.gz for each election, downloaded from the state's results site:
  https://results.sos.ga.gov/results/public/api/elections/Georgia/<slug>/data   (election summary; jurisdiction.mediaExportPath)
  https://results.sos.ga.gov/cdn/results/Georgia/export-<slug>.json            (every contest, statewide and by county)
Writes:
  ga_statewide_results_by_county.csv  race,year,office,county_fips,county,candidate,party,votes
  ga_ushouse_results.csv              year,race,plan,district,candidate,party,votes,unopposed
  ga_house_results.csv, ga_senate_results.csv   same columns, Georgia House and Senate
Scope: every statewide race on the November general-election ballot 2016-2024 plus the November 2025 PSC elections,
the general-election runoffs (Dec 2018, Jan 2021, Dec 2022), and the contested nonpartisan Supreme Court and Court of
Appeals elections (held with the May/June primary). 2020 President uses the state's recount, which is the certified count.
2026 November results come from the election-night importer (ga_live.py), not from this script.
"""
import csv, gzip, json, os, re, sys
from collections import defaultdict

# slug -> (election date, kind): general, runoff, judicial (nonpartisan judicial contests only), recount (President only)
ELECTIONS = {
    '2016NovGen': ('2016-11-08', 'general'), '2016MayGenPri': ('2016-05-24', 'judicial'),
    '2018NovGen': ('2018-11-06', 'general'), '2018DecGenRun': ('2018-12-04', 'runoff'), '2018GenPri': ('2018-05-22', 'judicial'),
    '2020NovGen': ('2020-11-03', 'general'), '2020NovGenRec': ('2020-11-03', 'recount'), '2020AugPPP': ('2020-06-09', 'judicial'),
    '2021JanFedRun': ('2021-01-05', 'runoff'),
    '2022NovGen': ('2022-11-08', 'general'), '2022DecGenRun': ('2022-12-06', 'runoff'), '2022MayGenPri': ('2022-05-24', 'judicial'),
    '2024NovGen': ('2024-11-05', 'general'), '2024MayGenPri': ('2024-05-21', 'judicial'),
    'MunicipalGeneralSpecialElectionPSC11042025': ('2025-11-04', 'general'),
    'GeneralPrimary51926': ('2026-05-19', 'judicial'),
}
USHOUSE_PLAN = {2016: 'c2012', 2018: 'c2012', 2020: 'c2012', 2022: 'c2021', 2024: 'c2023', 2026: 'c2023'}
HOUSE_PLAN = {2016: 'h2012', 2018: 'h2012', 2020: 'h2012', 2022: 'h2021', 2024: 'h2023', 2026: 'h2023'}
SENATE_PLAN = {2016: 's2012', 2018: 's2012', 2020: 's2012', 2022: 's2021', 2024: 's2023', 2026: 's2023'}
DISTRICT_CONTESTS = [
    ('ushouse', r'^(?:US House of Representatives|U\.?S\.? House|U\.?S\.? Representative)(?: -|,)? (?:District|Dist) 0*(\d+)\b', 'U.S. House', USHOUSE_PLAN),
    ('house', r'^State (?:House of Representatives|House|Representative)(?: -|,)? (?:District|Dist) 0*(\d+)\b', 'House', HOUSE_PLAN),
    ('senate', r'^State (?:Senate|Senator)(?: -|,)? (?:District|Dist) 0*(\d+)\b', 'Senate', SENATE_PLAN)]
PARTY = {'REP': 'R', 'DEM': 'D', 'LIB': 'L', 'GRN': 'G', 'GRE': 'G', 'IND': 'I'}
STATEWIDE = [(r'^President of the (United States|US)$', 'President'),
             (r'^(United States Senator|US Senate)(, Isakson| \(Perdue\))?$', 'Senate'),
             (r'^US Senate \(Loeffler\) - Special$', 'Senate (special)'),
             (r'^Governor$', 'Governor'), (r'^Lieutenant Governor$', 'Lt. Governor'), (r'^Secretary of State$', 'Secretary of State'),
             (r'^Attorney General$', 'Attorney General'), (r'^Commissioner of Agriculture$', 'Agriculture Commissioner'),
             (r'^Commissioner of Insurance$', 'Insurance Commissioner'), (r'^State School Superintendent$', 'School Superintendent'),
             (r'^Commissioner of Labor$', 'Labor Commissioner'),
             (r'^(?:Public Service Commission|PSC)(?:,| -)? District (\d)\b', 'PSC, District {0}')]
JUDICIAL = [(r'Supreme Court.*?[(,-]\s*([A-Za-z\' ]+?)(?:,? III)?\)?\s*$', 'Supreme Court'), (r'(?:Appeals|Court of Appeals).*?[(,-]\s*([A-Za-z\' ]+?)(?:,? III)?\)?\s*$', 'Court of Appeals')]


# Seats filled without a general-election contest on the state's results (winners chosen in special party primaries
# after the original nominee left the race); listed as unopposed with no vote total.
FILL = [('house', 2018, 14, 'Mitchell Scoggins', 'R'),   # special Republican primary Dec 18, 2018 (Christian Coomer withdrew)
        ('house', 2018, 28, 'Chris Erwin', 'R'),         # court-ordered Republican primary rerun Dec 4, 2018
        ('senate', 2020, 39, 'Sonya Halpern', 'D')]      # special Democratic primary Nov 3 and runoff Dec 1, 2020 (Nikema Williams withdrew)


def norm_contest(name):
    """Drops Spanish translations that some counties add ('Governor/Gobernador', '... District 3/Comisionado ... Distrito 3')."""
    return re.sub(r'\s+', ' ', re.sub(r'/[^()]*', ' ', name)).strip()


def statewide_office(name):
    n = norm_contest(name)
    for pat, off in STATEWIDE:
        m = re.match(pat, n, re.I)
        if m:
            return off.format(*m.groups())
    return None


def judicial_office(name):
    n = norm_contest(name)
    for pat, court in JUDICIAL:
        if (court == 'Supreme Court') == bool(re.search('Supreme', n)) and re.search(pat, n, re.I):
            seat = re.search(pat, n, re.I).group(1).strip()
            seat = 'LaGrua' if seat.lower() == 'lagura' else seat  # the 2022 ballot misspelled Justice LaGrua's name
            return f'{court}, {seat.title() if seat.isupper() else seat} seat'
    return None


def district_of(name):
    n = norm_contest(name)
    if re.search(r'primary|special|recall', n, re.I):
        return None, None
    for level, pat, label, plans in DISTRICT_CONTESTS:
        m = re.match(pat, n, re.I)
        if m:
            return level, int(m.group(1))
    return None, None


SMALL = {'Of', 'And', 'De', 'La', 'Van', 'Von', 'Der'}
def clean_name(raw):
    """'DONALD J. TRUMP (REP)' -> 'Donald J. Trump'; 'Jon Ossoff (I) (Dem)' -> 'Jon Ossoff'; '""Jen""' -> '"Jen"'."""
    n = re.sub(r'\s*\((?:I|REP|DEM|LIB|IND|GRN|NP|Rep|Dem|Lib|Ind|Grn)\)', '', raw)
    n = re.sub(r'""', '"', n)
    n = re.sub(r'\s+', ' ', n).strip().strip(',')
    if n.upper() == n:
        out = []
        for w in n.lower().split(' '):
            w = '-'.join(p[:1].upper() + p[1:] for p in w.split('-'))
            w = re.sub(r'^(Mc|O\')([a-z])', lambda m: m.group(1) + m.group(2).upper(), w)
            w = re.sub(r'^"([a-z])', lambda m: '"' + m.group(1).upper(), w)
            w = re.sub(r'^\(([a-z])', lambda m: '(' + m.group(1).upper(), w)
            if re.fullmatch(r'(ii|iii|iv)', w, re.I):
                w = w.upper()
            out.append(w)
        n = ' '.join(out)
    n = re.sub(r'\bJr$', 'Jr.', n)
    return n


def party_of(opt, blank='I'):
    p = (opt.get('politicalParty') or '').strip().upper()
    if not p:
        m = re.search(r'\((REP|DEM|LIB|IND|GRN)\)', opt['name'], re.I)
        p = m.group(1).upper() if m else ''
    if p == 'NP':
        return 'N'
    return PARTY.get(p, 'O') if p else blank


def load(src, slug):
    return json.loads(gzip.decompress(open(os.path.join(src, f'export_{slug}.json.gz'), 'rb').read()))


def main(src, out):
    fips = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ga_county_fips.json')))  # {Census county name: fips}
    by_upper = {k.upper().replace(' ', ''): (k, v) for k, v in fips.items()}
    sw = defaultdict(int)         # (year, office, county, candidate, party) -> votes
    sw_state = defaultdict(int)   # (year, office, candidate) -> statewide total as the state reports it
    dist = {lvl: defaultdict(int) for lvl, *_ in DISTRICT_CONTESTS}
    for slug, (date, kind) in ELECTIONS.items():
        year = int(date[:4])
        d = load(src, slug)
        offices = {}
        for b in d['results']['ballotItems']:
            name, opts = b['name'], b['ballotOptions']
            if kind == 'judicial':
                off = judicial_office(name)
                if off and len(opts) > 1:   # uncontested judicial seats are left out
                    offices[b['id']] = off
                continue
            off = statewide_office(name)
            if kind == 'recount' and off != 'President':
                continue
            if kind != 'recount' and slug == '2020NovGen' and off == 'President':
                continue   # the certified 2020 presidential count is the recount
            if off:
                offices[b['id']] = off + (' runoff' if kind == 'runoff' else '')
                for o in opts:
                    sw_state[(year, offices[b['id']], clean_name(o['name']))] += o['voteCount'] or 0
                continue
            lvl, dn = district_of(name)
            if lvl and kind in ('general', 'runoff') and year in USHOUSE_PLAN:
                if kind == 'runoff':
                    print('note: legislative runoff', slug, name)
                for o in opts:
                    dist[lvl][(year, dn, clean_name(o['name']), party_of(o))] += o['voteCount'] or 0
        wanted = set(offices.values())
        state_names = {b['name'].strip() for b in d['results']['ballotItems']}
        def local_office(name):
            # counties don't always use the state's contest id or name, so classify the county's own contest name
            if kind == 'judicial':
                off = judicial_office(name)
            else:
                off = statewide_office(name)
                if off and kind == 'runoff':
                    off += ' runoff'
                if kind == 'recount' and off != 'President':
                    off = None
            return off if off in wanted else None
        for loc in d['localResults']:
            cname = re.sub(r'\s+County$', '', loc['name']).strip()
            key = cname.upper().replace(' ', '')
            assert key in by_upper, cname
            cname, cf = by_upper[key]
            for b in loc['ballotItems']:
                off = local_office(b['name'])
                m = re.match(r'^(.*?)\s+-\s+(Rep|Dem)$', b['name'].strip())
                if not off and m and b['name'].strip() not in state_names:   # 'Commissioner of Insurance - Rep' on a general-election ballot
                    off = local_office(m.group(1))
                if not off:
                    continue
                for o in b['ballotOptions']:
                    p = 'N' if kind == 'judicial' else party_of(o, blank='O')
                    sw[(year, off, cname, clean_name(o['name']), p)] += o['voteCount'] or 0
    for lvl, y, dn, ch, p in FILL:
        assert not any(k[:2] == (y, dn) for k in dist[lvl]), (lvl, y, dn)
        dist[lvl][(y, dn, ch, p)] = None
    # check: county results add up to the state's totals for every candidate
    county_sum = defaultdict(int)
    for (y, off, c, ch, p), v in sw.items():
        county_sum[(y, off, ch)] += v
    bad = [(k, county_sum.get(k), v) for k, v in sw_state.items() if county_sum.get(k) != v]
    for k in bad:
        print('MISMATCH', k)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'ga_statewide_results_by_county.csv'), 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(['race', 'year', 'office', 'county_fips', 'county', 'candidate', 'party', 'votes'])
        for (y, off, c, ch, p), v in sorted(sw.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], -kv[1])):
            w.writerow([f'{y} {off}', y, off, fips[c], c, ch, p, v])
    files = {'ushouse': 'ga_ushouse_results.csv', 'house': 'ga_house_results.csv', 'senate': 'ga_senate_results.csv'}
    for lvl, pat, label, plans in DISTRICT_CONTESTS:
        rows = dist[lvl]
        n_cands = defaultdict(int)
        for (y, dn, ch, p) in rows:
            n_cands[(y, dn)] += 1
        with open(os.path.join(out, files[lvl]), 'w', newline='') as fh:
            w = csv.writer(fh); w.writerow(['year', 'race', 'plan', 'district', 'candidate', 'party', 'votes', 'unopposed'])
            for (y, dn, ch, p), v in sorted(rows.items(), key=lambda kv: (kv[0][0], kv[0][1], -(kv[1] or 0))):
                w.writerow([y, f'{y} {label}', plans[y], dn, ch, p, '' if v is None else v, int(n_cands[(y, dn)] == 1)])
    races = sorted({(y, off) for (y, off, *_) in sw})
    print('statewide races', len(races))
    for r in races:
        print('  ', *r)
    print({lvl: {y: len({k[1] for k in rows if k[0] == y}) for y in sorted({k[0] for k in rows})} for lvl, rows in dist.items()})


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
