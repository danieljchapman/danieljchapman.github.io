#!/usr/bin/env python3
"""Election-night importer for the Ohio dashboard.

Source: the Ohio Secretary of State's election-night results site, "Ohio Decides" (liveresults.ohiosos.gov). Its
"Election Results XML Feed" is a NIST 1500-100 file of every contest statewide and by county, refreshed about every
three minutes on election night:
  https://liveresults.ohiosos.gov/Api/v1/download?filename=VSSC1622XmlFileBlob
The site sits behind a Cloudflare bot check that refuses plain requests, so the file is fetched from inside a
headless Chromium page (Playwright), which the check lets through.

Writes:
  live_2026.csv     level, race, year, office, plan, unit, unit_name, candidate, party, votes, status, reporting, reporting_total
                    statewide races by county (unit = county FIPS); U.S. House, Ohio House and Senate by district (unit = district)
  live_status.json  phase, update time, source, problems
reporting / reporting_total are a county's precincts reported / precincts (the feed gives them per county, not per contest).
A district race is final when every county it touches has all precincts in. Write-in candidates are combined as 'Write-ins'.

Usage: python3 oh_live.py [--xml FILE] [--out DIR]
"""
import argparse, csv, datetime, json, os, re, sys, xml.etree.ElementTree as ET
from collections import defaultdict

NS = '{http://grouper.ieee.org/groups/1622/groups/2/V1/1622_2-election_results_reporting.xsd}'
XSI = '{http://www.w3.org/2001/XMLSchema-instance}'
SITE = 'https://liveresults.ohiosos.gov/'
FEED = '/Api/v1/download?filename=VSSC1622XmlFileBlob'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
FIELDS = ['level', 'race', 'year', 'office', 'plan', 'unit', 'unit_name', 'candidate', 'party', 'votes', 'status', 'reporting', 'reporting_total']
STATEWIDE = {'Governor and Lieutenant Governor': 'Governor', 'Attorney General': 'Attorney General', 'Auditor of State': 'Auditor',
             'Secretary of State': 'Secretary of State', 'Treasurer of State': 'Treasurer', 'U.S. Senator': 'Senate', 'President and Vice President': 'President'}
# Supreme Court seats by the day the term starts (same seat names as build_history.py)
COURT = {'2027-01-01': 'Supreme Court, Hawkins seat', '2027-01-02': 'Supreme Court, Brunner seat'}
DISTRICT = [(r'^Representative to Congress - District (\d+)$', 'ushouse', 'U.S. House', 'c2025'),
            (r'^State Senator - District (\d+)$', 'senate', 'Senate', 's2023'),
            (r'^State Representative - District (\d+)$', 'house', 'House', 'h2023')]
PARTY = {'REP': 'R', 'DEM': 'D', 'LIB': 'L', 'GRN': 'G', 'GRE': 'G', 'Write-in': 'W', 'Indep': 'I', 'Nonprtycan': 'I', 'None': 'I', 'Other-part': 'O'}


