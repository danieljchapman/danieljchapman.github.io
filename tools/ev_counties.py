"""Daily early-vote totals posted by large counties themselves, used where the state's file lags.

Each reader returns {date (YYYY-MM-DD): {'in_person_day': n, 'mail_day': m or None}} for days the county has posted.
Only summary reports are read; voter-by-voter rosters are never downloaded.
  Harris  - County Clerk "Daily Record of Early Voting Check-ins" (EVPA_unofficial.pdf): per-day check-ins and mail ballots received
  Tarrant - Elections "Early Voting In Person Totals" and "Absentee Voting Totals" PDFs
  Travis  - County Clerk "Unofficial Early Voting In Person and By Mail Totals" (G26-Daily-Totals.pdf)
  Collin  - Elections "Check-in Summary by Location" PDFs on the rosters page (one per posted day; in person only)
  El Paso - Elections "Early Voting Statistics" and "Ballot by Mail Statistics" PDFs linked from the current-election page
  Dallas  - Elections "Early Voting Turnout By Date and Location" spreadsheet (in person only)
"""
import datetime, re, subprocess, sys

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
YEAR = 2026
MON = {m: i for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}


def fetch(url):
    p = subprocess.run(['curl', '-s', '-L', '--compressed', '-m', '90', '-A', UA, '-w', '\n%{http_code}', url], capture_output=True)
    body, _, code = p.stdout.rpartition(b'\n')
    if code != b'200':
        raise RuntimeError(f'{url}: HTTP {code.decode()}')
    return body


def pdf_text(url):
    p = subprocess.run(['pdftotext', '-layout', '-', '-'], input=fetch(url), capture_output=True)
    return p.stdout.decode('utf-8', 'replace')


def nums(s):
    return [int(x.replace(',', '')) for x in re.findall(r'\d[\d,]*', s)]


def iso(m, d):
    return datetime.date(YEAR, m, d).isoformat()


def harris():
    t = pdf_text('https://appfiles.harrisvotes.com/harrisvotes/prd/docs/Uploads/EVPA_unofficial.pdf')
    head = next(l for l in t.splitlines() if re.search(r'\d{1,2}-Oct', l))
    dates = [iso(MON[mo.lower()], int(d)) for d, mo in re.findall(r'(\d{1,2})-(Oct|Nov)', head)]
    tot = nums(next(l for l in t.splitlines() if 'Total Early Voters' in l))[:len(dates)]
    mail = nums(next(l for l in t.splitlines() if 'Mail Ballots Received' in l))[:len(dates)]
    return {d: {'in_person_day': tv - mv, 'mail_day': mv} for d, tv, mv in zip(dates, tot, mail) if tv > 0}


def _tarrant_row(text, label_line):
    lines = text.splitlines()
    head = next(l for l in lines if re.search(r'Total\s+\d{1,2}/\d{1,2}', l))
    dates = [iso(int(m), int(d)) for m, d in re.findall(r'(\d{1,2})/(\d{1,2})', head)]
    row = nums(next(l for l in lines if re.match(label_line, l) and '/' not in l))  # skip the date header row
    return dates, row[1:1 + len(dates)]  # first number is the total


def tarrant():
    base = 'https://www.tarrantcountytx.gov/content/dam/main/elections/2026/1126/ev_reports/'
    t = pdf_text(base + 'Early_Voting_Daily_Totals.pdf')
    dates, vals = _tarrant_row(t, r'^Total\s+\d')
    out = {d: {'in_person_day': v, 'mail_day': None} for d, v in zip(dates, vals) if v > 0}
    a = pdf_text(base + 'ABS_Daily_Totals.pdf')
    sec = a[a.index('Ballots Received'):]
    dates_m, vals_m = _tarrant_row(sec, r'^\s*Total\s+\d')
    mail = dict(zip(dates_m, vals_m))
    # mail received before in-person voting is folded into the first in-person day
    first = min(out) if out else None
    for d, v in mail.items():
        k = d if d in out else first if first and d < first else None
        if k:
            out[k]['mail_day'] = (out[k]['mail_day'] or 0) + v
    return out


def travis():
    t = pdf_text('https://votetravis.gov/wp-content/uploads/G26-Daily-Totals.pdf')
    head = next(l for l in t.splitlines() if re.search(r'\d{1,2}-Oct', l))
    dates = [iso(MON[mo.lower()], int(d)) for d, mo in re.findall(r'(\d{1,2})-(Oct|Nov)', head)]
    ip = nums(next(l for l in t.splitlines() if 'Early Voting Location Voters' in l))[:len(dates)]
    lim = nums(next((l for l in t.splitlines() if 'Limited Ballots' in l), '')) or [0] * len(dates)
    mail = nums(next(l for l in t.splitlines() if 'Mail Ballots Received' in l))[:len(dates)]
    return {d: {'in_person_day': a + b, 'mail_day': m} for d, a, b, m in zip(dates, ip, lim[:len(dates)], mail) if a > 0}


