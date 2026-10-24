#!/usr/bin/env python3
"""Election-night importer for the Georgia dashboard.

Reads the Secretary of State's results site (Enhanced Voting), which needs no sign-in or bot check:
  https://results.sos.ga.gov/results/public/api/jurisdictions/Georgia          list of elections
  https://results.sos.ga.gov/results/public/api/elections/Georgia/<slug>/data  election summary (asOf = last publish)
  https://results.sos.ga.gov/cdn/results/Georgia/export-<slug>.json            every contest, statewide and by county,
                                                                                with precincts participating / reporting per county
Writes:
  live_2026.csv     level, race, year, office, plan, unit, unit_name, candidate, party, votes, status, reporting, reporting_total
                    statewide races by county (unit = county FIPS); U.S. House, Georgia House and Senate by district (unit = district)
  live_status.json  phase, update time, source, problems
reporting / reporting_total are precincts reported / precincts, from the state's county results. Advance and mail votes
are counted first, so a county can show votes with 0 precincts reporting.
If a general-election runoff on Dec 1, 2026 appears on the state's list, its statewide races are added with " runoff"
after the office (e.g. "2026 Senate runoff").

Usage: python3 ga_live.py [--slug 11032026GeneralAndSpecialElection] [--export FILE] [--out DIR]
"""
import argparse, csv, datetime, gzip, json, os, re, subprocess, sys, time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_history import statewide_office, district_of, clean_name, party_of, DISTRICT_CONTESTS  # same names and plans as the history files

API = 'https://results.sos.ga.gov/results/public/api'
CDN = 'https://results.sos.ga.gov/cdn/results/'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
FIELDS = ['level', 'race', 'year', 'office', 'plan', 'unit', 'unit_name', 'candidate', 'party', 'votes', 'status', 'reporting', 'reporting_total']
GENERAL = '11032026GeneralAndSpecialElection'


def get(url, tries=4):
    last = None
    for i in range(tries):
        p = subprocess.run(['curl', '-sS', '-L', '--compressed', '-m', '240', '-A', UA, '-H', 'Cache-Control: no-cache', '-w', '\n%{http_code}', url + ('&' if '?' in url else '?') + f't={int(time.time())}'], capture_output=True)
        body, _, code = p.stdout.rpartition(b'\n')
        if code == b'200' and body[:1] in (b'{', b'['):
            return json.loads(body)
        last = f'HTTP {code.decode() or "?"} {p.stderr.decode()[:120]}'
        time.sleep(3 + 4 * i)
    raise RuntimeError(f'{url}: {last}')


def runoff_slug(problems):
    """The Dec 1, 2026 general-election runoff, once the state lists it."""
    try:
        for e in get(f'{API}/jurisdictions/Georgia').get('elections') or []:
            name = ' '.join(t['text'] for t in e.get('name') or [])
            if e.get('electionDate') == '2026-12-01' and re.search('runoff', name, re.I) and not re.search('special|primary', name, re.I):
                return e['publicElectionId']
    except Exception as ex:  # noqa: BLE001
        problems.append(f'election list: {str(ex)[:120]}')
    return None


