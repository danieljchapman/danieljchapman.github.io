"""Election-night results from the Texas Secretary of State (goelect.txelections.civixapps.com).

The state's results app reads base64-encoded JSON from an open API:
  /s3/enr/electionConstants            list of elections (find the one on our date)
  /s3/enr/election/{id}                race totals (Federal, StateWide, Districted, ...)
  /s3/enr/election/countyInfo/{id}     every race by county, with precincts reporting
This covers every statewide race and every U.S. House, Texas House, Texas Senate and SBOE seat,
including unopposed ones. Rows use the live_2026.csv columns.
"""
import base64, datetime, json, re, subprocess, unicodedata

API = 'https://goelect.txelections.civixapps.com/api-ivis-system/api/s3/enr'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
PARTY = {'REP': 'R', 'DEM': 'D', 'LIB': 'L', 'GRN': 'G', 'GRE': 'G', 'IND': 'I', 'W': 'W', 'R': 'R', 'D': 'D', 'L': 'L', 'G': 'G', 'I': 'I'}
STATEWIDE = {'U. S. SENATOR': 'Senate', 'GOVERNOR': 'Governor', 'LIEUTENANT GOVERNOR': 'Lt. Governor', 'ATTORNEY GENERAL': 'Attorney General',
             'COMPTROLLER OF PUBLIC ACCOUNTS': 'Comptroller', 'COMMISSIONER OF THE GENERAL LAND OFFICE': 'Land Commissioner',
             'COMMISSIONER OF AGRICULTURE': 'Agriculture Commissioner', 'RAILROAD COMMISSIONER': 'Railroad Commissioner'}
DISTRICT = [(r'^STATE REPRESENTATIVE DISTRICT (\d+)$', 'house', 'House', 'planh2316'), (r'^STATE SENATOR, DISTRICT (\d+)$', 'senate', 'Senate', 'plans2168'),
            (r'^U\. S\. REPRESENTATIVE DISTRICT (\d+)$', 'ushouse', 'U.S. House', 'planc2333'),
            (r'^MEMBER, STATE BOARD OF EDUCATION, DISTRICT (\d+)$', 'sboe', 'SBOE', 'plane2106')]


def get(path, tries=3):
    code = '?'
    for _ in range(tries):
        p = subprocess.run(['curl', '-s', '--compressed', '-m', '90', '-A', UA, '-w', '\n%{http_code}', f'{API}/{path}'], capture_output=True)
        body, _, code = p.stdout.rpartition(b'\n')
        if code == b'200':
            return json.loads(body)
    raise RuntimeError(f'{path}: HTTP {code}')


def unpack(v):
    return json.loads(base64.b64decode(v)) if isinstance(v, str) else v


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn' and c.isalnum())


def nice(name):
    """'JOHN H. BUCY III (I)' -> 'John H. Bucy III'."""
    name = re.sub(r'\s*\(I\)\s*$', '', name.strip())
    name = re.sub(r',\s*(JR\.?|SR\.?|II|III|IV)$', r' \1', name)
    out = []
    for w in name.split():
        if re.fullmatch(r'(II|III|IV|JR\.?|SR\.?)', w):
            out.append(w if w.startswith(('I', 'V')) else w.title()); continue
        w = '-'.join(p[:1].upper() + p[1:].lower() for p in w.split('-'))
        w = re.sub(r'^(Mc|O\'|D\')([a-z])', lambda m: m.group(1) + m.group(2).upper(), w)
        w = re.sub(r'^(["\'])(\w)', lambda m: m.group(1) + m.group(2).upper(), w)
        out.append(w)
    return ' '.join(out)


def office_of(n):
    """Dashboard office (level, office, plan, district) for a state race name, or None."""
    n = re.sub(r'\s+', ' ', n).strip()
    if n in STATEWIDE:
        return ('statewide', STATEWIDE[n], '', None)
    m = re.match(r'^(CHIEF JUSTICE, SUPREME COURT|JUSTICE, SUPREME COURT, PLACE (\d+))( - UNEXPIRED TERM)?$', n)
    if m:
        seat = 'Chief Justice' if m.group(1).startswith('CHIEF') else f'Place {m.group(2)}'
        return ('statewide', f'Supreme Court, {seat}' + (' (unexpired term)' if m.group(3) else ''), '', None)
    for pat, level, label, plan in DISTRICT:
        m = re.match(pat, n)
        if m:
            return (level, label, plan, int(m.group(1)))
    return None


