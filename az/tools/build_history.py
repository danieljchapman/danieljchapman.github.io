#!/usr/bin/env python3
"""Builds the Arizona history files (2016-2024) from the Secretary of State's official statewide canvasses.

Usage: python3 build_history.py CANVASS_DIR OUT_DIR
CANVASS_DIR holds r<year>.json (rows read from each canvass: tools/canvass_rows; see az-dashboard-notes.md), fixes.json
(numbers read by hand from the canvass images where the automatic reading didn't add up) and c2022recount.txt
(pdftotext -layout of the Dec. 29, 2022 recount results; it replaces the attorney general, superintendent and LD 13 House races).

Every candidate row must add up: its county numbers sum to the canvass's TOTAL column. Write-ins are combined per county
(party W); their county numbers may be off by a few votes where the scan is hard to read, but each race's write-in total is the
canvass's own. Writes az_statewide_results_by_county.csv, az_ushouse_results.csv, az_house_results.csv, az_senate_results.csv.
"""
import csv, json, os, re, sys
from collections import defaultdict

COUNTIES = ['Apache', 'Cochise', 'Coconino', 'Gila', 'Graham', 'Greenlee', 'La Paz', 'Maricopa', 'Mohave', 'Navajo', 'Pima', 'Pinal', 'Santa Cruz', 'Yavapai', 'Yuma']
FIPS = dict(zip(COUNTIES, ['04001', '04003', '04005', '04007', '04009', '04011', '04012', '04013', '04015', '04017', '04019', '04021', '04023', '04025', '04027']))
STATEWIDE = {'President of the United States': 'President', 'U.S. Senator': 'Senate', 'Governor': 'Governor', 'Secretary of State': 'Secretary of State',
             'Attorney General': 'Attorney General', 'State Treasurer': 'Treasurer', 'Superintendent of Public Instruction': 'Superintendent of Public Instruction',
             'State Mine Inspector': 'Mine Inspector', 'Corporation Commissioner': 'Corporation Commission'}
PARTY = {'REP': 'R', 'DEM': 'D', 'OEM': 'D', 'REF': 'R', 'LBT': 'L', 'LIB': 'L', 'GRN': 'G', 'IND': 'I', 'NL': 'NL', 'NLB': 'NL', 'NOL': 'NL'}


def num(s):
    if s is None: return None
    s = s.strip()
    if not s or set(s) <= set('-—_~=.,:;\'"| '): return 0
    d = re.sub(r'[^\d]', '', s)
    return int(d) if d else 0     # no digits at all: a dash or a speck on the scan


def nice(name):
    name = re.sub(r'\s+', ' ', name).strip(' ,')
    if name.upper() != name: return name
    out = []
    for w in name.lower().split(' '):
        w = '-'.join(p[:1].upper() + p[1:] for p in w.split('-'))
        w = re.sub(r"^(Mc|O'|\")([a-z])", lambda m: m.group(1) + m.group(2).upper(), w)
        if w.lower() in ('ii', 'iii', 'iv'): w = w.upper()
        out.append(w)
    return ' '.join(out)


def norm_race(r):
    r = re.sub(r'U\.?S\.?,?', 'U.S.', r)
    r = re.sub(r'\s*[-~—]?\s*District N[oa][.,]? ?(\d+)', r' - District No. \1', r)
    r = re.sub(r'State Senat\w*', 'State Senator', r)
    r = re.sub(r'State Representat\w*', 'State Representative', r)
    return r


def repair(cty, tot, raw):
    """Fix the scan-reading slips that the row's own total exposes (each repair must make the row add up)."""
    cty = [0 if v is None else v for v in cty]
    nums = [int(x.replace(',', '')) for x in re.findall(r'(?<![\d,])\d{1,3}(?:,\d{3})+(?![\d,])|(?<![\d,])\d{1,3}(?![\d,])', raw)]
    s = sum(cty)
    if tot is not None and s == tot and tot: return cty, tot
    # 0. the whole-line reading: 16 numbers that add up (statewide rows, every county filled)
    if len(nums) == 16 and sum(nums[:15]) == nums[15]: return nums[:15], nums[15]
    # 0b. fewer numbers (a district): they add up, and the cell reading found the same number of filled counties
    if len(nums) >= 2 and sum(nums[:-1]) == nums[-1]:
        nz = [i for i, v in enumerate(cty) if v]
        if len(nz) == len(nums) - 1:
            out = [0] * 15
            for i, v in zip(nz, nums[:-1]): out[i] = v
            return out, nums[-1]
        # noise digits from dashes may sit between; drop single digits and retry
    big = [v for v in nums if v > 9]
    if len(big) >= 2 and sum(big[:-1]) == big[-1]:
        nz = [i for i, v in enumerate(cty) if v > 9]
        if len(nz) == len(big) - 1:
            out = [0] * 15
            for i, v in zip(nz, big[:-1]): out[i] = v
            return out, big[-1]
    # 1. TOTAL cell missed: the last number on the line is the total
    if (not tot) and nums and nums[-1] == s and s: return cty, s
    if tot is None: return cty, tot
    # 2. a dash read as a single digit in an empty cell
    if s > tot:
        hit = [i for i, v in enumerate(cty) if 0 < v < 100 and v == s - tot]
        if len(hit) == 1 and max(cty) >= 1000: cty[hit[0]] = 0; return cty, tot
        small = [i for i, v in enumerate(cty) if 0 < v < 100]
        if small and max(cty) >= 1000 and s - sum(cty[i] for i in small) == tot:
            for i in small: cty[i] = 0
            return cty, tot
    # 3. one county carries the whole district and its cell lost a digit: the line shows the number twice (county and total)
    nz = [i for i, v in enumerate(cty) if v]
    if len(nz) == 1 and cty[nz[0]] != tot and (nums.count(tot) >= 2 or str(tot).endswith(str(cty[nz[0]]))): cty[nz[0]] = tot; return cty, tot
    return cty, tot


