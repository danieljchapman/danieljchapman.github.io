#!/usr/bin/env python3
"""Turns the Iowa Secretary of State's results files (2014-2024) into one county-level file per year for build_history.py.

Usage: python3 extract_sources.py SRC_DIR OUT_DIR
Sources in SRC_DIR (the state's old results pages were taken down; 2016-2022 files are the Internet Archive's copies):
  results__xls__2016__general__statewide.xlsx       2016: every contest by precinct, with party (sos.iowa.gov/elections/results/xls/2016/general/)
  pdf__precinctresults__<year>general__<county>.xls(x)  2018, 2020, 2022: each county's precinct results export (Clarity/SOE)
  canv<year>.txt                                    the official canvass summaries (pdftotext -layout of
                                                    sos.iowa.gov/elections/pdf/<year>/general/canvsummary.pdf): every contest except
                                                    governor by county; used to fill counties whose export isn't archived
                                                    (2018 Clinton, Decatur; 2020 Scott; 2022 Black Hawk) and to check totals
  medsl_2018.csv, medsl_2022.csv                    MIT Election Data + Science Lab precinct returns from the official results (party
                                                    labels; governor in the counties without an archived export)
  detail_2024.xml                                   2024: the state's final Clarity export (electionresults.iowa.gov/IA/122322, reports/detailxml.zip)
  winners_2014.txt                                  pdftotext of the 2014 winner list (State Senate seats not up in 2016)
Writes OUT_DIR/<year>_county.csv: office, district, county, candidate, party, votes (write-ins combined as 'Write-ins', party W),
and senate_2014_winners.json.
"""
import csv, json, os, re, sys
import xml.etree.ElementTree as ET
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iowa_formats import header_names, parse_canvass, read_export  # noqa: E402

COUNTIES = [v['name'] for v in json.load(open(os.path.join(HERE, 'ia_county_fips.json'))).values()]
CKEY = {re.sub(r'[^a-z]', '', c.lower()): c for c in COUNTIES}
PARTY_WORD = {'republican': 'R', 'democratic': 'D', 'libertarian': 'L', 'iowa green': 'G', 'green': 'G', 'constitution': 'C', 'nominated by petition': 'I',
              'independent': 'I', 'rep': 'R', 'dem': 'D', 'lib': 'L', 'grn': 'G', 'con': 'C', 'nbp': 'I', 'ind': 'I', 'democrat': 'D'}


# candidates the canvass lists without a party code next to their column (petition candidates, or a header too wide to pair codes
# with names), checked against the canvass headers: name -> party
MANUAL = {'Donald J. Trump': 'R', 'Joseph R. Biden': 'D', 'Jo Jorgensen': 'L', 'Howie Hawkins': 'G', 'Don Blankenship': 'C',
          'Roque Rocky De La Fuente': 'O', 'Ricki Sue King': 'O', 'Brock Pierce': 'I', 'Kanye West': 'I', 'Joni Ernst': 'R',
          'Theresa Greenfield': 'D', 'Suzanne Herzog': 'I', 'Bennett Smith': 'I', 'Karen Koenig': 'D', 'Dave Lorenzen': 'R', 'Dave Stock': 'I',
          'Fred Hubbell': 'D', 'Jake Porter': 'L', 'Gary Siegwarth': 'O', 'Kim Reynolds': 'R', 'Deidre DeJear': 'D', 'Rick Stewart': 'L',
          'Alejandro Murguia-Ortiz': 'I', 'Bruce A. Gardner': 'I', 'Dennis McCullough': 'I', 'Luke Barnes': 'I', 'R.J. Miller': 'I'}


