#!/usr/bin/env python3
"""Turns the Kansas Secretary of State's official results files (2016-2024) into one county-level file per year for build_history.py.

Usage: python3 extract_sources.py SRC_DIR OUT_DIR
Sources in SRC_DIR (sos.ks.gov/elections/election-results.html; the site answers only a real browser, so the files were fetched with
Playwright on a GitHub runner):
  <yy>elec__*Precinct*.xlsx   one workbook per office: the first sheet lists every precinct of 101 counties (County, Precinct, Race,
                             [District], Candidate, Party, Votes); Johnson, Sedgwick, Shawnee and Wyandotte come as their own sheets in
                             each county's own layout (2018-2024) or not at all (2016)
  <yy>elec.txt               pdftotext -layout of the official vote totals (e.g. 2022-General-Official-Vote-Totals.pdf): every
                             contest's statewide total; names, parties and the checks come from here
  oe_<year>_<county>.csv     OpenElections precinct files for the four large counties, 2016-2020 (built from the counties' own reports)
  medsl_2018.csv             MIT Election Data + Science Lab 2018 precinct returns (2018: insurance commissioner in the four large counties,
                             and every statewide race in Wyandotte, whose sheet the state left out)
Statewide races in the four large counties: OpenElections (2016-2020), the counties' own sheets in the state's workbooks (2018 insurance
commissioner where available, 2022, 2024) and MEDSL (2018 Wyandotte); every candidate's statewide total is checked against the official
vote totals. District contests use the official vote totals directly (the page shows district totals).
Writes OUT_DIR/<year>_county.csv: level, office_or_district, county, candidate, party, votes; and official_totals.json for the checks.
Special elections for unexpired State Senate terms (2018 District 13, 2022 District 38) are left out.
"""
import csv, glob, json, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTIES = [v['name'] for v in json.load(open(os.path.join(HERE, 'ks_county_fips.json'))).values()]
CKEY = {re.sub(r'[^a-z]', '', c.lower()): c for c in COUNTIES}
BIG = ['Johnson', 'Sedgwick', 'Shawnee', 'Wyandotte']
PCODE = {'R': 'R', 'D': 'D', 'L': 'L', 'i': 'I', 'I': 'I', 'G': 'G', 'C': 'C'}


def county_of(s):
    return CKEY.get(re.sub(r'[^a-z]', '', str(s).lower()))


def office(title):
    t = re.sub(r'\s+', ' ', str(title)).strip()
    t = re.sub(r'^For (the )?', '', t)
    m = re.search(r'(?:United States|U\.?S\.?) (?:House of )?Rep(?:resentatives?|\.)?,? ?0*(\d+)', t, re.I) or re.search(r'^US Rep 0*(\d+)', t, re.I)
    if m: return ('ushouse', int(m.group(1)))
    m = re.search(r'(?:Kansas|State) Senat(?:e|or),? 0*(\d+)', t, re.I)
    if m: return ('senate', int(m.group(1)))
    m = re.search(r'(?:Kansas|State) (?:House of )?Representatives?,? 0*(\d+)', t, re.I)
    if m: return ('house', int(m.group(1)))
    for pat, o in [(r'^(Electors for |Presidential Electors for )?President', 'President'), (r'^(United States|US|U\.S\.) Senat', 'Senate'), (r'^Gov', 'Governor'),
                   (r'^Secretary of State', 'Secretary of State'), (r'^Attorney General', 'Attorney General'), (r'^State Treasurer', 'Treasurer'),
                   (r'^Commissioner of Insurance|^Insurance Commissioner', 'Insurance Commissioner')]:
        if re.match(pat, t, re.I): return ('statewide', o)
    return None


def oe_office(o, d):
    o = o.strip()
    if o in ('U.S. House',): return ('ushouse', int(d))
    if o in ('State Senate',): return ('senate', int(d))
    if o in ('State House', 'State Representative'): return ('house', int(d))
    return {'President': ('statewide', 'President'), 'U.S. Senate': ('statewide', 'Senate'), 'Governor': ('statewide', 'Governor'),
            'Secretary of State': ('statewide', 'Secretary of State'), 'Attorney General': ('statewide', 'Attorney General'),
            'State Treasurer': ('statewide', 'Treasurer'), 'Commissioner of Insurance': ('statewide', 'Insurance Commissioner'),
            'Insurance Commissioner': ('statewide', 'Insurance Commissioner')}.get(o)