def candidates(rows, year, fixes):
    """(race header, party, name, write-in, [15 county numbers], total) for every candidate row in the canvass."""
    out = []
    # district headers come in order (1, 2, 3 ...); a misread number (11 read as 14) is put back in sequence
    last, prev_raw = {}, None
    for r in rows:
        m = re.match(r'^(.*) - District No\. (\d+)$', norm_race(r['race']))
        if m and r['race'] != prev_raw:
            want = last.get(m.group(1), 0) + 1
            n = int(m.group(2))
            last[m.group(1)] = n if n == want or n == 1 else want
            prev_raw = r['race']
        if m: r['_race'] = f'{m.group(1)} - District No. {last[m.group(1)]}'
    for r in rows:
        lab = r['label']
        i = lab.find('(')
        if 0 < i <= 7: lab = lab[i:]     # specks before "(REP)" on the scan
        m = re.match(r'^\((\w+)[)}\]]\s*(.*)$', lab)
        if not m: continue
        race = r.get('_race') or norm_race(r['race'])
        if not (race in STATEWIDE or re.match(r'(U\.S\. Representative in Congress|State Senator|State Representative) - District No\. \d+$', race)): continue
        if re.search(r'\bPage\s*\d', r.get('raw', '')) or re.search(r', Vice', m.group(2)): continue
        party, name = m.group(1).upper(), m.group(2)
        wi = bool(re.search(r'Write', name, re.I)) or not name.strip(' *,')   # 2016: write-in names sit on the line above
        name = re.sub(r'\s*[({]?Write.*$', '', name).replace('*', '').strip(' ,.')
        name = re.sub(r',\s*President$', '', name)
        key = f'{year}|{race}|{name}'
        key = key if key in fixes else f'{year}|*|{name}' if f'{year}|*|{name}' in fixes else key
        cells = fixes.get(key, r['cells'])
        vals = [num(c) for c in cells]
        cty, tot = vals[:15], vals[15]
        cty, tot = repair(cty, tot, r.get('raw', '')) if key not in fixes else (cty, tot)
        ok = tot is not None and None not in cty and sum(cty) == tot
        out.append({'race': race, 'party': party, 'name': nice(name.replace(':', ' ').replace('  ', ' ')), 'raw_name': name, 'writein': wi, 'county': cty, 'total': tot, 'ok': ok, 'key': key, 'fixed': key in fixes})
    return out


def recount_2022(path):
    """Statewide recount table (page 2): AG, superintendent, LD 13 House."""
    txt = open(path).read()
    page = txt[txt.index('2022 General Election Recount Results'):txt.index('* denotes winners')]
    out, race = [], None
    for line in page.splitlines():
        s = line.strip()
        if s in ('Attorney General', 'Superintendent of Public Instruction') or s.startswith('State Representative - District No.'):
            race = s; continue
        m = re.match(r'^(?:\((\w+)\)\s*)?(.+?)\*?\s+((?:[\d,]+\s+)*[\d,]+)$', s)
        if not race or not m: continue
        nums = [int(x.replace(',', '')) for x in m.group(3).split()]
        name = m.group(2).strip(' *')
        wi = name.startswith('Write-in')
        if race.startswith('State Representative'):
            cty = [0] * 15; cty[COUNTIES.index('Maricopa')] = nums[0]; tot = nums[-1]
        else:
            cty, tot = nums[:15], nums[15]
        assert sum(cty) == tot, (race, name)
        out.append({'race': race, 'party': m.group(1) or 'W', 'name': name, 'writein': wi, 'county': cty, 'total': tot, 'ok': True})
    return out