def office(title):
    t = re.sub(r'\s+', ' ', title.strip())
    if re.search(r'special|unexpired|vacancy', t, re.I): return None
    m = re.match(r'^(?:US Rep\.|United States Representative) Dist(?:\.|rict) 0*(\d+)$', t)
    if m: return ('ushouse', int(m.group(1)))
    m = re.match(r'^State Senator Dist(?:\.|rict) 0*(\d+)$', t)
    if m: return ('senate', int(m.group(1)))
    m = re.match(r'^State Rep(?:\.|resentative) Dist(?:\.|rict) 0*(\d+)$', t)
    if m: return ('house', int(m.group(1)))
    for pat, o in [(r'^President and Vice President$', 'President'), (r'^(US|United States) Senator$', 'Senate'), (r'^Governor( and |/)(Lt\.|Lieutenant) Governor$', 'Governor'),
                   (r'^Secretary of State$', 'Secretary of State'), (r'^Attorney General$', 'Attorney General'), (r'^Auditor of State$', 'Auditor'),
                   (r'^Treasurer of State$', 'Treasurer'), (r'^Secretary of Agriculture$', 'Secretary of Agriculture')]:
        if re.match(pat, t, re.I): return ('statewide', o)
    return None


def county_of(s):
    return CKEY.get(re.sub(r'[^a-z]', '', s.lower()))


def nkey(s):
    s = re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?', '', s.lower())
    return re.sub(r'[^a-z]', '', s)


def short(name, off):
    """Tickets are listed under the top of the ticket: 'Kim Reynolds and Adam Gregg' -> 'Kim Reynolds'."""
    name = re.sub(r'\s+', ' ', name).strip().rstrip(',')
    return re.split(r' and |/', name)[0].strip() if off in ('President', 'Governor') else name


def from_2016(src):
    import openpyxl
    ws = openpyxl.load_workbook(os.path.join(src, 'results__xls__2016__general__statewide.xlsx'), read_only=True)['Statewide']
    rows = ws.iter_rows(values_only=True); h = next(rows)
    cols = [(j, county_of(x.split('-')[0])) for j, x in enumerate(h) if j >= 3 and x and x.strip().endswith(' Total')]
    assert all(c for _, c in cols)
    out = defaultdict(int)
    for r in rows:
        o = office(r[0] or '')
        if not o: continue
        nm = (r[1] or '').strip()
        if not nm or re.match(r'^(Under|Over) ?Votes', nm, re.I): continue
        w = nm.lower().startswith('write')
        p = 'W' if w else PARTY_WORD.get(re.sub(r'\s*party$', '', (r[2] or '').strip().lower()), 'O' if (r[2] or '').strip() else 'I')
        for j, c in cols:
            if o[0] != 'statewide' and not str(r[j] or '').strip().strip('0'): continue
            out[(o, c, 'Write-ins' if w else short(nm, o[1] if o[0] == 'statewide' else ''), p)] += int(str(r[j] or 0).strip() or 0)
    return out


