#!/usr/bin/env python3
"""Election-night importer for the National page: 2026 U.S. Senate, U.S. House and governor races.

Source: CivicAPI (civicapi.org), whose national records list every race of each kind with its candidates and
votes: United States Senate (race 87528, 35 states), United States House of Representatives (87524, 435
districts), United States Governors (87535, 36 states + territories). Three requests per run.
Writes:
  live_2026.csv     one row per race and candidate
  live_status.json  phase, update time, counts, problems
Usage: python3 us_live.py [--out DIR] [--keep-test]
CivicAPI serves made-up test numbers before Election Day (test_data: true); they're zeroed unless --keep-test.
"""
import argparse, csv, datetime, json, os, re, subprocess, sys, time

API = 'https://civicapi.org/api/v2/race/'
NATIONAL = {'senate': 87528, 'house': 87524, 'governor': 87535}
EXPECT = {'senate': 35, 'house': 435, 'governor': 36}
STATES = set('AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())
SPECIAL = {'FL', 'OH'}   # 2026 Senate specials (Rubio's and Vance's former seats)
PARTY = {'republican': 'R', 'democratic': 'D', 'democrat': 'D', 'libertarian': 'L', 'green': 'G', 'independent': 'I', 'constitution': 'C',
         'write-in': 'W', 'nonpartisan': 'I', 'no party preference': 'I', 'unaffiliated': 'I', 'democratic-farmer-labor': 'D'}
FIELDS = ['level', 'race', 'year', 'state', 'district', 'seat', 'candidate', 'party', 'votes', 'winner', 'unopposed', 'incumbent', 'status',
          'reporting', 'reporting_total']


def get(rid, tries=4):
    last = None
    for i in range(tries):
        p = subprocess.run(['curl', '-sS', '--compressed', '-m', '90', '-w', '\n%{http_code}', API + str(rid)], capture_output=True, text=True)
        body, _, code = p.stdout.rpartition('\n')
        if code == '200':
            return json.loads(body)
        last = f'HTTP {code or "?"} {p.stderr.strip()[:120]}'
        time.sleep(2 + 3 * i)
    raise RuntimeError(f'race {rid}: {last}')


def party(p):
    return PARTY.get(str(p or '').strip().lower(), 'O')


def clean(name):
    name = re.sub(r'\s+', ' ', str(name or '')).strip()
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='.')
    ap.add_argument('--keep-test', action='store_true')
    a = ap.parse_args()
    rows, problems, counts = [], [], {}
    called = counting = total = 0
    test = False
    for level, rid in NATIONAL.items():
        try:
            d = get(rid)
        except RuntimeError as e:
            problems.append(str(e)); continue
        test = test or bool(d.get('test_data'))
        zero = bool(d.get('test_data')) and not a.keep_test
        n = 0
        for key, reg in sorted((d.get('region_results') or {}).items()):
            key = key.lower()
            if level == 'house':
                m = re.match(r'^([a-z]{2})-(al|\d+)$', key)
                if not m:
                    problems.append(f'house: unknown district {key}'); continue
                st, dist = m.group(1).upper(), 0 if m.group(2) == 'al' else int(m.group(2))
                race = f'{st}-{dist:02d}'
            else:
                st, dist = key.upper(), ''
                race = st
            if st not in STATES:
                continue          # territories (Guam governor, etc.)
            n += 1
            cands = [c for c in (reg.get('candidates') or []) if clean(c.get('name'))]
            votes = [0 if zero else int(c.get('votes') or 0) for c in cands]
            won = [bool(c.get('winner')) and not zero for c in cands]
            unopposed = len(cands) == 1
            pr = reg.get('percent_reporting')
            pr = 0 if zero else pr
            if any(won) or unopposed:
                status = 'final'
            elif sum(votes):
                status = 'counting'
            else:
                status = 'pending'
            total += 1
            called += status == 'final'
            counting += status == 'counting'
            seat = 'special' if level == 'senate' and st in SPECIAL else ''
            for c, v, w in zip(cands, votes, won):
                rows.append({'level': level, 'race': race, 'year': 2026, 'state': st, 'district': dist, 'seat': seat, 'candidate': clean(c['name']),
                             'party': party(c.get('party')), 'votes': v, 'winner': int(w or unopposed), 'unopposed': int(unopposed),
                             'incumbent': int(bool(c.get('incumbent'))), 'status': status, 'reporting': '' if pr is None else pr, 'reporting_total': 100})
        counts[level] = n
        if n != EXPECT[level]:
            problems.append(f'{level}: {n} races listed, expected {EXPECT[level]}')
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'live_2026.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    phase = 'pre-election' if not counting and called == sum(1 for r in {(x['level'], x['race']) for x in rows if x['unopposed']}) else \
        'final' if total and called == total else 'counting'
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    status = {'phase': phase, 'updated_at': now, 'source': 'CivicAPI (civicapi.org), unofficial', 'races': total, 'called': called,
              'counting': counting, 'counts': counts, 'test_data_zeroed': test and not a.keep_test, 'problems': problems[:20]}
    json.dump([status], open(os.path.join(a.out, 'live_status.json'), 'w'), indent=1)
    print(json.dumps({k: status[k] for k in ('phase', 'races', 'called', 'counting', 'counts')} | {'rows': len(rows), 'problems': len(problems)}))
    for p in problems[:10]:
        print('problem:', p, file=sys.stderr)


if __name__ == '__main__':
    main()