def main(src, out):
    fixes = json.load(open(os.path.join(src, 'fixes.json'))) if os.path.exists(os.path.join(src, 'fixes.json')) else {}
    sw, dist = [], defaultdict(list)
    report = []
    for year in (2016, 2018, 2020, 2022, 2024):
        rows = candidates(json.load(open(os.path.join(src, f'r{year}.json'))), year, fixes)
        if year == 2022:
            rc = recount_2022(os.path.join(src, 'c2022recount.txt'))
            redo = {r['race'] for r in rc}
            rows = [r for r in rows if r['race'] not in redo] + rc
        # write-in names that wrapped onto the next line lose their "(Write-In)" tag (2016, 2022 text): a minor candidate with
        # under 0.1% of a statewide race, or under 0.5% of a district race, is treated as a write-in
        rtot = defaultdict(int)
        for r in rows: rtot[r['race']] += r['total'] or 0
        for r in rows:
            if not r['writein'] and r['party'] not in ('REP', 'DEM') and r['total'] is not None and r['total'] < (0.001 if r['race'] in STATEWIDE else 0.005) * rtot[r['race']]:
                r['writein'] = True
        for r in rows:
            if not r['writein'] and not r['total']: r['ok'] = False     # a ballot candidate with no votes: the reading lost the row
        bad = [r for r in rows if not r['ok'] and not r['writein']]
        badw = [r for r in rows if not r['ok'] and r['writein']]
        report.append(f'{year}: {len(rows)} rows, {len(bad)} ballot candidates not adding up, {len(badw)} write-in rows not adding up')
        for r in bad: report.append(f'   BAD {r["key"]} {r["county"]} {r["total"]}')
        # write-ins combined per race and county; a row that doesn't add up keeps its readable county numbers (the canvass total wins statewide)
        wsum = defaultdict(lambda: [0] * 15); wtot = defaultdict(int)
        # a district with fewer ballot candidates than seats: its leading write-ins count as candidates (2022 LD 22 Senate, Eva Diaz)
        for race in {r['race'] for r in rows if r['race'] not in STATEWIDE}:
            seats = 2 if race.startswith('State Representative') else 1
            onb = [r for r in rows if r['race'] == race and not r['writein']]
            wis = sorted([r for r in rows if r['race'] == race and r['writein'] and r['name']], key=lambda r: -(r['total'] or 0))
            for r in wis[:max(0, seats - len(onb))]:
                r['writein'] = False; r['name'] += ' (write-in)'
                report.append(f'   {year} {race}: write-in {r["name"]} counted as a candidate ({r["total"]:,} votes)')
        for r in rows:
            if r['writein']:
                c = [v or 0 for v in r['county']]
                if not r['ok'] and r['total'] is not None and sum(c) != r['total']:
                    # put the difference in the county with the most write-ins (Maricopa nearly always)
                    i = max(range(15), key=lambda k: c[k]); c[i] = max(0, c[i] + r['total'] - sum(c))
                for i in range(15): wsum[r['race']][i] += c[i]
                wtot[r['race']] += r['total'] or sum(c)
                continue
            party = PARTY.get(r['party'], 'I')
            if r['race'] in STATEWIDE:
                office = STATEWIDE[r['race']] + (' (special)' if year == 2020 and r['race'] == 'U.S. Senator' else '')
                for i, c in enumerate(COUNTIES):
                    sw.append({'race': f'{year} {office}', 'year': year, 'office': office, 'county_fips': FIPS[c], 'county': c, 'candidate': r['name'], 'party': party, 'votes': r['county'][i]})
            else:
                dist[(year, r['race'])].append((r['name'], party, r['total']))
        for race, c in wsum.items():
            if race in STATEWIDE:
                office = STATEWIDE[race] + (' (special)' if year == 2020 and race == 'U.S. Senator' else '')
                for i, cn in enumerate(COUNTIES):
                    if c[i]: sw.append({'race': f'{year} {office}', 'year': year, 'office': office, 'county_fips': FIPS[cn], 'county': cn, 'candidate': 'Write-ins', 'party': 'W', 'votes': c[i]})
            else:
                dist[(year, race)].append(('Write-ins', 'W', wtot[race]))
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'az_statewide_results_by_county.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['race', 'year', 'office', 'county_fips', 'county', 'candidate', 'party', 'votes']); w.writeheader(); w.writerows(sw)
    files = {'U.S. Representative in Congress': ('az_ushouse_results.csv', 'U.S. House', lambda y: 'c2012' if y <= 2020 else 'c2022'),
             'State Senator': ('az_senate_results.csv', 'Senate', lambda y: 'l2012' if y <= 2020 else 'l2022'),
             'State Representative': ('az_house_results.csv', 'House', lambda y: 'l2012' if y <= 2020 else 'l2022')}
    for prefix, (fn, label, plan) in files.items():
        rows = []
        for (year, race), cands in sorted(dist.items(), key=lambda k: (k[0][0], int(k[0][1].split('No. ')[1]))):
            if not race.startswith(prefix): continue
            d = int(race.split('No. ')[1])
            seats = 2 if prefix == 'State Representative' else 1
            unopposed = int(sum(1 for c in cands if c[1] != 'W') <= seats)
            for name, party, v in sorted(cands, key=lambda c: (c[1] == 'W', -c[2])):
                rows.append({'year': year, 'race': f'{year} {label}', 'plan': plan(year), 'district': d, 'candidate': name, 'party': party, 'votes': v, 'unopposed': unopposed})
        with open(os.path.join(out, fn), 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=['year', 'race', 'plan', 'district', 'candidate', 'party', 'votes', 'unopposed']); w.writeheader(); w.writerows(rows)
    print('\n'.join(report))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