def from_exports(src, year, canv, party_of):
    """County exports, plus the canvass for counties without one. Returns {(office, county, name, party): votes}, problems."""
    files = {county_of(re.sub(r'\.xlsx?$', '', f.split('__')[-1])): os.path.join(src, f) for f in os.listdir(src)
             if f.startswith(f'pdf__precinctresults__{year}general__') and re.search(r'\.xlsx?$', f)}
    files.pop(None, None)
    data = defaultdict(dict)                                          # office -> county -> [(name, votes)]
    for c, f in files.items():
        for title, cands in read_export(f).items():
            o = office(title)
            if o: data[o][c] = cands
    probs = []
    for t, race in canv.items():
        o = office(t)
        if not o: continue
        if o not in data:
            # the contest lies wholly in counties without an archived export: names and parties from the canvass header
            hn = header_names(race)
            if not hn:
                probs.append(f'{year} {t}: no export and the canvass header could not be read'); continue
            k = race['ncol'] - 4
            for nm, code in hn:
                party_of.setdefault(nkey(nm), PARTY_WORD.get((code or 'ind').lower(), 'O'))
            data[o] = {c: [(nm, row[j]) for j, (nm, _) in enumerate(hn)] + [('Write-in', row[k])] for c, row in race['counties'].items() if c != 'TOTAL'}
            continue
        k = race['ncol'] - 4                                          # candidate columns (then write-in, under, over, total)
        names = {}
        for c, cands in data[o].items():
            row = race['counties'].get(c)
            if not row: continue
            for nm, v in cands:
                if nm.lower().startswith('write'): continue
                js = {j for j in range(k) if row[j] == v}
                names[nm] = names[nm] & js if nm in names else js
        col = {nm: next(iter(js)) for nm, js in names.items() if len(js) == 1}
        if len(set(col.values())) != len(col) or len(col) != k:
            probs.append(f'{year} {t}: candidate columns not matched ({names})'); continue
        for nm, j in col.items():
            if race['parties'] and len(race['parties']) == k:
                party_of.setdefault(nkey(nm), PARTY_WORD.get(race['parties'][j].lower(), 'O'))
        for c, row in race['counties'].items():
            if c in data[o] or c == 'TOTAL': continue
            data[o][c] = [(nm, row[j]) for nm, j in col.items()] + [('Write-in', row[k])]
    out = defaultdict(int)
    for o, bc in data.items():
        for c, cands in bc.items():
            for nm, v in cands:
                w = nm.lower().startswith('write')
                n2 = 'Write-ins' if w else short(nm, o[1] if o[0] == 'statewide' else '')
                out[(o, c, n2, 'W' if w else party_of.get(nkey(nm)) or party_of.get(nkey(n2)) or '?')] += int(v or 0)
    return out, probs, data


def medsl_parties(path, party_of):
    for r in csv.DictReader(open(path)):
        p = r.get('party_simplified') or r.get('party_detailed') or ''
        if r['candidate'] and p and r.get('writein', 'FALSE') != 'TRUE':
            party_of.setdefault(nkey(r['candidate']), {'REPUBLICAN': 'R', 'DEMOCRAT': 'D', 'LIBERTARIAN': 'L', 'GREEN': 'G', 'NONPARTISAN': 'I', 'OTHER': 'O'}.get(p, 'O'))


def medsl_governor(path, counties):
    """Governor votes by county from MEDSL for counties without an archived export: {county: [(name, votes)]}."""
    t = defaultdict(lambda: defaultdict(int))
    for r in csv.DictReader(open(path)):
        if r['office'] in ('GOVERNOR', 'GOVERNOR/LIEUTENANT GOVERNOR'):
            c = county_of(r['county_name'])
            if c in counties:
                nm = 'Write-in' if r.get('writein') == 'TRUE' or r['candidate'] in ('WRITEIN', 'WRITE-IN') else re.split(r'/| AND ', r['candidate'])[0].strip()
                t[c][nm] += int(float(r['votes'] or 0))
    return t


def from_2024(src, canv):
    root = ET.parse(os.path.join(src, 'detail_2024.xml')).getroot()
    out = defaultdict(int)
    for con in root.iter('Contest'):
        o = office(con.get('text'))
        if not o: continue
        cr = canv.get(con.get('text'))
        official = set((cr['total'] or [])[:cr['ncol'] - 3]) if cr and cr['ncol'] else None
        for ch in con.iter('Choice'):
            nm = ch.get('text'); w = nm.lower().startswith('write')
            # a choice the canvass doesn't count (2024 House 63: Kayla Koether withdrew; Winneshiek County's export still lists her votes)
            if official and int(ch.get('totalVotes')) not in official and int(ch.get('totalVotes')) > 0:
                print('skipped (not in the canvass):', con.get('text'), nm, ch.get('totalVotes')); continue
            p = 'W' if w else PARTY_WORD.get((ch.get('party') or '').lower(), 'O' if ch.get('party') else 'I')
            for vt in ch.iter('VoteType'):
                for cty in vt.iter('County'):
                    out[(o, county_of(cty.get('name')), 'Write-ins' if w else short(nm, o[1] if o[0] == 'statewide' else ''), p)] += int(cty.get('votes'))
    return out


