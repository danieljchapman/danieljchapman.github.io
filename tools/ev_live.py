"""2026 early-voting turnout by county from the Texas Secretary of State (goelect.txelections.civixapps.com).

The state's early-voting app reads base64-encoded JSON from an open API:
  /api-ivis-system/api/v1/getFile?type=EVR_ELECTION                         elections and their early-voting dates
  /api-ivis-system/api/v1/getFile?type=EVR_EARLYVOTING&electionId=&electionDate=MM/DD/YYYY
                                                                            county totals for one day (no voter names)
Writes data/ev_2026.csv (year, date, ev_day, unit, registered, in_person_day, in_person, mail) and
data/ev_status.json. ev_day 1 is the first day of in-person early voting; mail ballots counted before it
have ev_day <= 0. Only county summaries are read; the per-voter roster files are never downloaded.
"""
import base64, datetime, json, os, subprocess, sys, unicodedata

API = 'https://goelect.txelections.civixapps.com/api-ivis-system/api/v1/getFile'
ELECTION_NAME = '2026 NOVEMBER GENERAL ELECTION'
FIRST_IN_PERSON = datetime.date(2026, 10, 19)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'


def get(**params):
    args = ['curl', '-s', '--compressed', '-m', '90', '-A', UA, '-G', API, '-w', '\n%{http_code}']
    for k, v in params.items():
        args += ['--data-urlencode', f'{k}={v}']
    for _ in range(3):
        out = subprocess.run(args, capture_output=True).stdout
        body, _, code = out.rpartition(b'\n')
        if code == b'200' and body.strip():
            d = json.loads(body)
            return json.loads(base64.b64decode(d['upload'])) if isinstance(d, dict) and 'upload' in d else d
    return None


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn' and c.isalnum())


def load_cache(path):
    try:
        return json.load(open(path))
    except Exception:
        return {}