def fetch_feed():
    """The XML feed as bytes, read from inside a real browser page so the bot check lets it through."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=['--disable-blink-features=AutomationControlled'])
        try:
            pg = b.new_context(user_agent=UA).new_page()
            last = None
            for attempt in range(3):
                pg.goto(SITE, timeout=90000)
                pg.wait_for_timeout(4000 + 4000 * attempt)
                res = pg.evaluate("""async (u) => { const r = await fetch(u + '&t=' + Date.now(), {cache: 'no-store'});
                                     return [r.status, await r.text()]; }""", FEED)
                if res[0] == 200 and res[1].lstrip().startswith('<?xml'):
                    return res[1].encode('utf-8')
                last = f'HTTP {res[0]} {res[1][:120]!r}'
            raise RuntimeError(f'feed: {last}')
        finally:
            b.close()


def nice(s):
    return re.sub(r'\s+', ' ', s or '').strip()


def build(root, fips):
    problems = []
    gp = {g.get('ObjectId'): g for g in root.find(NS + 'GpUnitCollection')}
    # county reporting units (the ones carrying precinct counts; 'X County' units are county-office districts)
    county = {}
    for oid, g in gp.items():
        if g.get('Type') == 'County' and g.get('TotalSubUnits') is not None:
            name = g.get('Name')
            if name not in fips:
                problems.append(f'unknown county {name}'); continue
            county[oid] = (name, int(g.get('SubUnitsReported') or 0), int(g.get('TotalSubUnits') or 0))
    if len(county) != len(fips):
        problems.append(f'{len(county)} of {len(fips)} counties in the feed')
    party = {p.get('ObjectId'): PARTY.get(p.get('Abbreviation'), 'O') for p in root.find(NS + 'PartyCollection')}
    election = root.find(NS + 'Election')
    cand = {}
    for c in election.find(NS + 'CandidateCollection'):
        nm = c.find(f'{NS}BallotName/{NS}LanguageString')
        pid = c.find(NS + 'PartyId')
        cand[c.get('ObjectId')] = (nice(nm.text if nm is not None else ''), party.get(pid.text if pid is not None else '', 'I'))
    office_term = {}
    for o in root.find(NS + 'OfficeCollection'):
        t = o.find(NS + 'Term')
        office_term[o.get('ObjectId')] = t.get('StartDate') if t is not None else None
    year = 2026
    rows, races = [], {}
    for c in election.find(NS + 'ContestCollection'):
        if c.get(XSI + 'type') != 'CandidateContest':
            continue
        name = nice(c.get('Name'))
        level, office, d, plan = None, None, None, ''
        if name in STATEWIDE:
            level, office = 'statewide', STATEWIDE[name]
        elif name == 'Justice of the Supreme Court':
            oid = c.find(NS + 'OfficeId')
            start = office_term.get(oid.text if oid is not None else '')
            if start not in COURT:
                problems.append(f'Supreme Court contest with unexpected term start {start}'); continue
            level, office = 'statewide', COURT[start]
        else:
            for pat, lvl, label, pl in DISTRICT:
                m = re.match(pat, name)
                if m:
                    level, office, d, plan = lvl, label, int(m.group(1)), pl
                    break
        if not level:
            continue
        per = defaultdict(lambda: defaultdict(int))   # county oid -> (candidate, party) -> votes
        for bs in c.findall(NS + 'BallotSelection'):
            ids = [x.text for x in bs.findall(NS + 'CandidateId') if not (x.text or '').startswith('_CO')]  # _CO.. = running mate
            nm, p = cand.get(ids[0], ('', 'I')) if ids else ('', 'I')
            if bs.get('IsWriteIn') == 'true' or p == 'W':
                nm, p = 'Write-ins', 'W'
            vcc = bs.find(NS + 'VoteCountsCollection')
            for vc in (vcc if vcc is not None else []):
                if vc.get('Type') != 'Total':
                    continue
                g = vc.find(NS + 'GpUnitId').text
                if g in county:
                    per[g][(nm, p)] += int(vc.get('Count') or 0)
        if not per:
            problems.append(f'{name}: no county results'); continue
        votes = sum(v for cc in per.values() for v in cc.values())
        done = all(county[g][2] and county[g][1] >= county[g][2] for g in per)
        st = 'final' if done and votes else 'counting' if votes else 'pending'
        race = f'{year} {office}'
        if level == 'statewide':
            if len(per) != len(fips):
                problems.append(f'{office}: {len(per)} of {len(fips)} counties')
            races[race] = st
            for g in sorted(per, key=lambda g: county[g][0]):
                cn, got, tot = county[g]
                for (nm, p), v in sorted(per[g].items(), key=lambda kv: -kv[1]):
                    rows.append({'level': 'statewide', 'race': race, 'year': year, 'office': office, 'plan': '', 'unit': fips[cn], 'unit_name': cn,
                                 'candidate': nm, 'party': p, 'votes': v, 'status': st, 'reporting': got, 'reporting_total': tot})
        else:
            races[f'{race} {d}'] = st
            tot = defaultdict(int)
            for cc in per.values():
                for k, v in cc.items():
                    tot[k] += v
            got = sum(county[g][1] for g in per); all_ = sum(county[g][2] for g in per)
            for (nm, p), v in sorted(tot.items(), key=lambda kv: -kv[1]):
                rows.append({'level': level, 'race': race, 'year': year, 'office': office, 'plan': plan, 'unit': d, 'unit_name': '',
                             'candidate': nm, 'party': p, 'votes': v, 'status': st, 'reporting': got, 'reporting_total': all_})
    # districts on the ballot: 15 U.S. House, 99 Ohio House, 17 Ohio Senate (odd-numbered seats in 2026)
    for lvl, n in [('ushouse', 15), ('house', 99), ('senate', 17)]:
        have = len({r['unit'] for r in rows if r['level'] == lvl})
        if have != n:
            problems.append(f'{lvl}: {have} of {n} districts')
    prec = [sum(v[1] for v in county.values()), sum(v[2] for v in county.values())]
    return rows, races, problems, prec, root.get('IsTest') == 'true'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--xml', help='read this feed file instead of downloading')
    ap.add_argument('--out', default='.')
    ap.add_argument('--keep-test', action='store_true', help="keep a test feed's mock votes (for checking the page)")
    a = ap.parse_args()
    fips = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'oh_county_fips.json')))
    raw = open(a.xml, 'rb').read() if a.xml else fetch_feed()
    root = ET.fromstring(raw)
    rows, races, problems, prec, is_test = build(root, fips)
    if not races:
        raise SystemExit('no statewide or district contests found; not writing')
    n_final = sum(s == 'final' for s in races.values()); n_count = sum(s == 'counting' for s in races.values())
    phase = 'pre-election' if not n_final and not n_count else 'final' if n_final == len(races) else 'counting'
    if is_test and not a.keep_test:
        # Before Election Day the state posts mock-election numbers (IsTest="true"); show every race at zero instead
        for r in rows:
            r['votes'], r['status'], r['reporting'] = 0, 'pending', 0
        phase, n_final, n_count = 'pre-election', 0, 0
        prec[0] = 0
        problems.append('the state feed is still a test file (mock votes set to zero)')
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'live_2026.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    json.dump([{'phase': phase, 'updated_at': now, 'source': 'Ohio Secretary of State, unofficial', 'races': len(races), 'called': n_final,
                'counting': n_count, 'precincts': prec, 'feed_generated': root.get('GeneratedDate'), 'problems': problems[:20], 'local_problems': []}],
              open(os.path.join(a.out, 'live_status.json'), 'w'), indent=1)
    print(json.dumps({'races': len(races), 'rows': len(rows), 'phase': phase, 'final': n_final, 'counting': n_count, 'precincts': prec,
                      'test_feed': is_test, 'problems': len(problems)}))
    for p in problems:
        print('problem:', p, file=sys.stderr)


if __name__ == '__main__':
    main()
