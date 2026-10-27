#!/usr/bin/env python3
"""Polling averages for the National page: 2026 U.S. Senate, House and governor races, and the generic congressional ballot.

Source: pollresults.org API (New York Times poll data, CC BY 4.0): https://api.pollresults.org/v1.0/politics/results/{senate,house,governor}
Writes us/data/polls.json:
  {updated_at, source, license, since, races: {"senate|NC": {...}, "house|AK-00": {...}, "governor|TX": {...}}, generic: {...}}
  each race: pair [[name, party], [name, party]] (margin = first minus second, in points), polls [{d, s, e, p, n, part, m, w}],
             curve [[date, margin], ...] (LOESS, only with enough polls) or null, final {m, method, n}
Rules (chosen with the site owner, Oct 27, 2026):
  - general-election questions for the Nov 3, 2026 election, fieldwork ending Aug 1 or later
  - likely voters only (polls without a likely-voter result are left out)
  - one result per poll: the likely-voter question that includes both main candidates, the fullest ballot if several
  - repeated polls by one pollster count once per two weeks: weight = 1 / (that pollster's polls in the race within 14 days)
  - partisan-sponsored polls are kept and marked (part = sponsor's party)
  - LOESS curve (local linear, tricube, span 60% of the weighted polls — wider when there are few — at least 21 days each side) when a race has 8+ polls;
    otherwise the final figure is the weighted average of the polls in the last 30 days before the latest poll
  - Alaska's ranked-choice polls: first choices (round 1), comparable with election-night counts
Usage: python3 us_polls.py [--out us/data] [--pages DIR]  (--pages reads saved {office}_pages.json instead of the API)
"""
import argparse, datetime as dt, json, math, os, subprocess, sys, time
from collections import defaultdict

BASE = 'https://api.pollresults.org/v1.0/politics/results/'
SINCE = dt.date(2026, 8, 1)
ELECTION = '2026-11-03'
AT_LARGE = {'AK', 'DE', 'ND', 'SD', 'VT', 'WY'}
PARTY = {'REP': 'R', 'DEM': 'D', 'IND': 'I', 'LIB': 'L', 'GRE': 'G', 'NONE': None}
MIN_CURVE = 8
SPAN = 0.6
MIN_HALF_WIDTH = 21   # days


def fetch(office):
    pages, cursor = [], None
    for _ in range(300):
        url = f'{BASE}{office}?limit=100' + (f'&cursor={cursor}' if cursor else '')
        for attempt in range(4):
            p = subprocess.run(['curl', '-sS', '--compressed', '-m', '60', '-w', '\n%{http_code}', url], capture_output=True, text=True)
            body, _, code = p.stdout.rpartition('\n')
            if code == '200':
                break
            time.sleep(3 + 5 * attempt)
        else:
            raise RuntimeError(f'{office}: HTTP {code} {p.stderr[:200]}')
        d = json.loads(body)
        pages.append(d)
        cursor = d.get('cursor')
        if not cursor or not d.get('results'):
            break
        time.sleep(0.3)
    return pages


def date(s):
    m, d, y = s.split('/')
    return dt.date(2000 + int(y) if len(y) == 2 else int(y), int(m), int(d))


def last(name):
    w = [x for x in name.replace(',', ' ').split() if x.rstrip('.').lower() not in ('jr', 'sr', 'ii', 'iii', 'iv')]
    return (w[-1] if w else name).lower()


def race_key(office, p, q):
    st = p['state']
    if office == 'house':
        if st == 'US':
            return 'generic'
        n = int(q.get('seatNumber') or 0)
        return f'house|{st}-{0 if st in AT_LARGE else n:02d}'
    return f'{office}|{st}'


def answers(q, generic=False):
    """Candidate answers (no undecided etc.), first-round only for ranked-choice polls. In a single race, "Generic Democrat"-style
    answers are skipped (a few district polls ask a generic ballot instead of naming the candidates)."""
    out = []
    for a in q['answers']:
        if a.get('party') == 'NONE':
            continue
        if not generic and str(a.get('candidateName', '')).lower().startswith('generic'):
            continue
        r = a.get('rankedChoiceRound')
        if r is not None and int(r) != 1:
            continue
        if a.get('pct') is None:
            continue
        out.append(a)
    return out