def collin():
    page = fetch('https://www.collincountytx.gov/elections/rosters').decode('utf-8', 'replace')
    links = sorted(set(re.findall(r'href="(/docs/default-source/elections/election-rosters/totals-by-site-through-[^"]+?\.pdf[^"]*)"', page)))
    per_day, cum = {}, {}
    for l in links:
        t = pdf_text('https://www.collincountytx.gov' + l.replace('&amp;', '&'))
        m = re.search(r'Date Range:\s*(\d\d)/(\d\d)/(\d{4})\s*-\s*(\d\d)/(\d\d)/(\d{4})', t)
        tot = re.search(r'^Total\s+[\d,]+\s+[\d,]+\s+([\d,]+)\s*$', t, re.M) or re.search(r'^Total\s.*?([\d,]+)\s*$', t, re.M)
        if not m or not tot:
            continue
        a, b = iso(int(m.group(1)), int(m.group(2))), iso(int(m.group(4)), int(m.group(5)))
        n = int(tot.group(1).replace(',', ''))
        (per_day if a == b else cum)[(a, b)] = n
    out = {b: {'in_person_day': n, 'mail_day': None} for (a, b), n in per_day.items()}
    # cumulative reports (first day through a later day) fill any day not posted on its own
    for (a, b), n in sorted(cum.items()):
        known = sum(v['in_person_day'] for d, v in out.items() if a <= d < b)
        if b not in out and n > known:
            out[b] = {'in_person_day': n - known, 'mail_day': None}
    return out


def _date_row(text, label):
    """Per-day values from a PDF table whose header has MM/DD/YY dates and a row starting with `label`."""
    lines = text.splitlines()
    head = next(l for l in lines if re.search(r'\d{1,2}/\d{1,2}/\d\d', l))
    dates = [iso(int(m), int(d)) for m, d, _ in re.findall(r'(\d{1,2})/(\d{1,2})/(\d\d)', head)]
    row = nums(next(l for l in lines if l.strip().startswith(label)).split(label, 1)[1] if True else '')
    return dates, row


def el_paso_parse(stats, mail):
    dates, vals = _date_row(stats, 'Daily Totals')
    vals = vals[:len(dates)] if len(vals) > len(dates) else vals
    out = {d: {'in_person_day': v, 'mail_day': None} for d, v in zip(dates, vals) if v > 0}
    if mail and out:
        mdates, mvals = _date_row(mail, 'Boletas Regresadas')
        for d, v in zip(mdates, mvals):
            k = d if d in out else min(out) if d < min(out) else None
            if k:
                out[k]['mail_day'] = (out[k]['mail_day'] or 0) + v
    return out


def el_paso():
    page = fetch('https://epcountyvotestx.gov/voter-information/current-election').decode('utf-8', 'replace')
    links = re.findall(r'(https://ep-county-elections-production[^"\s]*?Day_(\d+)_Early_Voting_Statistics\.pdf[^"\s]*)', page)
    if not links:
        return {}
    latest = max(links, key=lambda x: int(x[1]))  # (url, day number)
    day = latest[1]
    mail_url = next((m for m in re.findall(r'(https://ep-county-elections-production[^"\s]*?Day_(\d+)_Ballot_by_Mail_Statistics\.pdf[^"\s]*)', page) if m[1] == day), None)
    stats = pdf_text(latest[0].replace('&amp;', '&'))
    mail = pdf_text(mail_url[0].replace('&amp;', '&')) if mail_url else ''
    return el_paso_parse(stats, mail)


def dallas_parse(rows):
    head = next(r for r in rows if r and r[0] == 'Vote Center Name')
    tot = next(r for r in rows if r and r[0] == 'Daily Unofficial Total')
    out = {}
    for h, v in zip(head, tot):
        if hasattr(h, 'strftime') or (isinstance(h, str) and re.match(r'\d{4}-\d\d-\d\d', h)):
            d = h.strftime('%Y-%m-%d') if hasattr(h, 'strftime') else h[:10]
            if v and int(float(v)) > 0:
                out[d] = {'in_person_day': int(float(v)), 'mail_day': None}
    return out


def dallas():
    import io
    import openpyxl
    page = fetch('https://www.dallascountyvotes.org/election-results/historical/november-3-2026-general-and-joint-election/').decode('utf-8', 'replace')
    links = re.findall(r'(https://www\.dallascountyvotes\.org/wp-content/uploads/[^"]*Turnout-By-Date-and-Location[^"]*?_(\d\d)\.(\d\d)\.(\d\d)\.xlsx)', page)
    if not links:
        return {}
    url = max(links, key=lambda x: (x[3], x[1], x[2]))[0]
    wb = openpyxl.load_workbook(io.BytesIO(fetch(url)), read_only=True, data_only=True)
    return dallas_parse([list(r) for r in wb.worksheets[0].iter_rows(values_only=True)])


READERS = {'48201': ('Harris County Clerk', harris), '48439': ('Tarrant County Elections', tarrant),
           '48453': ('Travis County Clerk', travis), '48085': ('Collin County Elections', collin),
           '48141': ('El Paso County Elections', el_paso), '48113': ('Dallas County Elections', dallas)}


def collect():
    data, problems = {}, []
    for fips, (name, fn) in READERS.items():
        try:
            days = fn()
            if days:
                data[fips] = {'source': name, 'days': days}
        except Exception as e:
            problems.append(f'{name}: {str(e)[:120]}')
    return data, problems


if __name__ == '__main__':
    d, p = collect()
    for f, v in d.items():
        print(f, v['source'], v['days'])
    print('problems', p, file=sys.stderr)
