"""Build the National page's data files.

Inputs (in SRC): clerk_2024.json (parse_clerk.py on the House Clerk's 2024 election statistics), gov2024.json (2024 governor
results), legislators-current.yaml + legislators-historical.yaml (unitedstates/congress-legislators), governors_now.json,
hex_layout.json (hexlayout.py).
Outputs (in OUT): us_results.csv (2024 Senate, House, governor results), us_seats.json (who held each seat before each
election, seats not up, maps redrawn), us_hex.json.
Usage: python3 build_us.py SRC OUT
"""
import csv, json, os, re, sys
import yaml

ST = {'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR', 'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
      'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID', 'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS', 'KENTUCKY': 'KY',
      'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD', 'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS', 'MISSOURI': 'MO',
      'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV', 'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM', 'NEW YORK': 'NY',
      'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH', 'OKLAHOMA': 'OK', 'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI',
      'SOUTH CAROLINA': 'SC', 'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT', 'VERMONT': 'VT', 'VIRGINIA': 'VA',
      'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV', 'WISCONSIN': 'WI', 'WYOMING': 'WY'}
NAME = {v: k.title() for k, v in ST.items()}

# Election dates and the day the seat holders are read from the roster (the day before the election)
DAY = {2024: '2024-11-04', 2026: '2026-10-27'}
# States whose U.S. House map changed from the previous election (district flips aren't meaningful there)
REDRAWN = {2024: ['AL', 'GA', 'LA', 'NC', 'NY'],
           2026: ['AL', 'CA', 'FL', 'LA', 'NC', 'OH', 'TN', 'TX', 'UT']}
GOV_UP = {2024: ['DE', 'IN', 'MO', 'MT', 'NH', 'NC', 'ND', 'UT', 'VT', 'WA', 'WV'],
          2026: ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'FL', 'GA', 'HI', 'ID', 'IL', 'IA', 'KS', 'ME', 'MD', 'MA', 'MI', 'MN', 'NE', 'NV', 'NH',
                 'NM', 'NY', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'VT', 'WI', 'WY']}
# Governors before the 2024 election (seats up in 2024), and the party of every other state's governor then.
# Differences from today: the 2024 winners took office in Jan 2025, Virginia (Youngkin, R) and New Jersey (Murphy, D) elected new
# governors in Nov 2025, South Dakota's Kristi Noem (R) resigned Jan 2025 (Larry Rhoden, R).
GOV_2024_UP = {'DE': ('John Carney', 'D'), 'IN': ('Eric Holcomb', 'R'), 'MO': ('Mike Parson', 'R'), 'MT': ('Greg Gianforte', 'R'),
               'NH': ('Chris Sununu', 'R'), 'NC': ('Roy Cooper', 'D'), 'ND': ('Doug Burgum', 'R'), 'UT': ('Spencer Cox', 'R'),
               'VT': ('Phil Scott', 'R'), 'WA': ('Jay Inslee', 'D'), 'WV': ('Jim Justice', 'R')}
GOV_2024_OTHER = {'VA': ('Glenn Youngkin', 'R'), 'NJ': ('Phil Murphy', 'D'), 'SD': ('Kristi Noem', 'R')}
GOV_NAME_FIX = {'Louisiana': 'Jeff Landry'}


def party_code(p):
    p = (p or '').strip()
    pl = p.lower()
    if pl.startswith('write-in') or pl in ('write-ins', 'scattering'):
        return 'W'
    if pl in ('republican',) or pl.startswith('republican'):
        return 'R'
    if pl in ('democrat', 'democratic', 'democratic-farmer-labor', 'democratic-nonpartisan league', 'democratic/progressive') or pl.startswith('democratic'):
        return 'D'
    if 'libertarian' in pl:
        return 'L'
    if 'green' in pl and 'peace' not in pl:
        return 'G'
    if 'constitution' in pl or pl in ('u.s. taxpayers', 'american constitution'):
        return 'C'
    if pl in ('independent', 'by petition', 'unenrolled independent', 'common sense independent', 'unaffiliated', 'no party affiliation', 'no political party', 'no party', 'no party preference', 'nonpartisan', 'independent politician'):
        return 'I'
    return 'O'


