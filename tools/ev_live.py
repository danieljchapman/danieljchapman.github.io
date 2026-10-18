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
        for c in day['turnout_by_county']:
            f = fips.get(norm(c['name']))
            if not f:
                problems.append('unknown county ' + c['name'])
                continue
            r = {'registered': c.get('registered_voters') or 0, 'in_person_day': c.get('in_person_votes_on_date') or 0,
                 'in_person': c.get('total_in_person_votes_for_election') or 0, 'mail': c.get('total_mail_votes_for_election') or 0}
            for k in tot:
                tot[k] += r[k]
            rows.append({'year': 2026, 'date': d.isoformat(), 'ev_day': (d - FIRST_IN_PERSON).days + 1, 'unit': f, **r})
        rows.append({'year': 2026, 'date': d.isoformat(), 'ev_day': (d - FIRST_IN_PERSON).days + 1, 'unit': 'TX', **tot})
        last = (d.isoformat(), tot, day.get('date_updated'))
    if not rows:
        raise SystemExit('no early-voting data posted yet')
    import csv
    with open(os.path.join(out_dir, 'ev_2026.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    status = {'updated_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'latest_date': last[0],
              'latest_ev_day': (datetime.date.fromisoformat(last[0]) - FIRST_IN_PERSON).days + 1, 'state_updated': last[2],
              'total_early': last[1]['in_person'] + last[1]['mail'], 'source': 'Texas Secretary of State early-voting turnout, unofficial',
              'problems': sorted(set(problems))[:10]}
    json.dump([status], open(os.path.join(out_dir, 'ev_status.json'), 'w'), indent=1)
    print(json.dumps(status))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'data')