def loess(xs, ys, ws, grid):
    """Local linear regression with tricube weights; the window holds SPAN of the total poll weight (at least MIN_HALF_WIDTH days each side)."""
    out = []
    W = sum(ws)
    span = max(SPAN, min(1.0, 8 / max(W, 1)))   # sparse races: wider window, so a handful of polls can't make the line wiggle
    for g in grid:
        dist = sorted((abs(x - g), w) for x, w in zip(xs, ws))
        acc, h = 0.0, MIN_HALF_WIDTH
        for d_, w in dist:
            acc += w
            if acc >= span * W:
                h = max(MIN_HALF_WIDTH, d_ * 1.0001)
                break
        else:
            h = max(MIN_HALF_WIDTH, dist[-1][0] * 1.0001)
        k = [w * (1 - (abs(x - g) / h) ** 3) ** 3 if abs(x - g) < h else 0.0 for x, w in zip(xs, ws)]
        sk = sum(k)
        if sk <= 0:
            out.append(None); continue
        mx = sum(ki * x for ki, x in zip(k, xs)) / sk
        my = sum(ki * y for ki, y in zip(k, ys)) / sk
        sxx = sum(ki * (x - mx) ** 2 for ki, x in zip(k, xs))
        sxy = sum(ki * (x - mx) * (y - my) for ki, x, y in zip(k, xs, ys))
        b = sxy / sxx if sxx > 1e-9 else 0.0
        out.append(my + b * (g - mx))
    return out


def build(pages_by_office):
    raw = defaultdict(list)     # race -> [(poll, [lv general questions])]
    for office, pages in pages_by_office.items():
        for pg in pages:
            for p in pg.get('results') or []:
                if p.get('cycle') != '2026' or p.get('electionDate') != ELECTION:
                    continue
                if date(p['endDate']) < SINCE:
                    continue
                qs = [q for q in p['questions'] if q.get('stage') == 'general' and q.get('population') == 'lv']
                if not qs:
                    continue
                k = race_key(office, p, qs[0])
                raw[k].append((p, qs))
    races, generic = {}, None
    for k, items in raw.items():
        # main pair: candidates appearing in the most polls of the last 45 days of polling (ties: higher average share)
        latest = max(date(p['endDate']) for p, _ in items)
        seen = defaultdict(lambda: [0, 0.0, None, None])
        for p, qs in items:
            if (latest - date(p['endDate'])).days > 45:
                continue
            ids = set()
            for q in qs:
                for a in answers(q, k == 'generic'):
                    key = a['candidateId'] if k != 'generic' else a['party']
                    if key in ids:
                        continue
                    ids.add(key)
                    s = seen[key]; s[0] += 1; s[1] += a['pct']; s[2] = a['candidateName']; s[3] = PARTY.get(a['party'], 'O')
        top = sorted(seen.items(), key=lambda kv: (-kv[1][0], -kv[1][1] / kv[1][0]))[:2]
        if len(top) < 2:
            continue
        # order the pair: Democrat first when there is one, so margins read D minus R (otherwise the leader first)
        top.sort(key=lambda kv: (kv[1][3] != 'D', kv[1][3] == 'R', -kv[1][1] / kv[1][0]))
        pair = [[v[2] if k != 'generic' else ('Democrats' if v[3] == 'D' else 'Republicans' if v[3] == 'R' else v[2]), v[3]] for _, v in top]
        keys = [kv[0] for kv in top]
        polls = []
        for p, qs in items:
            best = None
            for q in qs:
                got = {}
                for a in answers(q, k == 'generic'):
                    kk = a['candidateId'] if k != 'generic' else a['party']
                    if kk in keys and kk not in got:
                        got[kk] = a['pct']
                if len(got) == 2:
                    n_ans = len(answers(q, k == 'generic'))
                    if best is None or n_ans > best[0]:
                        best = (n_ans, q, got)
            if not best:
                continue
            _, q, got = best
            part = p.get('partisan') or p.get('sponsorCandidateParty') or ''
            polls.append({'s': date(p['startDate']).isoformat(), 'e': date(p['endDate']).isoformat(), 'p': p.get('displayName') or p['pollster'],
                          'n': q.get('sampleSize'), 'part': {'DEM': 'D', 'REP': 'R', 'IND': 'I', 'OTH': 'O'}.get(part, ''),
                          'm': round(got[keys[0]] - got[keys[1]], 1), 'a': round(got[keys[0]], 1), 'b': round(got[keys[1]], 1),
                          'url': p.get('url') or '', 'pid': p['pollsterId'], 'id': p['pollId']})
        # drop exact duplicates (same poll id), sort, weight repeated polling by one pollster
        uniq = {x['id']: x for x in polls}
        polls = sorted(uniq.values(), key=lambda x: x['e'])
        for x in polls:
            e = dt.date.fromisoformat(x['e'])
            same = [y for y in polls if y['pid'] == x['pid'] and abs((dt.date.fromisoformat(y['e']) - e).days) <= 14]
            x['w'] = round(1 / len(same), 3)
        if not polls:
            continue
        xs = [(dt.date.fromisoformat(x['e']) - SINCE).days for x in polls]
        ys = [x['m'] for x in polls]
        ws = [x['w'] for x in polls]
        last_x = max(xs)
        curve, final = None, None
        if len(polls) >= MIN_CURVE:
            grid = list(range(min(xs), last_x + 1))
            vals = loess(xs, ys, ws, grid)
            curve = [[(SINCE + dt.timedelta(days=g)).isoformat(), round(v, 2)] for g, v in zip(grid, vals) if v is not None]
            final = {'m': round(curve[-1][1], 1), 'method': 'loess', 'n': len(polls), 'asof': curve[-1][0]}
        else:
            recent = [(y, w) for x, y, w in zip(xs, ys, ws) if last_x - x <= 30]
            m = sum(y * w for y, w in recent) / sum(w for _, w in recent)
            final = {'m': round(m, 1), 'method': 'average', 'n': len(recent), 'asof': (SINCE + dt.timedelta(days=last_x)).isoformat()}
        for x in polls:
            del x['pid'], x['id']
        rec = {'pair': pair, 'polls': polls, 'curve': curve, 'final': final}
        if k == 'generic':
            generic = rec
        else:
            races[k] = rec
    return races, generic