def election_id(date):
    d = datetime.date.fromisoformat(date)
    info = unpack(get('electionConstants')['upload'])['electionInfo'].get(str(d.year), {})
    month = d.strftime('%B').upper()
    for et in ('GE', 'G'):
        for eid, e in (info.get(et) or {}).items():
            if month in e['N'] and 'GENERAL' in e['N']:
                return eid
    raise RuntimeError(f'no state general election listed for {date}')


def collect(date, county_fips):
    """(rows, info). county_fips maps normalized county name -> 5-digit FIPS."""
    year = int(date[:4])
    eid = election_id(date)
    el = {k: unpack(v) for k, v in get(f'election/{eid}').items() if k != 'Version'}
    counties = get(f'election/countyInfo/{eid}')
    if isinstance(counties, dict) and 'upload' in counties:
        counties = unpack(counties['upload'])
    races = {}
    for part in ('Federal', 'StateWide', 'Districted'):
        for r in (el.get(part) or {}).get('Races') or []:
            races[r['id']] = r
    # precincts reporting per race, summed over counties
    rep = {}
    for c in counties.values():
        for oid, rr in (c.get('Races') or {}).items():
            a = rep.setdefault(int(oid), [0, 0])
            a[0] += rr.get('PR') or 0; a[1] += rr.get('TP') or 0
    rows, problems = [], []
    for rid, r in races.items():
        o = office_of(r['N'])
        if not o:
            continue
        level, office, plan, district = o
        total = sum(c.get('V') or 0 for c in r['Candidates'])
        pr, tp = rep.get(rid, (0, 0))
        status = 'final' if tp and pr >= tp and total else 'counting' if total else 'pending'
        race_id = f'{year} {office}'
        if level == 'statewide':
            for c in counties.values():
                f = county_fips.get(norm(c['N']))
                rr = (c.get('Races') or {}).get(str(rid))
                if not f or not rr:
                    if not f: problems.append(f'unknown county {c["N"]}')
                    continue
                for cand in rr['C'].values():
                    rows.append({'level': 'statewide', 'race': race_id, 'year': year, 'office': office, 'plan': '', 'unit': f, 'unit_name': c['N'].title(),
                                 'candidate': nice(cand['N']), 'party': PARTY.get(cand.get('P') or '', 'O'), 'votes': cand.get('V') or 0, 'status': status,
                                 'reporting': rr.get('PR') or 0, 'reporting_total': rr.get('TP') or ''})  # precinct counts, so they add up statewide
        else:
            for cand in r['Candidates']:
                rows.append({'level': level, 'race': race_id, 'year': year, 'office': office, 'plan': plan, 'unit': district, 'unit_name': '',
                             'candidate': nice(cand['N']), 'party': PARTY.get(cand.get('P') or '', 'O'), 'votes': cand.get('V') or 0, 'status': status,
                             'reporting': pr, 'reporting_total': tp})
    home = el.get('Home') or {}
    return rows, {'election_id': eid, 'updated': home.get('LastUpdatedTime'), 'counties_reporting': home.get('CountiesReporting'), 'problems': sorted(set(problems))[:10]}


if __name__ == '__main__':
    import sys, collections, os
    fips = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tx_county_fips.json')))
    rows, info = collect(sys.argv[1] if len(sys.argv) > 1 else '2026-11-03', fips)
    print(info)
    print(collections.Counter((r['level'], r['office'] if r['level'] == 'statewide' else '') for r in {(r['level'], r['race'], r['unit']): r for r in rows}.values()))
    for lv in ('house', 'senate', 'ushouse', 'sboe'):
        print(lv, len({r['unit'] for r in rows if r['level'] == lv}), 'districts')