def surname(name):
    """Last name of the candidate (or of the top of a ticket), for matching names across files."""
    s = str(name).strip()
    s = re.split(r'\s*/\s*|\s+and\s+', s)[0]
    s = re.sub(r'^(DEM|REP|LIB|IND|Dem|Rep|Lib|Ind|NON)\s+', '', s)
    s = re.sub(r'\s+\d+(st|nd|rd|th) District$', '', s)
    if ',' in s:                                                   # 'Kobach, Kris' -> 'Kris Kobach'
        a, b = s.split(',', 1); s = b + ' ' + a
    s = re.sub(r'\b(Jr|Sr|II|III|IV)\b\.?', ' ', s)
    w = re.findall(r"[A-Za-z][A-Za-z'\-]*", s)
    return re.sub(r'[^a-z]', '', w[-1].lower()) if w else ''


def parse_official(path):
    races, cur = {}, None
    for l in open(path).read().split('\n'):
        if not l.strip() or re.search(r'Kansas Secretary of State|General Election|Official Vote|^Race\b|^\s+Candidate\s+Votes', l): continue
        if not l.startswith(' '):
            cur = races.setdefault(l.strip(), []); continue
        m = re.match(r'^\s+(?:([RDLiIGC])-)?(.*?)\s{2,}([\d,]*)\s+[\d.]+\s*%\s*$', l)
        if m and cur is not None:
            cur.append((PCODE.get(m.group(1)) if m.group(1) else None, m.group(2).strip(), int(m.group(3).replace(',', '') or 0)))
    return races


def main_sheet(path):
    """{(office, county): {raw name: votes}} from the first sheet."""
    import openpyxl
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True); h = [str(x).strip() if x else '' for x in next(rows)]
    out = defaultdict(lambda: defaultdict(int))
    for r in rows:
        d = dict(zip(h, r))
        race = str(d.get('Race') or '') + (' ' + str(d['District']) if d.get('District') not in (None, '') else '')
        o = office(race); c = county_of(d.get('County'))
        if not o or not c or d.get('Candidate') is None: continue
        if 'write' in str(d.get('Party', '')).lower(): nm = 'Write-in:' + str(d['Candidate']).strip()
        else: nm = str(d['Candidate']).strip()
        out[(o, c)][nm] += int(float(d.get('Votes') or 0))
    return out


def wide_sheet(rows, county, default=None):
    """A large county's own sheet, in whatever layout the county used -> {(office, county): {raw name: votes}}.
    Handles: blocks of columns per contest (title row(s), an optional party-code row, a candidate row, precinct rows, a totals row),
    several such blocks stacked down the sheet (Wyandotte 2020), a 'Overall Results' summary (Sedgwick 2018: Candidate, Party, Votes),
    and 'Votes by Precinct' lists with the district in the candidate name (Sedgwick 2018 House)."""
    num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) or (isinstance(x, str) and re.fullmatch(r'\s*\d[\d,]*\s*', x) is not None)
    val = lambda x: int(float(str(x).replace(',', ''))) if num(x) else 0
    txt = lambda x: isinstance(x, str) and x.strip() != ''
    out = defaultdict(lambda: defaultdict(int))
    rows = [list(r) for r in rows]
    if not rows: return out
    if rows and any(txt(x) and x.strip() == 'Overall Results' for r in rows[:3] for x in r[:1]):
        i = next(i for i, r in enumerate(rows) if r[0] == 'Candidate') + 1
        while i < len(rows) and rows[i][0] not in ('Votes by Precinct', None):
            nm = str(rows[i][0]); m = re.search(r'^(.*?)\s+(\d+)(st|nd|rd|th) District$', nm)
            o = (default[0], int(m.group(2))) if m and default and default[0] != 'statewide' else default
            if m: nm = m.group(1)
            out[(o, county)]['Write-in:' if 'WRITE' in nm.upper() else nm] += val(rows[i][2]); i += 1
        return out
    if rows and rows[0] and rows[0][0] == 'Votes by Precinct':
        for r in rows[2:]:
            if len(r) > 2 and txt(r[1]):
                m = re.search(r'^(.*?)\s+(\d+)(st|nd|rd|th) District$', r[1])
                if m: out[((default[0] if default else 'house', int(m.group(2))), county)]['Write-in:' if 'WRITE' in m.group(1) else m.group(1)] += val(r[2])
        return out
    width = max(len(r) for r in rows)
    for r in rows: r.extend([None] * (width - len(r)))
    i = 0
    while i < len(rows):
        # a block starts at a row that has a contest title in it
        if not any(txt(x) and office(x) for x in rows[i][1:]):
            i += 1; continue
        h0 = i
        j = i
        while j < len(rows) and not (sum(num(x) for x in rows[j][1:]) >= 1 and not any(txt(x) and office(x) for x in rows[j][1:])):
            j += 1
        if j >= len(rows): break
        title, last = [None] * width, None
        for c in range(width):
            for k in range(h0, j):
                if txt(rows[k][c]) and office(rows[k][c]): last = rows[k][c]; break
            title[c] = last
        cand = [None] * width
        for c in range(width):
            for k in range(j - 1, h0 - 1, -1):
                x = rows[k][c]
                if txt(x) and not office(x) and not re.fullmatch(r'\s*(NON|REP|DEM|LIB|IND|-|VOTE FOR \d+)\s*', x, re.I):
                    cand[c] = x.strip(); break
        e = j
        while e < len(rows) and not any(txt(x) and 'TOTAL' in x.upper() for x in rows[e][:4]) and not any(txt(x) and office(x) for x in rows[e][1:]):
            e += 1
        has_tot = e < len(rows) and any(txt(x) and 'TOTAL' in x.upper() for x in rows[e][:4])
        for c in range(1, width):
            nm, t = cand[c], title[c]
            if not nm or not t or re.search(r'over|under|total|vote for|precinct', nm, re.I): continue
            o = office(t)
            v = val(rows[e][c]) if has_tot else sum(val(r[c]) for r in rows[j:e])
            out[(o, county)]['Write-in:' if 'write' in nm.lower() else nm] += v
        i = e + 1
    return out