def ballot_check(races, live_path):
    """Drop races whose poll pair isn't on the 2026 ballot (CivicAPI candidate list in live_2026.csv), matched by last name."""
    import csv, unicodedata
    if not os.path.exists(live_path):
        return []
    def ln(n):
        n = ''.join(c for c in unicodedata.normalize('NFD', n.lower()) if c.isalpha() or c == ' ')
        w = [x for x in n.split() if x not in ('jr', 'sr', 'ii', 'iii', 'iv')]
        return w[-1] if w else ''
    ballot = defaultdict(set)
    for r in csv.DictReader(open(live_path)):
        ballot[f"{r['level']}|{r['race']}"].add(ln(r['candidate']))
    dropped = []
    for k in list(races):
        if any(ln(c[0]) not in ballot.get(k, set()) for c in races[k]['pair']):
            dropped.append(f"{k}: {races[k]['pair']}")
            del races[k]
    return dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='us/data')
    ap.add_argument('--pages', help='read saved {office}_pages.json files from this folder instead of the API')
    a = ap.parse_args()
    pages = {}
    for office in ('senate', 'house', 'governor'):
        pages[office] = json.load(open(os.path.join(a.pages, f'{office}_pages.json'))) if a.pages else fetch(office)
    races, generic = build(pages)
    dropped = ballot_check(races, os.path.join(a.out, 'live_2026.csv'))
    for x in dropped:
        print('not on the ballot, left out:', x, file=sys.stderr)
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    out = {'updated_at': now, 'source': 'New York Times poll data via pollresults.org', 'license': 'CC BY 4.0',
           'since': SINCE.isoformat(), 'rules': 'Likely voters only; general election; fieldwork ending Aug 1, 2026 or later; '
           'repeated polls by one pollster count once per two weeks; LOESS with 8+ polls, otherwise 30-day average.',
           'races': dict(sorted(races.items())), 'generic': generic, 'dropped': dropped}
    os.makedirs(a.out, exist_ok=True)
    json.dump(out, open(os.path.join(a.out, 'polls.json'), 'w'), separators=(',', ':'))
    by = defaultdict(lambda: [0, 0])
    for k, r in races.items():
        by[k.split('|')[0]][0] += 1; by[k.split('|')[0]][1] += r['curve'] is not None
    print(json.dumps({'races': {k: {'with_polls': v[0], 'with_curve': v[1]} for k, v in by.items()},
                      'generic_polls': len(generic['polls']) if generic else 0}))


if __name__ == '__main__':
    main()
