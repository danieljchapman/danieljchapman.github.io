#!/usr/bin/env python3
"""Election-night importer for the North Carolina dashboard.

Reads the State Board of Elections results file, which the state replaces with a fresh
snapshot every few minutes on election night:
  https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/YYYY_MM_DD/results_pct_YYYYMMDD.zip
(one tab-separated row per county, precinct, contest and choice). Writes:
  live_2026.csv     level, race, year, office, plan, unit, unit_name, candidate, party, votes, status, reporting, reporting_total
                    statewide races by county (unit = county FIPS); U.S. House, NC House, NC Senate by district (unit = district)
  live_status.json  phase, update time, source, problems
reporting / reporting_total are precincts reported / precincts, as published by the State Board's results site
(er.ncsbe.gov/enr/YYYYMMDD/data/county.txt per county, results_0.txt per contest). If those files can't be read,
they are estimated from the results file: real precincts with Election Day votes / real precincts on the ballot.
Early and absentee votes are counted first, so a county can show votes with 0 precincts reporting.

Usage: python3 nc_live.py [--date 2026-11-03] [--zip FILE] [--out DIR]
"""
import argparse, csv, datetime, io, json, os, re, subprocess, sys, time, zipfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_history import office_of, party_of, district_of, DISTRICT_CONTESTS  # same names and plans as the history files

FIELDS = ['level', 'race', 'year', 'office', 'plan', 'unit', 'unit_name', 'candidate', 'party', 'votes', 'status', 'reporting', 'reporting_total']


def county_title(c):
    return ' '.join('McDowell' if w == 'MCDOWELL' else w.title() for w in c.split())


def download(date, tries=4):
    d = date.replace('-', '')
    url = f"https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/{date.replace('-', '_')}/results_pct_{d}.zip"
    last = None
    for i in range(tries):
        p = subprocess.run(['curl', '-sS', '-L', '-m', '120', '-w', '\n%{http_code}', '-H', 'Cache-Control: no-cache', url + f'?t={int(time.time())}'], capture_output=True)
        body, _, code = p.stdout.rpartition(b'\n')
        if code == b'200' and body[:2] == b'PK':
            return body, url
        last = f'HTTP {code.decode() or "?"} {p.stderr.decode()[:120]}'
        time.sleep(3 + 4 * i)
    raise RuntimeError(f'{url}: {last}')


def rows_of(zbytes):
    z = zipfile.ZipFile(io.BytesIO(zbytes))
    name = next(n for n in z.namelist() if n.endswith('.txt'))
    text = z.read(name).decode('latin-1')
    return csv.DictReader(io.StringIO(text), delimiter='\t')


def num(x):
    try:
        return int(float(x or 0))
    except ValueError:
        return 0


def get_json(url):
    p = subprocess.run(['curl', '-sS', '-L', '-m', '60', '-w', '\n%{http_code}', url + f'?v={int(time.time())}'], capture_output=True)
    body, _, code = p.stdout.rpartition(b'\n')
    if code != b'200':
        raise RuntimeError(f'{url}: HTTP {code.decode() or "?"}')
    return json.loads(body.decode('utf-8-sig'))


def official_reporting(date):
    """{county name: (reported, total)}, {(contest name, county name or 'STATE'): (reported, total)} from er.ncsbe.gov."""
    base = f"https://er.ncsbe.gov/enr/{date.replace('-', '')}/data"
    county = {c['cnm'].strip().upper(): (int(c['prt']), int(c['ptl'])) for c in get_json(f'{base}/county.txt') if c['cnm'].strip().upper() != 'STATE'}
    contest = {}
    for c in get_json(f'{base}/results_0.txt'):
        name = re.sub(r'\s*\(VOTE FOR \d+\)\s*$', '', c['cnm']).strip().upper()
        contest[name] = (int(c['prt']), int(c['ptl']))
    return county, contest