def build(exp, year, fips, runoff=False):
    """Rows and race statuses from one export."""
    by_upper = {k.upper().replace(' ', ''): (k, v) for k, v in fips.items()}
    problems, rows, races = [], [], {}
    sw = defaultdict(int)                       # (office, county, candidate, party) -> votes
    sw_rep = {}                                 # (office, county) -> (reporting, total)
    dist = defaultdict(int)                     # (level, district, candidate, party) -> votes
    dist_rep = defaultdict(lambda: [0, 0])      # (level, district) -> [reporting, total] over counties
    def classify(name):
        off = statewide_office(name)
        if off:
            return ('statewide', off + (' runoff' if runoff else ''), None)
        lvl, d = district_of(name)
        return (lvl, None, d) if lvl and not runoff else None
    state_tot = {}                              # (contest, candidate) -> the state's own total, to check the county sums
    listed = {}                                 # contest -> candidates on the state's list (others are county-only write-ins)
    state_names = {b['name'].strip() for b in exp['results']['ballotItems']}
    for b in exp['results']['ballotItems']:
        o = classify(b['name'])
        if o:
            listed[o] = {clean_name(x['name']) for x in b['ballotOptions']}
            for x in b['ballotOptions']:
                state_tot[(o, clean_name(x['name']))] = x['voteCount'] or 0
    for loc in exp['localResults']:
        key = re.sub(r'\s+County$', '', loc['name']).upper().replace(' ', '')
        if key not in by_upper:
            problems.append(f'unknown county {loc["name"]}')
            continue
        cname, cf = by_upper[key]
        for b in loc['ballotItems']:
            # counties don't always use the state's contest id or wording, so classify the county's own contest name
            o = classify(b['name'])
            # a few counties tag general-election contests with a primary suffix ('Commissioner of Insurance - Rep')
            m = re.match(r'^(.*?)\s+-\s+(Rep|Dem)$', b['name'].strip())
            if o not in listed and m and b['name'].strip() not in state_names:
                o = classify(m.group(1))
            if o not in listed:
                continue
            got, tot = b.get('precinctsReporting') or 0, b.get('precinctsParticipating') or 0
            lvl, off, d = o
            for opt in b['ballotOptions']:
                nm = clean_name(opt['name'])
                # qualified write-in candidates appear only in county results, without a party
                p = 'W' if nm not in listed[o] else party_of(opt, blank='O') if lvl == 'statewide' else party_of(opt)
                if p == 'W':
                    nm = 'Write-ins'
                if lvl == 'statewide':
                    sw[(off, cname, nm, p)] += opt['voteCount'] or 0
                else:
                    dist[(lvl, d, nm, p)] += opt['voteCount'] or 0
            if lvl == 'statewide':
                sw_rep[(off, cname)] = (got, tot)
            else:
                dist_rep[(lvl, d)][0] += got; dist_rep[(lvl, d)][1] += tot
    # checks: every statewide race in all 159 counties; county sums equal the state's totals
    for off in sorted({k[0] for k in sw}):
        n = len({k[1] for k in sw if k[0] == off})
        if n != len(fips):
            problems.append(f'{off}: {n} of {len(fips)} counties')
    csum = defaultdict(int)
    for (off, c, nm, p), v in sw.items():
        csum[(('statewide', off, None), nm)] += v
    for (lvl, d, nm, p), v in dist.items():
        csum[((lvl, None, d), nm)] += v
    off_by = [f'{k[0][1] or k[0][0] + " " + str(k[0][2])} {k[1]}: counties {csum.get(k, 0):,} vs state {v:,}' for k, v in state_tot.items() if csum.get(k, 0) != v]
    if off_by:
        problems.append(f'{len(off_by)} candidate totals differ from the state summary, e.g. ' + '; '.join(off_by[:3]))
    for off in sorted({k[0] for k in sw}):
        keys = [k for k in sw if k[0] == off]
        votes = sum(sw[k] for k in keys)
        reps = [v for (o, c), v in sw_rep.items() if o == off]
        done = bool(reps) and all(t and g >= t for g, t in reps)
        st = 'final' if done and votes else 'counting' if votes else 'pending'
        races[f'{year} {off}'] = st
        for k in sorted(keys, key=lambda k: (k[1], -sw[k])):
            g, t = sw_rep.get((off, k[1]), (0, 0))
            rows.append({'level': 'statewide', 'race': f'{year} {off}', 'year': year, 'office': off, 'plan': '', 'unit': fips[k[1]], 'unit_name': k[1],
                         'candidate': k[2], 'party': k[3], 'votes': sw[k], 'status': st, 'reporting': g, 'reporting_total': t})
    info = {lvl: (label, plans) for lvl, _, label, plans in DISTRICT_CONTESTS}
    order = [x[0] for x in DISTRICT_CONTESTS]
    for (lvl, d) in sorted({k[:2] for k in dist}, key=lambda k: (order.index(k[0]), k[1])):
        label, plans = info[lvl]
        keys = [k for k in dist if k[:2] == (lvl, d)]
        votes = sum(dist[k] for k in keys)
        g, t = dist_rep[(lvl, d)]
        st = 'final' if t and g >= t and votes else 'counting' if votes else 'pending'
        races[f'{year} {label} {d}'] = st
        for k in sorted(keys, key=lambda k: -dist[k]):
            rows.append({'level': lvl, 'race': f'{year} {label}', 'year': year, 'office': label, 'plan': plans.get(year, ''), 'unit': d, 'unit_name': '',
                         'candidate': k[2], 'party': k[3], 'votes': dist[k], 'status': st, 'reporting': g, 'reporting_total': t})
    return rows, races, problems