def file_office(f):
    n = os.path.basename(f).replace('-', '_')
    for pat, o in [(r'President', ('statewide', 'President')), (r'US_Senate', ('statewide', 'Senate')), (r'US_House|United_States_House', ('ushouse', None)),
                   (r'Governor', ('statewide', 'Governor')), (r'Secretary_of_State', ('statewide', 'Secretary of State')),
                   (r'Attorney_General', ('statewide', 'Attorney General')), (r'Treasurer', ('statewide', 'Treasurer')),
                   (r'Insurance', ('statewide', 'Insurance Commissioner')), (r'Kansas_Senate', ('senate', None)), (r'Kansas_House', ('house', None))]:
        if re.search(pat, n): return o
    return None


def oe_county(path):
    out = defaultdict(lambda: defaultdict(int))
    for r in csv.DictReader(open(path, encoding='utf-8', errors='replace')):
        o = oe_office(r['office'], r.get('district') or 0)
        if not o or not r['candidate']: continue
        try: v = int(float(r['votes'] or 0))
        except ValueError: continue
        nm = r['candidate'].strip()
        if re.search(r'over ?votes|under ?votes|total|ballots', nm, re.I) or re.search(r'total', r.get('precinct') or '', re.I): continue
        out[(o, county_of(r['county']))]['Write-in:' if 'write' in nm.lower() else nm] += v
    return out


MEDSL_OFF = {'GOVERNOR': 'Governor', 'SECRETARY OF STATE': 'Secretary of State', 'ATTORNEY GENERAL': 'Attorney General', 'STATE TREASURER': 'Treasurer',
             'COMMISSIONER OF INSURANCE': 'Insurance Commissioner'}


def medsl(path, offices, counties):
    out = defaultdict(lambda: defaultdict(int))
    for r in csv.DictReader(open(path)):
        if r['office'] in offices and county_of(r['county_name']) in counties:
            nm = 'Write-in:' if r.get('writein') == 'TRUE' else r['candidate']
            out[(('statewide', MEDSL_OFF[r['office']]), county_of(r['county_name']))][nm] += int(float(r['votes'] or 0))
    return out