def merge_counties(rows, problems, cache_path=None):
    """Use large counties' own daily reports for the days they have posted (the state's file lags or differs)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import ev_counties
        cty, cprob = ev_counties.collect()
        problems += cprob
    except Exception as e:
        problems.append('county reports: ' + str(e)[:120])
        return []
    # Counties sometimes replace a day's file with a running total, so every county number read is kept in a
    # small cache (data/ev_county_cache.json); fresh readings replace cached ones for the same date.
    cache = load_cache(cache_path) if cache_path else {}
    for f, info in cty.items():
        c = cache.setdefault(f, {'source': info['source'], 'days': {}})
        c['source'] = info['source']
        c['days'].update(info['days'])
    if cache_path:
        json.dump(cache, open(cache_path, 'w'), indent=1, sort_keys=True)
    used = set()
    for f, info in cache.items():
        days = sorted(info['days'].items())
        cum_ip, cum_m, run_ip, run_m, has_m = {}, {}, 0, 0, any(v.get('mail_day') is not None for _, v in days)
        info['days'] = {}
        for d, v in days:
            if v.get('in_person_cum') is not None:  # running total: that day's count is the increase
                day = max(0, v['in_person_cum'] - run_ip); run_ip = v['in_person_cum']
            else:
                day = v['in_person_day']; run_ip += day
            run_m += v.get('mail_day') or 0
            cum_ip[d], cum_m[d] = run_ip, run_m
            info['days'][d] = {'in_person_day': day}
        mine = sorted((r for r in rows if r['unit'] == f), key=lambda r: r['date'])
        state_ip = {r['date']: r['in_person'] for r in mine}  # the state's own running totals, before any change
        state_m = {r['date']: r['mail'] for r in mine}
        for r in mine:
            if r['ev_day'] < 1:
                continue
            past = [d for d in cum_ip if d <= r['date']]
            if not past:
                continue
            last = max(past)
            # the county is the original source: for days it has posted, its numbers are used even when the
            # state's differ; after its latest report, add whatever the state has recorded since that day
            ip = cum_ip[last] + max(0, r['in_person'] - state_ip.get(last, r['in_person']))
            if ip != r['in_person']:
                r['in_person'] = ip
                v = info['days'].get(r['date'])
                r['in_person_day'] = v['in_person_day'] if v else max(0, r['in_person_day'])
                r['source'] = 'county'
                used.add(info['source'])
            if has_m:
                m = cum_m[last] + max(0, r['mail'] - state_m.get(last, r['mail']))
                if m != r['mail']:
                    r['mail'] = m
                    r['source'] = 'county'
                    used.add(info['source'])
    # statewide rows are the sum of the counties
    for t in [r for r in rows if r['unit'] == 'TX']:
        same = [r for r in rows if r['date'] == t['date'] and r['unit'] != 'TX']
        for k in ('registered', 'in_person_day', 'in_person', 'mail'):
            t[k] = sum(r[k] for r in same)
    for r in rows:
        r.setdefault('source', 'state')
    return sorted(used)


def main(out_dir):
    here = os.path.dirname(os.path.abspath(__file__))
    fips = json.load(open(os.path.join(here, 'tx_county_fips.json')))
    meta = get(type='EVR_ELECTION')
    el = next(e for e in meta['elections'] if e['election_name'].strip().upper() == ELECTION_NAME)
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-6))).date()  # Central (CST)
    rows, problems, last = [], [], None
    for ed in el['early_voting_dates']:
        d = datetime.datetime.strptime(ed['date'], '%m/%d/%Y').date()
        if d > today:
            continue
        day = get(type='EVR_EARLYVOTING', electionId=el['id'], electionDate=ed['date'])
        if not day or not day.get('turnout_by_county'):
            continue  # not posted yet
        tot = {'registered': 0, 'in_person_day': 0, 'in_person': 0, 'mail': 0}
        day_rows = []
        for c in day['turnout_by_county']:
            f = fips.get(norm(c['name']))
            if not f:
                problems.append('unknown county ' + c['name'])
                continue
            r = {'registered': c.get('registered_voters') or 0, 'in_person_day': c.get('in_person_votes_on_date') or 0,
                 'in_person': c.get('total_in_person_votes_for_election') or 0, 'mail': c.get('total_mail_votes_for_election') or 0}
            for k in tot:
                tot[k] += r[k]
            day_rows.append({'year': 2026, 'date': d.isoformat(), 'ev_day': (d - FIRST_IN_PERSON).days + 1, 'unit': f, **r})
        # The state posts a file for an in-person day before the count starts (Oct 26, 1:38 am: 0 in-person votes
        # statewide, totals copied from the day before). Skip such a day until it has votes.
        if d >= FIRST_IN_PERSON and tot['in_person_day'] == 0:
            continue
        rows.extend(day_rows)
        rows.append({'year': 2026, 'date': d.isoformat(), 'ev_day': (d - FIRST_IN_PERSON).days + 1, 'unit': 'TX', **tot})
        last = (d.isoformat(), tot, day.get('date_updated'))
    if not rows:
        raise SystemExit('no early-voting data posted yet')
    county_sources = merge_counties(rows, problems, os.path.join(out_dir, 'ev_county_cache.json'))
    import csv
    with open(os.path.join(out_dir, 'ev_2026.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['year', 'date', 'ev_day', 'unit', 'registered', 'in_person_day', 'in_person', 'mail', 'source'])
        w.writeheader()
        w.writerows(rows)
    status = {'updated_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'latest_date': last[0],
              'latest_ev_day': (datetime.date.fromisoformat(last[0]) - FIRST_IN_PERSON).days + 1, 'state_updated': last[2],
              'total_early': next(r['in_person'] + r['mail'] for r in rows if r['unit'] == 'TX' and r['date'] == last[0]), 'source': 'Texas Secretary of State early-voting turnout, unofficial' + ('; county reports for ' + ', '.join(county_sources) if county_sources else ''),
              'county_sources': county_sources,
              'problems': sorted(set(problems))[:10]}
    json.dump([status], open(os.path.join(out_dir, 'ev_status.json'), 'w'), indent=1)
    print(json.dumps(status))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'data')