def write(path, d):
    rows = sorted(((o[0], o[1], c, nm, p, v) for (o, c, nm, p), v in d.items()), key=lambda r: (r[0], str(r[1]), r[2], -r[5]))
    with open(path, 'w', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n'); w.writerow(['level', 'office_or_district', 'county', 'candidate', 'party', 'votes']); w.writerows(rows)
    print(path, len(rows))


def main(src, out):
    os.makedirs(out, exist_ok=True)
    party_of = {nkey(k): v for k, v in MANUAL.items()}
    medsl_parties(os.path.join(src, 'medsl_2018.csv'), party_of)
    medsl_parties(os.path.join(src, 'medsl_2022.csv'), party_of)
    write(os.path.join(out, '2016_county.csv'), from_2016(src))
    for year in (2018, 2020, 2022):
        canv = {r['title']: r for r in parse_canvass(os.path.join(src, f'canv{year}.txt'), COUNTIES)}
        d, probs, data = from_exports(src, year, canv, party_of)
        gov = ('statewide', 'Governor')
        if gov in data:
            missing = set(COUNTIES) - set(data[gov])
            if missing:
                for c, cands in medsl_governor(os.path.join(src, f'medsl_{year}.csv'), missing).items():
                    for nm, v in cands.items():
                        w = nm == 'Write-in'
                        n2 = 'Write-ins' if w else nm
                        # MEDSL names are upper case: use the spelling from the other counties
                        known = {nkey(k[2]): k[2] for k in d if k[0] == gov}
                        n2 = known.get(nkey(n2), n2)
                        d[(gov, c, n2, 'W' if w else party_of.get(nkey(nm), '?'))] += v
                missing -= set(medsl_governor(os.path.join(src, f'medsl_{year}.csv'), missing))
                if missing: probs.append(f'{year} governor: no results for {sorted(missing)}')
        for p in probs: print('problem:', p)
        unk = sorted({k[2] for k in d if k[3] == '?'})
        if unk: print(year, 'party unknown for', unk)
        write(os.path.join(out, f'{year}_county.csv'), d)
    write(os.path.join(out, '2024_county.csv'), from_2024(src, {r['title']: r for r in parse_canvass(os.path.join(src, 'canv2024.txt'), COUNTIES)}))
    # canvass totals for build_history.py's checks: {year: {'level|office or district': [candidate totals..., write-ins]}}
    checks = {}
    for year in (2016, 2018, 2020, 2022, 2024):
        cy = checks[str(year)] = {}
        for r in parse_canvass(os.path.join(src, f'canv{year}.txt'), COUNTIES):
            o = office(r['title'])
            if not o or not r['ncol']: continue
            k = r['ncol'] - 3
            t = r['total'] or [sum(v[j] for v in r['counties'].values()) for j in range(r['ncol'])]
            cy[f'{o[0]}|{o[1]}'] = t[:k]
    json.dump(checks, open(os.path.join(out, 'canvass_totals.json'), 'w'), separators=(',', ':'))
    # State Senate seats not up in 2016 (odd-numbered, elected 2014), from the 2014 winner list
    L = open(os.path.join(src, 'winners_2014.txt')).read().split('\n')
    hold = {}
    for i, l in enumerate(L):
        for m in re.finditer(r'State Senator Dist\. (\d+)', l):
            half = slice(0, 46) if m.start() < 46 else slice(46, None)
            for kk in (1, 2):
                pm = re.search(r'(Republican|Democratic|Libertarian|Independent|No Party|Nominated)', L[i + kk][half])
                if pm: hold[int(m.group(1))] = {'Republican': 'R', 'Democratic': 'D'}.get(pm.group(1), 'I'); break
    json.dump({str(k): v for k, v in sorted(hold.items())}, open(os.path.join(out, 'senate_2014_winners.json'), 'w'))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
