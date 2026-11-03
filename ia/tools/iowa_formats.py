"""Readers for the Iowa Secretary of State's results files (used by extract_sources.py).

parse_canvass(path, counties): an official canvass summary converted with `pdftotext -layout` -> [{title, parties, ncol, counties: {county:
    [candidate columns..., write-in, under votes, over votes, total]}, total}] (each county's 'Total' row; parties = the column party codes
    when the header lists them on their own line).
read_export(path): one county's precinct results export (Clarity/SOE; SpreadsheetML .xls or .xlsx) -> {contest title: [(candidate, county total)]}.
"""
import html, re

NUM = re.compile(r'(?<![\w.])\d{1,3}(?:,\d{3})*(?![\w.])')
PCODE = re.compile(r'^(?:[A-Z]{2,4}\s*)+$')

def parse_canvass(path, counties):
    CTY = sorted(counties, key=len, reverse=True)
    lines = open(path).read().split('\n')
    races, cur, county, header = [], None, None, []
    i = 0
    while i < len(lines):
        l = re.sub(r'\s*Page \d+ of \d+\s*$', '', lines[i].rstrip())
        if re.search(r'CANVASS SUMMARY', l, re.I):
            t = lines[i + 1].strip()
            if not cur or cur['title'] != t:
                cur = {'title': t, 'parties': [], 'counties': {}, 'total': None, 'ncol': None, 'header': []}; races.append(cur); header = cur['parties']; county = None
            i += 2; continue
        s = l.strip()
        if cur is None or not s or s == 'IOWA SECRETARY OF STATE':
            i += 1; continue
        name = None
        for c in CTY + ['TOTAL']:
            if s.startswith(c + ' ') or s == c:
                name = c; break
        rest = s[len(name):].strip() if name else s
        if name: county = name
        m = re.match(r'^(Election Day|Absentee|Total)\b(.*)$', rest)
        if m and county:
            nums = [int(x.replace(',', '')) for x in NUM.findall(m.group(2))]
            if m.group(1) == 'Total':
                # 2020 labels the contest total row just 'Total' (no 'TOTAL'): a second Total row for the same county is the contest total
                if county == 'TOTAL' or (not name and county in cur['counties']): cur['total'] = nums
                else: cur['counties'][county] = nums
                if cur['ncol'] is None: cur['ncol'] = len(nums)
        elif not cur['counties'] and not PCODE.match(s):
            cur['header'].append(s)
        elif not cur['counties'] and PCODE.match(s) and s not in ('REP', 'DEM') or (not cur['counties'] and re.fullmatch(r'(?:[A-Z]{2,4}\s+)*[A-Z]{2,4}', s)):
            if not cur['counties']: cur['parties'].extend(s.split())
        i += 1
    return races


def sheets_xml(path):
    s = open(path, encoding='utf-8-sig', errors='replace').read()
    for w in re.findall(r'<s:Worksheet s:Name="([^"]*)">(.*?)</s:Worksheet>', s, re.S):
        rows = []
        for r in re.findall(r'<s:Row[^>]*?(?:/>|>(.*?)</s:Row>)', w[1], re.S):
            row, col = [], 0
            for attrs, body in re.findall(r'<s:Cell([^>]*?)(?:/>|>(.*?)</s:Cell>)', r or '', re.S):
                m = re.search(r's:Index="(\d+)"', attrs)
                if m: col = int(m.group(1)) - 1
                while len(row) < col: row.append(None)
                d = re.search(r'<s:Data[^>]*>(.*?)</s:Data>', body or '', re.S)
                row.append(html.unescape(d.group(1)).strip() if d else None)
                col += 1
                m = re.search(r's:MergeAcross="(\d+)"', attrs)
                if m:
                    for _ in range(int(m.group(1))): row.append(None); col += 1
            rows.append(row)
        yield w[0], rows

def sheets_xlsx(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True)
    for n in wb.sheetnames:
        yield n, [[None if v is None else str(v).strip() for v in r] for r in wb[n].iter_rows(values_only=True)]

def read_export(path):
    out = {}
    it = sheets_xlsx(path) if path.endswith('.xlsx') else sheets_xml(path)
    for name, rows in it:
        if name in ('Table of Contents', 'Registered Voters') or len(rows) < 4: continue
        title = re.sub(r'\s*\(\s*\d+\s*\)\s*$', '', (rows[0][0] or '')).strip()
        names, sub = rows[1], rows[2]
        tot = next((r for r in rows if r and r[0] and r[0].startswith('Total')), None)
        if not tot: continue
        cands = []
        for j, n in enumerate(names):
            if n and j > 0:
                # the candidate's "Total Votes" column: first 'Total Votes' sub-header at or after j
                k = next((k for k in range(j, len(sub)) if sub[k] and sub[k].startswith('Total')), None)
                v = tot[k] if k is not None and k < len(tot) else None
                try: v = int(float(str(v).replace(',', '')))
                except (TypeError, ValueError): v = None
                cands.append((n, v))
        out[title] = cands
    return out


def header_names(race):
    """Candidate names from a simple canvass header ('Sean Hanley, Monica Kurth,' then 'Jonathan Vance'): names followed by a comma have a
    party code (in order); names without one are listed after them. Returns [(name, party code or None)] or None if it doesn't fit."""
    text = ' '.join(re.sub(r'Write-?[Ii]n\s+Under\s*Votes\s+Over\s*Votes\s+Total', ' ', h) for h in race['header'])
    parts = text.split(',')
    named = [re.sub(r'\s+', ' ', x).strip() for x in parts[:-1]]
    rest = [re.sub(r'\s+', ' ', x).strip() for x in re.split(r'\s{2,}', parts[-1]) if x.strip()]
    out = list(zip(named, race['parties'])) + [(n, None) for n in rest]
    return out if len(named) == len(race['parties']) and len(out) == race['ncol'] - 4 and all(n for n, _ in out) else None
