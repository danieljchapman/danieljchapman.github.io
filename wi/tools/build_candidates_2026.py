#!/usr/bin/env python3
"""Wisconsin's Nov. 3, 2026 ballot for the races on the page (Governor, Attorney General, Secretary of State, State Treasurer,
all 99 Assembly seats, the 17 odd-numbered Senate seats), from two Wisconsin Elections Commission files:
  - August 2026 Partisan Primary Summary Results (pdf): each party's nominee is the primary 'Winner' (a SCATTERING winner means
    no nominee; a write-in winner is nominated only with at least as many votes as the signatures the office requires:
    2,000 statewide, 400 Senate, 200 Assembly, Wis. Stat. 8.16(2))
  - Ballot Access Report for the June 9, 2026 Commission meeting (pdf, Appendix B 'Candidates Tracking by Office'):
    independent candidates marked Approve (they skip the primary)
Both are read with pdftotext -layout. Writes candidates_2026.csv: level, office, district, candidate, party, source.
Usage: build_candidates_2026.py PRIMARY_PDF BALLOT_ACCESS_PDF OUT_CSV"""
import csv, re, subprocess, sys, collections

PRIM, ACCESS, OUT = sys.argv[1:4]
STATEWIDE = {'GOVERNOR': 'Governor', 'ATTORNEY GENERAL': 'Attorney General', 'SECRETARY OF STATE': 'Secretary of State', 'STATE TREASURER': 'Treasurer'}
PARTY = {'Republican': 'R', 'Democrat': 'D', 'Democratic': 'D', 'Libertarian': 'L', 'Wisconsin Green': 'G', 'Constitution': 'I', 'Independent': 'I'}
MIN_WRITEIN = {'statewide': 2000, 'senate': 400, 'house': 200}


def text(pdf):
    return subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True).stdout


def office_of(name):
    name = re.sub(r'\s+', ' ', name).strip().rstrip(' -')
    if name in STATEWIDE:
        return 'statewide', STATEWIDE[name], ''
    m = re.match(r'^(REPRESENTATIVE TO THE ASSEMBLY|STATE SENATOR) DISTRICT (\d+)$', name)
    if m:
        return ('house', 'Assembly', int(m.group(2))) if m.group(1).startswith('REP') else ('senate', 'Senate', int(m.group(2)))
    return None


rows, notes = [], []
# --- primary nominees
office, party = None, None
for line in text(PRIM).splitlines():
    m = re.match(r'^\s*Office\s+(.+?)(\s{2,}Total Votes:.*)?$', line)
    if m:
        office = office_of(m.group(1)); continue
    m = re.match(r'^\s*Party:\s+(?:.* - )?(Republican|Democratic|Democrat|Libertarian|Constitution|Wisconsin Green)\b', line)
    if m:
        party = PARTY[m.group(1)]; continue
    m = re.match(r'^\s*Winner\s+([\d,]+)\s+[\d.]+%\s+(.+?)(\s{2,}\S.*)?$', line)
    if m and office:
        votes, name = int(m.group(1).replace(',', '')), re.sub(r'\s+', ' ', m.group(2)).strip()
        if name.upper() == 'SCATTERING':
            continue
        if re.search(r'\(write[- ]?in\)', name, re.I):
            name = re.sub(r'\s*\(write[- ]?in\)', '', name, flags=re.I)
            if votes < MIN_WRITEIN[office[0]]:
                notes.append(f'write-in {name} ({office[1]} {office[2]}, {votes} votes) below the minimum; not a nominee'); continue
            notes.append(f'write-in nominee {name} ({office[1]} {office[2]}, {votes} votes)')
        rows.append({'level': office[0], 'office': office[1], 'district': office[2], 'candidate': name, 'party': party, 'source': 'primary'})
# --- independents approved for the general election
office = None
lines = text(ACCESS).splitlines()
for i, line in enumerate(lines):
    m = re.match(r'^\s*Office\s*:\s+(.+?)(\s{2,}Incumbent:.*)?$', line)
    if m:
        name = m.group(1).strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ''
        if re.fullmatch(r'(DISTRICT )?\d+', nxt):   # the district number (or 'DISTRICT n') wraps to the next line
            name += ' ' + nxt
        office = office_of(name); continue
    m = re.match(r'^\s*(?:\d+\s+)?([A-Z][A-Za-z.\'\- ]+?)\s{2,}Independent\b.*\s(Approve|Deny|Challenged)\s*$', line)
    if m and office:
        if m.group(2) == 'Approve':
            rows.append({'level': office[0], 'office': office[1], 'district': office[2], 'candidate': m.group(1).strip(), 'party': 'I', 'source': 'independent'})
        elif m.group(2) == 'Challenged':
            notes.append(f'challenged independent {m.group(1).strip()} ({office[1]} {office[2]}): not listed')
rows.sort(key=lambda r: (['statewide', 'senate', 'house'].index(r['level']), r['office'], r['district'] or 0, 'DRLGI'.index(r['party'])))
with open(OUT, 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=['level', 'office', 'district', 'candidate', 'party', 'source']); w.writeheader(); w.writerows(rows)
races = {(r['level'], r['office'], r['district']) for r in rows}
print('candidates', len(rows), 'races', len(races), collections.Counter(r['level'] for r in rows), collections.Counter(r['party'] for r in rows))
for n in notes:
    print('note:', n)
