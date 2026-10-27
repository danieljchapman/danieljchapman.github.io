"""Parse the House Clerk's 'Statistics of the Presidential and Congressional Election of November 5, 2024'
(pdftotext -layout) into Senate and House candidate rows.
Usage: python3 parse_clerk.py clerk.txt out_dir
Writes clerk_2024.json: [{chamber, state, district, candidate, party, votes}] where fusion-party sublines
(New York, Connecticut) are added to the candidate above, and Blank/Void/Over/Under lines are dropped.
"""
import json, re, sys

STATES = ['ALABAMA', 'ALASKA', 'ARIZONA', 'ARKANSAS', 'CALIFORNIA', 'COLORADO', 'CONNECTICUT', 'DELAWARE', 'FLORIDA', 'GEORGIA', 'HAWAII', 'IDAHO',
          'ILLINOIS', 'INDIANA', 'IOWA', 'KANSAS', 'KENTUCKY', 'LOUISIANA', 'MAINE', 'MARYLAND', 'MASSACHUSETTS', 'MICHIGAN', 'MINNESOTA', 'MISSISSIPPI',
          'MISSOURI', 'MONTANA', 'NEBRASKA', 'NEVADA', 'NEW HAMPSHIRE', 'NEW JERSEY', 'NEW MEXICO', 'NEW YORK', 'NORTH CAROLINA', 'NORTH DAKOTA', 'OHIO',
          'OKLAHOMA', 'OREGON', 'PENNSYLVANIA', 'RHODE ISLAND', 'SOUTH CAROLINA', 'SOUTH DAKOTA', 'TENNESSEE', 'TEXAS', 'UTAH', 'VERMONT', 'VIRGINIA',
          'WASHINGTON', 'WEST VIRGINIA', 'WISCONSIN', 'WYOMING', 'AMERICAN SAMOA', 'DISTRICT OF COLUMBIA', 'GUAM', 'NORTHERN MARIANA ISLANDS',
          'PUERTO RICO', 'VIRGIN ISLANDS']
DROP = re.compile(r'^(continuing ballots|exhausted ballots|blanks?|void|over ?votes?|under ?votes?|blank/void|none of these candidates)\b', re.I)
LINE = re.compile(r'^(\s*)(?:(\d+)\.\s+)?(\S.*?)\s*\.{2,}[\s.]*([\d,]+|\(\d\))\s*$')


def parse(path):
    rows, state, section, district, last = [], None, None, None, None
    lines = open(path, encoding='utf-8').read().splitlines()
    for raw in lines:
        s = raw.strip()
        st = re.sub(r'—Continued$', '', s)
        if st in STATES:
            if st != state:
                state, section, district, last = st, None, None, None
            continue
        if s.startswith('FOR UNITED STATES SENATOR'):
            if section != 'senate' or 'Continued' not in s:
                section, district, last = 'senate', 'UNEXPIRED' if 'UNEXPIRED' in s.upper() else '', None
            continue
        if s.startswith('FOR UNITED STATES REPRESENTATIVE'):
            if section != 'house':
                section, district, last = 'house', None, None
            continue
        if s.startswith('FOR PRESIDENTIAL ELECTORS') or s.startswith('FOR RESIDENT COMMISSIONER') or s.startswith('FOR DELEGATE') or s.startswith('Recapitulation'):
            section, last = None, None
            continue
        if section == 'house' and re.match(r'^AT LARGE$', s):
            district, last = 0, None
            continue
        if section == 'senate' and re.match(r'^\(For (unexpired|the unexpired) term', s, re.I):
            district, last = 'UNEXPIRED', None
            continue
        if section == 'senate' and re.match(r'^\(For (the )?(full )?term', s, re.I):
            district, last = '', None
            continue
        if not section:
            continue
        m = LINE.match(raw)
        if not m:
            continue
        indent, num, label, votes = len(m.group(1)), m.group(2), m.group(3).strip(), (None if m.group(4).startswith('(') else int(m.group(4).replace(',', '')))
        if num:
            district = int(num)
        if DROP.match(label):
            last = None
            continue
        if ',' in label:
            name, party = label.rsplit(',', 1)
            last = {'chamber': section, 'state': state, 'district': district, 'candidate': name.strip(), 'party': party.strip(), 'votes': votes, 'lines': [party.strip()]}
            rows.append(last)
        elif re.match(r'^(write-?ins?|scattering|others?|all others|miscellaneous)\b', label, re.I):
            last = None
            rows.append({'chamber': section, 'state': state, 'district': district, 'candidate': 'Write-ins', 'party': 'Write-in', 'votes': votes, 'lines': ['Write-in']})
        elif last is not None:  # fusion: another party line for the candidate above
            last['votes'] = (last['votes'] or 0) + (votes or 0)
            last['lines'].append(label)
        else:
            print('UNPLACED', state, section, district, repr(s[:90]), file=sys.stderr)
    return rows


if __name__ == '__main__':
    rows = parse(sys.argv[1])
    json.dump(rows, open(sys.argv[2] + '/clerk_2024.json', 'w'), indent=0)
    print(len(rows))