def fetch_election(slug, problems):
    """(export, summary) for one election; notes a stale export (older than the latest publish)."""
    data = get(f'{API}/elections/Georgia/{slug}/data')
    path = (data.get('jurisdiction') or {}).get('mediaExportPath') or f'Georgia/export-{slug}.json'
    exp = get(CDN + path)
    try:
        as_of = datetime.datetime.fromisoformat(data['election']['asOf'][:19])
        made = datetime.datetime.fromisoformat(exp['createdAt'][:19])
        if (as_of - made).total_seconds() > 900:
            problems.append(f'{slug}: county file is {int((as_of - made).total_seconds() // 60)} minutes behind the state summary')
    except Exception:  # noqa: BLE001
        pass
    return exp, data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slug', default=GENERAL)
    ap.add_argument('--export', help='read this export file (.json or .json.gz) instead of downloading')
    ap.add_argument('--out', default='.')
    a = ap.parse_args()
    fips = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ga_county_fips.json')))
    problems = []
    if a.export:
        raw = open(a.export, 'rb').read()
        exp = json.loads(gzip.decompress(raw) if a.export.endswith('.gz') else raw)
    else:
        exp, _ = fetch_election(a.slug, problems)
    year = int(exp['electionDate'][:4])
    rows, races, p = build(exp, year, fips)
    problems += p
    if not a.export:
        rs = runoff_slug(problems)
        if rs:
            try:
                rexp, _ = fetch_election(rs, problems)
                r_rows, r_races, p = build(rexp, year, fips, runoff=True)
                rows += r_rows; races.update(r_races); problems += p
            except Exception as ex:  # noqa: BLE001 - the runoff never stops the general-election update
                problems.append(f'runoff {rs}: {str(ex)[:120]}')
    if not races:
        raise SystemExit('no statewide or district contests found; not writing')
    n_final = sum(s == 'final' for s in races.values()); n_count = sum(s == 'counting' for s in races.values())
    phase = 'pre-election' if not n_final and not n_count else 'final' if n_final == len(races) else 'counting'
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'live_2026.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    first = next((r['race'] for r in rows if r['level'] == 'statewide'), None)   # precinct counts are the same for every statewide race
    gov = [r for r in rows if r['race'] == first]
    prec = [sum(r['reporting'] for r in {r['unit']: r for r in gov}.values()), sum(r['reporting_total'] for r in {r['unit']: r for r in gov}.values())]
    json.dump([{'phase': phase, 'updated_at': now, 'source': 'Georgia Secretary of State, unofficial', 'races': len(races), 'called': n_final,
                'counting': n_count, 'precincts': prec, 'problems': problems[:20], 'local_problems': []}], open(os.path.join(a.out, 'live_status.json'), 'w'), indent=1)
    print(json.dumps({'races': len(races), 'rows': len(rows), 'phase': phase, 'final': n_final, 'counting': n_count, 'precincts': prec, 'problems': len(problems)}))
    for p in problems:
        print('problem:', p, file=sys.stderr)


if __name__ == '__main__':
    main()
