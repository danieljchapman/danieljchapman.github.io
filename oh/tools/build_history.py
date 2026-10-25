#!/usr/bin/env python3
"""Ohio general-election results 2016-2024 from the Secretary of State's official canvass workbooks
(ohiosos.gov/globalassets/elections/<year>/gen/..., retrieved from the Internet Archive because the
state's site blocks automated downloads). Writes, to OUT_DIR:
  oh_statewide_results_by_county.csv  race,year,office,county_fips,county,candidate,party,votes
  oh_ushouse_results.csv / oh_house_results.csv / oh_senate_results.csv  year,race,plan,district,candidate,party,votes,unopposed
  oh_turnout_county.csv  year,county_fips,county,registered,ballots
Write-in candidates are combined into one 'Write-ins' row (party W) per county or district.
Usage: build_history.py SRC_DIR OUT_DIR"""
import openpyxl, re, csv, sys, os, json, collections
SRC, OUT = sys.argv[1], sys.argv[2]
FIPS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'oh_county_fips.json')))  # {county name: fips}
FILES = {2014: '2014_results.xlsx', 2016: '2016_gen_county.xlsx', 2018: '2018_gen_2018-11-06_statewidecounty_miami.xlsx', 2020: '2020_gen_statewideresultsbycounty.xlsx',
         2022: '2022_gen_statewide-races-summary.xlsx', 2024: '2024_gen_official_statewide-races-precint-level.xlsx'}
# district plans in force each year
PLANS = {'ushouse': {2014: 'c2012', 2016: 'c2012', 2018: 'c2012', 2020: 'c2012', 2022: 'c2022', 2024: 'c2022'},
         'house': {2014: 'h2012', 2016: 'h2012', 2018: 'h2012', 2020: 'h2012', 2022: 'h2022', 2024: 'h2023'},
         'senate': {2014: 's2012', 2016: 's2012', 2018: 's2012', 2020: 's2012', 2022: 's2022', 2024: 's2023'}}
STATEWIDE = {'President': 'President', 'President and Vice President': 'President', 'U.S. Senator': 'Senate', 'Governor and Lieutenant Governor': 'Governor', 'Governor': 'Governor',
             'Attorney General': 'Attorney General', 'Auditor of State': 'Auditor', 'Secretary of State': 'Secretary of State', 'Treasurer of State': 'Treasurer'}
PARTY = {'D': 'D', 'R': 'R', 'L': 'L', 'G': 'G', 'WI': 'W'}


def seat_of(title, sub, year):
    """Ohio Supreme Court seats aren't numbered; a seat is known by the day its term starts (Jan. 1 or Jan. 2)
    and its six-year cycle. Seats are labeled by the justice holding them in 2026. Only 2022 and later:
    party labels first appeared on the general-election ballot in 2022."""
    if 'Chief Justice' in title:
        return 'Supreme Court, Chief Justice'
    m = re.search(r'Term Commencing (\d\d)/(\d\d)/(\d{4})', sub)
    if m:
        day, start = int(m.group(2)), int(m.group(3))
        cycle = (start - 2017) % 6  # 0: 2017/2023/2029, 2: 2019/2025, 4: 2021/2027
        return SEATS[(cycle, day)]
    if re.search(r'Unexpired Term Ending 12/31/2026', sub):
        return SEATS[(4, 1)]
    raise ValueError((title, sub, year))


SEATS = {(0, 1): 'Supreme Court, Fischer seat', (0, 2): 'Supreme Court, DeWine seat', (2, 1): 'Supreme Court, Shanahan seat',
         (2, 2): 'Supreme Court, Deters seat', (4, 1): 'Supreme Court, Hawkins seat', (4, 2): 'Supreme Court, Brunner seat'}


def split_name(h):
    h = re.sub(r'\s+', ' ', h.replace('*', '')).strip()
    m = re.match(r'^(.*?)\s*\((D|R|L|G|WI)\)$', h)
    name, party = (m.group(1), PARTY[m.group(2)]) if m else (h, 'I')
    name = re.split(r' and ', name)[0].strip()  # ticket: keep the top of the ticket
    return name, party