def main(src, out):
    import openpyxl
    os.makedirs(out, exist_ok=True)
    checks = {}
    for year in (2016, 2018, 2020, 2022, 2024):
        yy = str(year)[2:]
        official = {office(t): c for t, c in parse_official(os.path.join(src, f'{yy}elec.txt')).items() if office(t)
                    and not (year in (2018, 2022) and office(t)[0] == 'senate')}
        data = defaultdict(lambda: defaultdict(int))                         # (office, county) -> raw name -> votes
        files = [f for f in sorted(glob.glob(os.path.join(src, f'{yy}elec__*.xlsx'))) if re.search(r'Senate|House|President|Governor|Secretary|Attorney|Treasurer|Insurance', f)
                 and 'Presidential-Results' not in f and 'District-Attorney' not in f]
        if year <= 2020:
            for c in BIG:
                for k, v in oe_county(os.path.join(src, f'oe_{year}_{c.lower()}.csv')).items():
                    if k[0][0] == 'statewide': data[k] = v
        for f in files:
            for k, v in main_sheet(f).items():
                data[k] = v
            if year >= 2018:
                wb = openpyxl.load_workbook(f, read_only=True)
                fo = file_office(f)
                for sn in wb.sheetnames[1:]:
                    c = county_of(sn)
                    if c not in BIG: continue
                    for k, v in wide_sheet(list(wb[sn].iter_rows(values_only=True)), c, fo).items():
                        if k[0] is None or (fo and k[0][0] != fo[0]) or (fo and fo[0] == 'statewide' and k[0] != fo): continue
                        if k not in data: data[k] = v
        if year == 2018:
            # insurance commissioner in the large counties isn't in OpenElections; Wyandotte's statewide races (the state has no sheet for it,
            # and OpenElections is a few votes off the canvass) come from MEDSL, which matches it
            for k, v in medsl(os.path.join(src, 'medsl_2018.csv'), {'COMMISSIONER OF INSURANCE'}, set(BIG)).items():
                if k not in data: data[k] = v
            # (attorney general stays with OpenElections, which matches the official total there; MEDSL is 85 votes off)
            for k, v in medsl(os.path.join(src, 'medsl_2018.csv'), set(MEDSL_OFF) - {'ATTORNEY GENERAL'}, {'Wyandotte'}).items():
                data[k] = v
        # match each county's names to the official list by last name; registered write-ins and unmatched names count as write-ins
        rows, probs = defaultdict(int), []
        for (o, c), names in data.items():
            if o not in official:
                continue
            offc = [(p, nm) for p, nm, _ in official[o] if p]
            by_sur = defaultdict(list)
            for p, nm in offc: by_sur[surname(nm)].append((p, nm))
            for raw, v in names.items():
                hit = by_sur.get(surname(raw)) if not raw.startswith('Write-in:') else None
                if not raw.startswith('Write-in:') and not (hit and len(hit) == 1):
                    # 'Laura Kelly Lynn Rogers' (ticket without a separator): the official candidate whose last name comes first
                    toks = [re.sub(r'[^a-z]', '', t.lower()) for t in re.split(r'[\s,/]+', raw)]
                    pos = sorted((toks.index(k), k) for k in by_sur if k in toks and len(by_sur[k]) == 1)
                    hit = by_sur[pos[0][1]] if pos else hit
                if hit and len(hit) == 1:
                    p, nm = hit[0]
                    nm = re.split(r'\s*/\s*', nm)[0].strip() if o[0] == 'statewide' and o[1] in ('President', 'Governor') else nm
                    rows[(o, c, nm, p)] += v
                else:
                    rows[(o, c, 'Write-ins', 'W')] += v
        # district contests: the certified totals themselves (the page shows district totals; county splits aren't needed)
        for o, cands in official.items():
            if o[0] == 'statewide': continue
            for k in [k for k in rows if k[0] == o]: del rows[k]
            for p, nm, v in cands:
                rows[(o, 'ALL', nm if p else 'Write-ins', p or 'W')] += v
        # checks: each named candidate's total equals the official total; every statewide race covers all 105 counties
        cy = checks[str(year)] = {}
        for o, cands in official.items():
            cy[f'{o[0]}|{o[1]}'] = [[nm, p, v] for p, nm, v in cands if p]
            got = defaultdict(int)
            for (oo, c, nm, p), v in rows.items():
                if oo == o and p != 'W': got[nm] += v
            for p, nm, v in cands:
                if not p: continue
                n2 = re.split(r'\s*/\s*', nm)[0].strip() if o[0] == 'statewide' and o[1] in ('President', 'Governor') else nm
                if got.get(n2, 0) != v: probs.append(f'{year} {o} {n2}: {got.get(n2, 0)} vs official {v}')
            if o[0] == 'statewide':
                cs = {c for (oo, c, _, _) in rows if oo == o}
                if len(cs) != 105: probs.append(f'{year} {o}: {len(cs)} counties, missing {sorted(set(COUNTIES) - cs)}')
        for p in probs[:40]: print('problem:', p)
        if len(probs) > 40: print('...', len(probs), 'problems')
        with open(os.path.join(out, f'{year}_county.csv'), 'w', newline='') as fh:
            w = csv.writer(fh, lineterminator='\n'); w.writerow(['level', 'office_or_district', 'county', 'candidate', 'party', 'votes'])
            w.writerows(sorted(((o[0], o[1], c, nm, p, v) for (o, c, nm, p), v in rows.items() if v or p != 'W'), key=lambda r: (r[0], str(r[1]), r[2], -r[5])))
        print(year, len(rows), 'rows,', len(probs), 'problems')
    json.dump(checks, open(os.path.join(out, 'official_totals.json'), 'w'), separators=(',', ':'))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