def roster(src):
    people = yaml.safe_load(open(os.path.join(src, 'legislators-current.yaml'))) + yaml.safe_load(open(os.path.join(src, 'legislators-historical.yaml')))
    terms = []
    for p in people:
        nm = p['name'].get('official_full') or (p['name']['first'] + ' ' + p['name']['last'])
        for t in p['terms']:
            terms.append((nm, t))
    return terms


def held(terms, day, kind):
    """Seat holders on a date: senate {(state, class): (name, party)}, house {(state, district): (name, party)}.
    A vacant seat gets its most recent holder, marked vacant."""
    out, last = {}, {}
    for nm, t in terms:
        if t['type'] != kind:
            continue
        key = (t['state'], t['class'] if kind == 'sen' else t.get('district'))
        if t['start'] <= day <= t['end']:
            out[key] = (nm, t.get('party'), False)
        elif t['end'] < day and (key not in last or t['end'] > last[key][0]):
            last[key] = (t['end'], nm, t.get('party'))
    return out, last


def pcode(roster_party):
    return {'Republican': 'R', 'Democrat': 'D', 'Independent': 'I'}.get(roster_party, 'O')


def main(src, out):
    os.makedirs(out, exist_ok=True)
    clerk = json.load(open(os.path.join(src, 'clerk_2024.json')))
    rows = []
    for x in clerk:
        if x['state'] not in ST:
            continue
        st = ST[x['state']]
        if x['chamber'] == 'senate':
            if x['district'] == 'UNEXPIRED' and st == 'CA':
                continue          # California's same-day contest for the last weeks of Feinstein's term
            seat = 'special' if x['district'] == 'UNEXPIRED' else ''
            rows.append({'level': 'senate', 'year': 2024, 'state': st, 'district': '', 'seat': seat, 'candidate': x['candidate'],
                         'party': party_code(x['party']), 'votes': x['votes'] if x['votes'] is not None else '', 'unopposed': int(x['votes'] is None)})
        else:
            rows.append({'level': 'house', 'year': 2024, 'state': st, 'district': x['district'], 'seat': '', 'candidate': x['candidate'],
                         'party': party_code(x['party']), 'votes': x['votes'] if x['votes'] is not None else '', 'unopposed': int(x['votes'] is None)})
    gov = json.load(open(os.path.join(src, 'gov2024.json')))
    for name, cands in gov.items():
        st = ST[name.replace('_', ' ').upper()]
        for party, cand, votes in cands:
            rows.append({'level': 'governor', 'year': 2024, 'state': st, 'district': '', 'seat': '', 'candidate': 'Write-ins' if party == 'W' and cand == 'Write-ins' else cand,
                         'party': party, 'votes': votes, 'unopposed': 0})
    # combine write-ins per race; mark winners (most votes; Maine's 2nd uses the final ranked-choice round, as the Clerk reports)
    comb = {}
    for r in rows:
        if r['party'] == 'W' and r['candidate'] in ('Write-ins',):
            k = (r['level'], r['state'], r['district'], r['seat'], 'Write-ins')
            if k in comb:
                comb[k]['votes'] = (comb[k]['votes'] or 0) + (r['votes'] or 0)
                r['_drop'] = True
            else:
                comb[k] = r
    rows = [r for r in rows if not r.get('_drop')]
    races = {}
    for r in rows:
        races.setdefault((r['level'], r['state'], r['district'], r['seat']), []).append(r)
    for rs in races.values():
        w = max(rs, key=lambda r: (r['unopposed'], r['votes'] or 0))
        for r in rs:
            r['winner'] = int(r is w)
    fields = ['level', 'year', 'state', 'district', 'seat', 'candidate', 'party', 'votes', 'winner', 'unopposed']
    rows.sort(key=lambda r: (r['level'], r['state'], str(r['district']).zfill(2), r['seat'], -(r['votes'] or 0)))
    with open(os.path.join(out, 'us_results.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore'); w.writeheader(); w.writerows(rows)

    # ---- seat holders before each election ----
    terms = roster(src)
    seats = {'senate': {}, 'house': {}, 'governor': {}, 'redrawn': REDRAWN, 'names': NAME}
    up_sen = {2024: {(st, 1) for st in ST.values()} | {('NE', 2)}, 2026: {(st, 2) for st in ST.values()} | {('FL', 3), ('OH', 3)}}
    for year in (2024, 2026):
        cur, last = held(terms, DAY[year], 'sen')
        sen = {}
        for (st, cl), (nm, party, _) in cur.items():
            if st not in NAME:
                continue
            sen.setdefault(st, []).append({'name': nm, 'party': pcode(party), 'class': cl, 'up': (st, cl) in up_sen[year]})
        for st in sen:
            sen[st].sort(key=lambda s: (not s['up'], s['class']))
        assert sum(len(v) for v in sen.values()) == 100, year
        seats['senate'][str(year)] = sen
        hcur, hlast = held(terms, DAY[year], 'rep')
        hs = {}
        for st in NAME:
            for (s2, d), v in list(hcur.items()) + [((k[0], k[1]), (l[1], l[2], True)) for k, l in hlast.items() if k not in hcur]:
                if s2 != st:
                    continue
                key = f'{st}-{int(d or 0):02d}'
                if key in hs and not hs[key]['vacant']:
                    continue
                hs[key] = {'name': v[0], 'party': pcode(v[1]), 'vacant': v[2]}
        seats['house'][str(year)] = hs
    # keep only real districts (the layout's 435 keys); a vacant seat keeps the party of its last member
    hexes = json.load(open(os.path.join(src, 'hex_layout.json')))
    for y in seats['house']:
        seats['house'][y] = {k: seats['house'][y][k] for k in hexes['hexes']}
    govnow = json.load(open(os.path.join(src, 'governors_now.json')))
    g26, g24 = {}, {}
    for name, (nm, party) in govnow.items():
        st = ST[name.upper()]
        nm = GOV_NAME_FIX.get(name, nm)
        pc = 'D' if 'Democratic' in party else 'R' if 'Republican' in party else 'I'
        g26[st] = {'name': nm, 'party': pc, 'up': st in GOV_UP[2026]}
        if st in GOV_2024_UP:
            g24[st] = {'name': GOV_2024_UP[st][0], 'party': GOV_2024_UP[st][1], 'up': True}
        elif st in GOV_2024_OTHER:
            g24[st] = {'name': GOV_2024_OTHER[st][0], 'party': GOV_2024_OTHER[st][1], 'up': False}
        else:
            g24[st] = {'name': nm, 'party': pc, 'up': False}
    seats['governor'] = {'2024': g24, '2026': g26}
    json.dump(seats, open(os.path.join(out, 'us_seats.json'), 'w'), separators=(',', ':'))
    json.dump(hexes, open(os.path.join(out, 'us_hex.json'), 'w'), separators=(',', ':'))
    # ---- summary ----
    for lvl in ('senate', 'house', 'governor'):
        win = [r for r in rows if r['level'] == lvl and r['winner']]
        print(lvl, len(win), 'races; winners', {p: sum(r['party'] == p for r in win) for p in 'RDI'})
    for y in ('2024', '2026'):
        s = seats['senate'][y]
        notup = [x['party'] for v in s.values() for x in v if not x['up']]
        up = [x['party'] for v in s.values() for x in v if x['up']]
        print('senate', y, 'up', len(up), {p: up.count(p) for p in 'RDI'}, 'not up', len(notup), {p: notup.count(p) for p in 'RDI'})
        g = seats['governor'][y]
        print('governor', y, 'up', sum(v['up'] for v in g.values()), 'not up by party', {p: sum((not v['up']) and v['party'] == p for v in g.values()) for p in 'RD'})
        h = seats['house'][y]
        print('house', y, len(h), {p: sum(v['party'] == p for v in h.values()) for p in 'RD'}, 'vacant', [k for k, v in h.items() if v['vacant']])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