def read(year):
    ws = openpyxl.load_workbook(os.path.join(SRC, FILES[year]), read_only=True)['Master']
    it = ws.iter_rows(values_only=True)
    h0, h1 = next(it), next(it)
    ncol = {2014: 5, 2024: 8}.get(year, 6)
    contests, cur = [], None
    for i in range(ncol, len(h1)):
        if h0[i]:
            parts = str(h0[i]).split('\n')
            cur = (parts[0].strip(), ' '.join(p.strip() for p in parts[1:]).strip())
        if h1[i] is None:
            continue
        contests.append((i, cur, split_name(str(h1[i]))))
    votes = collections.Counter()  # (county, col) -> votes
    turnout = collections.Counter()
    for r in it:
        c = r[0]
        if not c or c in ('Total', 'Percentage', 'Percentage of Votes') or c not in FIPS:
            if c and c not in ('Total', 'Percentage', 'Percentage of Votes'):
                raise ValueError(f'{year}: unknown county {c}')
            continue
        reg, bal = (r[5], r[6]) if year == 2024 else (r[3], r[4])
        if isinstance(reg, str) or isinstance(bal, str):
            raise ValueError(f'{year} {c}: formula instead of a number')
        turnout[(c, 'reg')] += int(reg or 0); turnout[(c, 'bal')] += int(bal or 0)
        for i, _, _ in contests:
            votes[(c, i)] += int(r[i] or 0)
    return contests, votes, turnout


sw_rows, dist_rows, turn_rows, checks = [], collections.defaultdict(list), [], []
for year in sorted(FILES):
    contests, votes, turnout = read(year)
    for c in sorted(FIPS):
        turn_rows.append([year, FIPS[c], c, turnout[(c, 'reg')], turnout[(c, 'bal')]])
    by = collections.defaultdict(list)
    for i, (title, sub), (name, party) in contests:
        by[(title, sub)].append((i, name, party))
    for (title, sub), cands in by.items():
        full = re.sub(r'\s+', ' ', f'{title} {sub}').strip()
        m = re.match(r'^(Representative to Congress|U\.S\. House of Representatives|State Senator|State Senate|State Representative|State House of Representatives)\s*-?\s*District (\d+)\b', full)
        if title in STATEWIDE or 'Supreme Court' in title:
            if 'Supreme Court' in title:
                if year < 2022:
                    continue
                office = seat_of(title, sub, year)
            else:
                office = STATEWIDE[title]
            race = f'{year} {office}'
            for c in sorted(FIPS):
                wi = 0
                for i, name, party in cands:
                    v = votes[(c, i)]
                    if party == 'W':
                        wi += v
                    else:
                        sw_rows.append([race, year, office, FIPS[c], c, name, party, v])
                if any(p == 'W' for _, _, p in cands):
                    sw_rows.append([race, year, office, FIPS[c], c, 'Write-ins', 'W', wi])
        elif m:
            level = {'Representative to Congress': 'ushouse', 'U.S. House of Representatives': 'ushouse', 'State Senator': 'senate', 'State Senate': 'senate',
                     'State Representative': 'house', 'State House of Representatives': 'house'}[m.group(1)]
            label = {'ushouse': 'U.S. House', 'senate': 'Senate', 'house': 'House'}[level]
            d = int(m.group(2))
            race = f'{year} {label}'  # 2024's unexpired-term SD 33 race sits with that year's even-numbered seats
            real = [(i, n, p) for i, n, p in cands if p != 'W']
            tot = {n: sum(votes[(c, i)] for c in FIPS) for i, n, p in cands}
            unopp = int(len([1 for i, n, p in real if tot[n] > 0]) <= 1)
            for i, n, p in real:
                dist_rows[level].append([year, race, PLANS[level][year], d, n, p, tot[n], unopp])
            wi = sum(tot[n] for i, n, p in cands if p == 'W')
            if any(p == 'W' for _, _, p in cands) and wi:
                dist_rows[level].append([year, race, PLANS[level][year], d, 'Write-ins', 'W', wi, unopp])
        elif re.search(r'Court of Appeals|Board of Education|Supreme Court', title):
            continue
        else:
            print('skipped contest', year, title, sub)
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, 'oh_statewide_results_by_county.csv'), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['race', 'year', 'office', 'county_fips', 'county', 'candidate', 'party', 'votes']); w.writerows(sw_rows)
for level, rows in dist_rows.items():
    with open(os.path.join(OUT, f'oh_{level}_results.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['year', 'race', 'plan', 'district', 'candidate', 'party', 'votes', 'unopposed'])
        w.writerows(sorted(rows, key=lambda r: (r[0], r[1], r[3], -r[6])))
with open(os.path.join(OUT, 'oh_turnout_county.csv'), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['year', 'county_fips', 'county', 'registered', 'ballots']); w.writerows(turn_rows)
print('statewide rows', len(sw_rows), {k: len(v) for k, v in dist_rows.items()})