def build(rows, year, fips, official=None):
    problems = []
    real = defaultdict(set)            # county -> real precincts on the ballot
    done = defaultdict(set)            # county -> real precincts with Election Day votes
    sw = defaultdict(int)              # (office, county, candidate, party) -> votes
    us = defaultdict(int)              # (level, district, candidate, party) -> votes
    us_prec = defaultdict(set)         # (level, district) -> {(county, precinct)} real precincts voting in the contest
    cname = {}                         # (level, district) -> contest name as the state writes it
    for r in rows:
        cty, prec = r['County'].strip(), r['Precinct'].strip()
        is_real = (r.get('Real Precinct') or 'Y').strip() == 'Y'
        if is_real:
            real[cty].add(prec)
            if num(r['Election Day']) > 0:
                done[cty].add(prec)
        if r['Contest Type'].strip() != 'S':
            continue
        name, ch = r['Contest Name'].strip(), r['Choice'].strip()
        v, p = num(r['Total Votes']), party_of(ch, r['Choice Party'] or '')
        off = office_of(name, year)
        if off:
            sw[(off, cty, ch, p)] += v
            continue
        lvl, d = district_of(name)
        if lvl:
            p = party_of(ch, r['Choice Party'] or '', blank='I')
            us[(lvl, d, ch, p)] += v
            cname[(lvl, d)] = name.upper()
            if is_real:
                us_prec[(lvl, d)].add((cty, prec))
    unknown = set(real) - set(fips)
    if unknown:
        problems.append(f'unknown counties: {sorted(unknown)}')
    rep = {c: (len(done[c]), len(real[c])) for c in real}
    oc, ok = official or ({}, {})
    if oc:
        missing = set(rep) - set(oc)
        if missing:
            problems.append(f'no official precinct count for {sorted(missing)}; estimated')
        rep.update({c: v for c, v in oc.items() if c in rep})
    all_in = bool(rep) and all(a >= b for a, b in rep.values())

    out, races = [], {}
    offices = sorted({k[0] for k in sw})
    for off in offices:
        keys = [k for k in sw if k[0] == off]
        votes = sum(sw[k] for k in keys)
        st = 'final' if all_in and votes else 'counting' if votes else 'pending'
        races[f'{year} {off}'] = st
        for (o, c, ch, p) in sorted(keys, key=lambda k: (k[1], -sw[k])):
            a, b = rep.get(c, (0, 0))
            out.append({'level': 'statewide', 'race': f'{year} {off}', 'year': year, 'office': off, 'plan': '', 'unit': fips.get(c, ''), 'unit_name': county_title(c),
                        'candidate': ch, 'party': p, 'votes': sw[(o, c, ch, p)], 'status': st, 'reporting': a, 'reporting_total': b})
    info = {lvl: (label, plans) for lvl, _, label, plans in DISTRICT_CONTESTS}
    for (lvl, d) in sorted({k[:2] for k in us}, key=lambda k: ([x[0] for x in DISTRICT_CONTESTS].index(k[0]), k[1])):
        label, plans = info[lvl]
        keys = [k for k in us if k[:2] == (lvl, d)]
        votes = sum(us[k] for k in keys)
        tot = len(us_prec[(lvl, d)]); got = sum(1 for (c, pr) in us_prec[(lvl, d)] if pr in done[c])
        o = ok.get(cname[(lvl, d)])
        if oc and o:
            got, tot = o
        st = 'final' if tot and got >= tot and votes else 'counting' if votes else 'pending'
        races[f'{year} {label} {d}'] = st
        for k in sorted(keys, key=lambda k: -us[k]):
            out.append({'level': lvl, 'race': f'{year} {label}', 'year': year, 'office': label, 'plan': plans.get(year, ''), 'unit': d, 'unit_name': '',
                        'candidate': k[2], 'party': k[3], 'votes': us[k], 'status': st, 'reporting': got, 'reporting_total': tot})
    return out, races, rep, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default='2026-11-03')
    ap.add_argument('--zip', help='read this results_pct zip instead of downloading')
    ap.add_argument('--out', default='.')
    ap.add_argument('--official', action='store_true', help='with --zip, still read precinct counts from er.ncsbe.gov')
    a = ap.parse_args()
    year = int(a.date[:4])
    fips = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nc_county_fips.json')))
    if a.zip:
        zb, src = open(a.zip, 'rb').read(), a.zip
    else:
        zb, src = download(a.date)
    official, note = None, None
    if not a.zip or a.official:
        try:
            official = official_reporting(a.date)
        except Exception as e:  # noqa: BLE001 - fall back to the estimate from the results file
            note = f'precincts reporting estimated (state results site: {str(e)[:120]})'
    rows, races, rep, problems = build(rows_of(zb), year, fips, official)
    if note:
        problems.insert(0, note)
    if not races:
        raise SystemExit('no statewide or U.S. House contests found; not writing')
    n_final = sum(s == 'final' for s in races.values()); n_count = sum(s == 'counting' for s in races.values())
    phase = 'pre-election' if not n_final and not n_count else 'final' if n_final == len(races) else 'counting'
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'live_2026.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    prec = [sum(x[0] for x in rep.values()), sum(x[1] for x in rep.values())]
    json.dump([{'phase': phase, 'updated_at': now, 'source': 'North Carolina State Board of Elections, unofficial', 'races': len(races), 'called': n_final,
                'counting': n_count, 'precincts': prec, 'problems': problems[:20], 'local_problems': []}], open(os.path.join(a.out, 'live_status.json'), 'w'), indent=1)
    print(json.dumps({'races': len(races), 'rows': len(rows), 'phase': phase, 'final': n_final, 'counting': n_count, 'precincts': prec, 'problems': len(problems)}))
    for p in problems:
        print('problem:', p, file=sys.stderr)


if __name__ == '__main__':
    main()
