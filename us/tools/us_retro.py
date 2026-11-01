#!/usr/bin/env python3
"""Retro National pages (us/retro/): plain HTML 3.2 for old browsers (an iMac G3 with IE 5, Classilla, early Safari),
styled like 1980s teletext ("Ballotfax"): black screen, the eight teletext colors, numbered pages (P100 Senate block
map, P101 national overview, P110 Senate, P120 House, P130 governors, P150 states, P201-250 states; 2024 in the 600s/700s).

No JavaScript, no CSS, no images: tables, <FONT> colors, a block map made of colored table cells, and each state drawn in blocks. Built from the same files as
the National page, and rebuilt by the election-night workflow after every update (us/tools/fetch_live.sh), so it
is as current as the main page. Pages reload themselves every 2 minutes until every 2026 race is called.

Usage: python3 us/tools/us_retro.py [--data us/data] [--out us/retro]
       python3 us/tools/us_retro.py --ascii   (redraw data/retro_ascii.json from the state shapes; needs numpy + matplotlib)
The ASCII art is drawn once (retro_ascii.py) and saved, so the election-night build needs only the standard library.
Writes: index.html (Senate block map), national.html, senate.html, house.html, governors.html, states.html, st/XX.html, and the same set for 2024
under 2024/. Text is ISO-8859-1 with entities; anything outside Latin-1 is folded to plain ASCII.
"""
import argparse, csv, datetime, html, json, os, re, sys, unicodedata
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LEVELS = ['senate', 'house', 'governor']
LNAME = {'senate': 'U.S. Senate', 'house': 'U.S. House', 'governor': 'Governor'}
PAGE = {'senate': 'senate.html', 'house': 'house.html', 'governor': 'governors.html'}
SIZE = {'senate': 100, 'house': 435, 'governor': 50}
MAJ = {'senate': 51, 'house': 218, 'governor': 26}
PARTY = {'R': 'Republican', 'D': 'Democrat', 'I': 'Independent', 'L': 'Libertarian', 'G': 'Green', 'C': 'Constitution', 'O': 'Other', 'W': 'Write-in'}
PLURAL = {'R': 'Republicans', 'D': 'Democrats', 'I': 'Independents'}
CAUCUS_D = re.compile(r'^(Bern(ie|ard) Sanders|Angus S?\.? ?King|Kyrsten Sinema|Joe Manchin)')
# Teletext look: black screen, the eight teletext colors only. Democrats are cyan (teletext blue is unreadable
# on black, so blue is used only as a background band, and on the map for states with no race).
BLACK, WHITE, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN = '#000000', '#FFFFFF', '#FF0000', '#00FF00', '#FFFF00', '#0000FF', '#FF00FF', '#00FFFF'
COL = {'R': RED, 'D': CYAN, 'I': MAGENTA, 'L': YELLOW, 'G': GREEN}
GREY = YELLOW            # secondary text ("not counted yet", "no polls"): teletext has no grey
FACE = 'Courier New,Courier'
REFRESH = 120
SMALL_NOTE = ['VT', 'NH', 'MA', 'RI', 'CT', 'NJ', 'DE', 'MD', 'HI']
# teletext page numbers; 2024 pages are the same set in the 600s, state pages 201-250 (2026) / 701-750 (2024)
PNO = {'front': 100, 'national': 101, 'senate': 110, 'house': 120, 'governor': 130, 'states': 150}
FILES = {'front': 'index.html', 'national': 'national.html', 'senate': 'senate.html', 'house': 'house.html', 'governor': 'governors.html', 'states': 'states.html'}
MAP_W, MAP_H = 8, 12     # one teletext block on the map, in pixels


# ---------- text ----------
def h(s):
    """HTML-escape for an ISO-8859-1 page: Latin-1 letters as entities, everything else folded to ASCII."""
    s = str(s).replace('–', '-').replace('—', '--').replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    out = []
    for ch in html.escape(s, quote=False).replace('"', '&quot;'):
        o = ord(ch)
        if o < 128:
            out.append(ch)
        elif o < 256:
            out.append(f'&#{o};')
        else:
            out.append(unicodedata.normalize('NFKD', ch).encode('ascii', 'ignore').decode() or '?')
    return ''.join(out)


def num(n):
    return f'{n:,}'


def pct(x):
    return '' if x is None else f'{x * 100:.1f}%'


def font(text, color, bold=False):
    t = f'<B>{text}</B>' if bold else text
    return f'<FONT COLOR="{color}">{t}</FONT>'


def side(p):
    return p if p in ('R', 'D') else 'I'


def pcol(p):
    return COL.get(p, WHITE)


def et(iso):
    d = datetime.datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(ZoneInfo('America/New_York'))
    return d.strftime('%a %b ') + str(d.day) + ', ' + d.strftime('%I:%M %p').lstrip('0') + ' ET'


# ---------- model (same rules as us/js/us.js) ----------
def caucus(party, name):
    return 'D' if party == 'I' and CAUCUS_D.match(name or '') else party


def holder_caucus(hd):
    return None if not hd else ('D' if hd['party'] == 'I' else hd['party'])


def seat_of(S, level, year, race):
    y = str(year)
    if level == 'house':
        return S['house'].get(y, {}).get(race['key'])
    if level == 'governor':
        return S['governor'].get(y, {}).get(race['state'])
    up = [s for s in S['senate'].get(y, {}).get(race['state'], []) if s['up']]
    if len(up) < 2:
        return up[0] if up else None
    if race['seat'] == 'special':
        return next((s for s in up if s['class'] == 2), None)
    return next((s for s in up if s['class'] != 2), up[0])


def build(level, year, results, live, S):
    rows = [r for r in results if r['level'] == level and r['year'] == '2024'] if year == 2024 else [r for r in live if r['level'] == level]
    by = {}
    for r in rows:
        if level == 'house':
            key = f"{r['state']}-{int(r['district']):02d}"
        else:
            key = r['state'] + ('-S' if r.get('seat') == 'special' and year == 2024 else '')
        by.setdefault(key, {'key': key, 'state': r['state'], 'district': int(r['district']) if level == 'house' else None, 'seat': r.get('seat', ''), 'rows': []})['rows'].append(r)
    races = []
    for race in by.values():
        cands = [{'name': r['candidate'], 'party': r['party'], 'votes': int(float(r['votes'] or 0)), 'winner': r['winner'] == '1',
                  'unopposed': r['unopposed'] == '1', 'incumbent': r.get('incumbent') == '1'} for r in race['rows']]
        total = sum(c['votes'] for c in cands)
        for c in cands:
            c['share'] = c['votes'] / total if total else None
        cands.sort(key=lambda c: (-c['votes'], -c['winner']))
        status = 'final' if year == 2024 else race['rows'][0]['status']
        win = next((c for c in cands if c['winner']), None) or (cands[0] if year == 2024 and cands else None)
        lead = cands[0] if total else None
        top = win or lead
        margin = (cands[0]['votes'] - cands[1]['votes']) / total if total and len(cands) > 1 else None
        hd = seat_of(S, level, year, race)
        redrawn = level == 'house' and race['state'] in S['redrawn'].get(str(year), [])
        wc = caucus(top['party'], top['name']) if top else None
        hc = holder_caucus(hd)
        rep = race['rows'][0].get('reporting', '')
        name = S['names'].get(race['state'], race['state'])
        if level == 'house':
            d = race['district']
            label, short = f"{name} {'at-large' if d == 0 else d}", f"{race['state']}-{'AL' if d == 0 else d}"
        else:
            sp = race['seat'] == 'special'
            label, short = name + (' (special)' if sp else ''), race['state'] + (' special' if sp else '')
        race.update(level=level, year=year, cands=cands, total=total, status=status, win=win, lead=lead, top=top, margin=margin, holder=hd,
                    redrawn=redrawn, wc=wc, hc=hc, flip=bool(win and hd and not redrawn and wc != hc),
                    lead_flip=bool(not win and lead and hd and not redrawn and wc != hc), unopposed=any(c['unopposed'] for c in cands),
                    reporting=None if rep in ('', None) else float(rep), label=label, short=short)
        races.append(race)
    races.sort(key=lambda r: (r['state'], r['district'] or 0, r['seat'] or ''))
    return races


def tally(level, year, races, S):
    z = lambda: {'R': 0, 'D': 0, 'I': 0}
    won, lead, not_up, before, fto, ffrom = z(), z(), z(), z(), z(), z()
    und = 0
    for r in races:
        if r['win']:
            won[side(r['wc'])] += 1
            if r['flip']:
                fto[side(r['wc'])] += 1; ffrom[side(r['hc'])] += 1
        else:
            und += 1
            if r['lead'] and r['total']:
                lead[side(r['wc'])] += 1
    y = str(year)
    if level == 'senate':
        for lst in S['senate'].get(y, {}).values():
            for s in lst:
                before[side(holder_caucus(s))] += 1
                if not s['up']:
                    not_up[side(holder_caucus(s))] += 1
    elif level == 'governor':
        for g in S['governor'].get(y, {}).values():
            before[side(g['party'])] += 1
            if not g['up']:
                not_up[side(g['party'])] += 1
    else:
        for hd in S['house'].get(y, {}).values():
            before[side(hd['party'])] += 1
    total = {p: won[p] + not_up[p] for p in won}
    return dict(won=won, lead=lead, not_up=not_up, total=total, undecided=und, flips_to=fto, flips_from=ffrom, before=before, n=len(races))


def poll_rec(polls, level, r):
    return (polls or {}).get('races', {}).get(f"{level}|{r['key']}") if polls else None


def last_name(n):
    return re.sub(r',?\s+(Jr|Sr|II|III|IV)\.?$', '', str(n), flags=re.I).strip().split()[-1]


def pair_label(pair, m):
    if m is None:
        return '-'
    if abs(m) < 0.05:
        return 'Tied'
    lead = pair[0] if m >= 0 else pair[1]
    dr = {x[1] for x in pair} == {'D', 'R'}
    return f"{lead[1]}+{abs(m):.1f}" if dr else f"{last_name(lead[0])} +{abs(m):.1f}"


def margin_txt(r):
    if not r['top']:
        return '-'
    if r['unopposed']:
        return 'Unopposed'
    if r['margin'] is None:
        return '-'
    p = r['top']['party']
    return f"{p if p in ('R', 'D', 'I') else 'O'}+{r['margin'] * 100:.1f}"


# ---------- page pieces ----------
def pno(kind, year):
    return PNO[kind] + (500 if year == 2024 else 0)


def clock(status):
    iso = (status or {}).get('updated_at')
    d = datetime.datetime.fromisoformat(iso.replace('Z', '+00:00')) if iso else datetime.datetime.now(datetime.timezone.utc)
    d = d.astimezone(ZoneInfo('America/New_York'))
    return d.strftime('%a %d %b'), d.strftime('%H:%M')


# A ticked ballot going into a ballot box, in teletext blocks (Y ballot, K black, W box, B stripe). 14 x 10 blocks of 7 x 12 px.
BALLOT_ICON = ['....YYYYYY....',
               '....YYYYYK....',
               '....YYYYKY....',
               '....YKYKYY....',
               '....YYKYYY....',
               'WWWKYYYYYYKWWW',
               'WWWWWWWWWWWWWW',
               'WWBBBBBBBBBBWW',
               'WWWWWWWWWWWWWW',
               '.WW........WW.']
ICON_COL = {'Y': YELLOW, 'W': WHITE, 'K': BLACK, 'B': BLUE, '.': BLACK}


def icon(rows=BALLOT_ICON, w=7, hgt=12):
    """A block-graphics picture on a black panel (runs of one color merged into one cell)."""
    n = len(rows[0])
    trs = ['<TR>' + ''.join(f'<TD WIDTH="{w}"></TD>' for _ in range(n)) + '</TR>']
    for row in rows:
        cells, i = [], 0
        while i < n:
            j = i
            while j < n and ICON_COL[row[j]] == ICON_COL[row[i]]:
                j += 1
            cells.append(f'<TD BGCOLOR="{ICON_COL[row[i]]}"{f" COLSPAN={j - i}" if j - i > 1 else ""} HEIGHT="{hgt}"><FONT SIZE="1">&nbsp;</FONT></TD>')
            i = j
        trs.append('<TR>' + ''.join(cells) + '</TR>')
    return f'<TABLE BORDER="0" CELLPADDING="0" CELLSPACING="0" BGCOLOR="{BLACK}" WIDTH="{n * w}">' + ''.join(trs) + '</TABLE>'


def strip(n=48):
    """A row of separated blocks in the teletext colors, like the test-card bars."""
    cyc = [RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE]
    cells = ''.join(f'<TD BGCOLOR="{cyc[i % len(cyc)]}" HEIGHT="6"><FONT SIZE="1">&nbsp;</FONT></TD>' for i in range(n))
    return f'<TABLE WIDTH="100%" BORDER="0" CELLPADDING="0" CELLSPACING="3" BGCOLOR="{BLACK}"><TR>{cells}</TR></TABLE>\n'


def band(text, bg, fg, right=''):
    """The teletext title screen: ballot-box icon on a black panel, the service name, a big title, the year,
    then a strip of colored blocks."""
    return (f'<TABLE WIDTH="100%" CELLPADDING="0" CELLSPACING="0" BORDER="0" BGCOLOR="{bg}"><TR>'
            f'<TD BGCOLOR="{bg}" WIDTH="130" VALIGN="MIDDLE"><TABLE BORDER="0" CELLPADDING="6" CELLSPACING="8" BGCOLOR="{bg}"><TR><TD BGCOLOR="{BLACK}">{icon()}</TD></TR></TABLE></TD>'
            f'<TD BGCOLOR="{bg}" VALIGN="MIDDLE"><FONT FACE="{FACE}" SIZE="3" COLOR="{fg}"><B>BALLOTFAX &nbsp;&middot;&nbsp; U.S. ELECTIONS</B></FONT><BR>'
            f'<FONT FACE="{FACE}" SIZE="7" COLOR="{fg}"><B>{text}</B></FONT></TD>'
            f'<TD BGCOLOR="{bg}" ALIGN="RIGHT" VALIGN="MIDDLE"><TABLE BORDER="0" CELLPADDING="6" CELLSPACING="0"><TR><TD BGCOLOR="{BLACK}">'
            f'<FONT FACE="{FACE}" SIZE="6" COLOR="{YELLOW}"><B>{right}</B></FONT></TD></TR></TABLE></TD><TD BGCOLOR="{bg}" WIDTH="8"></TD>'
            f'</TR></TABLE>\n' + strip())


def page(title, body, depth, year, status, refresh, kind, band_text, band_bg, band_fg, num=None):
    up = '../' * depth
    yr = '' if year == 2026 else '2024/'
    n = num or pno(kind, year)
    link = lambda k, label: f'<FONT COLOR="{YELLOW}">{pno(k, year)}</FONT> <A HREF="{up}{yr}{FILES[k]}">{label}</A>'
    other = (f'<FONT COLOR="{YELLOW}">600</FONT> <A HREF="{up}2024/index.html">2024 results</A>' if year == 2026
             else f'<FONT COLOR="{YELLOW}">100</FONT> <A HREF="{up}index.html">2026 results</A>')
    nav = ' &nbsp; '.join([link('front', 'Map'), link('national', 'National'), link('senate', 'Senate'), link('house', 'House'),
                           link('governor', 'Governors'), link('states', 'States'), other])
    meta = f'<META HTTP-EQUIV="Refresh" CONTENT="{REFRESH}">\n' if refresh else ''
    day, hm = clock(status)
    live = ''
    if year == 2026 and status:
        if status['phase'] == 'pre-election':
            msg = f'<FONT COLOR="{YELLOW}">ELECTION DAY TUESDAY 3 NOVEMBER.</FONT> Results from 6pm ET as polls close, updated every few minutes.'
        elif status['phase'] == 'counting':
            msg = f"<FONT COLOR=\"{YELLOW}\"><B>COUNTING</B></FONT> &nbsp; {status['called']} of {status['races']} races called"
        else:
            msg = f"All {status['races']} races called. Unofficial until certified."
        live = (f'<TABLE WIDTH="100%" CELLPADDING="4" CELLSPACING="0" BORDER="0"><TR><TD BGCOLOR="{BLUE}"><FONT FACE="{FACE}" SIZE="2" COLOR="{WHITE}">{msg}'
                f'<BR>Last update {h(et(status["updated_at"]))}.{" Page reloads every 2 minutes." if refresh else ""}</FONT></TD></TR></TABLE><BR>\n')
    fast = [('senate', RED, 'Senate'), ('house', GREEN, 'House'), ('governor', YELLOW, 'Governors')]
    fcells = ''.join(f'<TD WIDTH="25%"><A HREF="{up}{yr}{FILES[k]}"><FONT COLOR="{c}"><B>{t}</B></FONT></A></TD>' for k, c, t in fast)
    fcells += (f'<TD WIDTH="25%"><A HREF="{up}{"2024/index.html" if year == 2026 else "index.html"}"><FONT COLOR="{CYAN}"><B>{"2024" if year == 2026 else "2026"}</B></FONT></A></TD>')
    return f"""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<HTML>
<HEAD>
<TITLE>{h(title)}</TITLE>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=iso-8859-1">
{meta}</HEAD>
<BODY BGCOLOR="{BLACK}" TEXT="{WHITE}" LINK="{CYAN}" VLINK="{CYAN}" ALINK="{YELLOW}">
<FONT FACE="{FACE}">
<TABLE WIDTH="100%" CELLPADDING="2" CELLSPACING="0" BORDER="0"><TR>
<TD><FONT FACE="{FACE}" SIZE="4">P{n}</FONT></TD><TD><FONT FACE="{FACE}" SIZE="4" COLOR="{YELLOW}"><B>BALLOTFAX {n}</B></FONT></TD>
<TD><FONT FACE="{FACE}" SIZE="4">{day}</FONT></TD><TD ALIGN="RIGHT"><FONT FACE="{FACE}" SIZE="4" COLOR="{YELLOW}">{hm}</FONT></TD>
</TR></TABLE>
{band(band_text, band_bg, band_fg, str(year))}<FONT FACE="{FACE}" SIZE="2">{nav}</FONT><BR><BR>
{live}{body}
<BR>
<TABLE WIDTH="100%" CELLPADDING="4" CELLSPACING="0" BORDER="0"><TR>{fcells}</TR></TABLE>
<FONT FACE="{FACE}" SIZE="1" COLOR="{WHITE}">{source_line(year, status)}<BR>
Teletext-style plain-HTML edition for older computers: no scripts, no images. Times are Eastern. The full interactive page is at
<A HREF="{up}../index.html?year={year}">danieljchapman.github.io/us/</A> (needs a modern browser).</FONT>
</FONT>
</BODY>
</HTML>
"""


def source_line(year, status):
    if year == 2024:
        return ('Sources: Clerk of the U.S. House, official 2024 returns (Senate and House); state certified results via Wikipedia (governors). '
                'Seat holders: unitedstates/congress-legislators.')
    src = h((status or {}).get('source') or 'CivicAPI (civicapi.org), unofficial')
    return f'Source: {src}. Races are called when CivicAPI marks a winner. Polling averages: The New York Times poll data (CC BY 4.0), via pollresults.org; averages computed for this site.'


def h2(text):
    """Section heading: yellow on a blue bar."""
    return (f'<BR><TABLE WIDTH="100%" CELLPADDING="3" CELLSPACING="0" BORDER="0"><TR><TD BGCOLOR="{BLUE}"><FONT FACE="{FACE}" SIZE="3" COLOR="{YELLOW}">'
            f'<B>{text}</B></FONT></TD></TR></TABLE>\n')


def block(ring, fill, w, hgt):
    """One mosaic block: a solid square (ring == fill) or an outline (fill black)."""
    return (f'<TD BGCOLOR="{ring}"><TABLE BORDER="0" CELLPADDING="0" CELLSPACING="0" WIDTH="{w}" HEIGHT="{hgt}"><TR>'
            f'<TD BGCOLOR="{fill}"><FONT SIZE="1">&nbsp;</FONT></TD></TR></TABLE></TD>')


BAR = {'senate': (2, 8), 'house': (9, 6), 'governor': (1, 8)}   # rows, block width


def balance(level, t, year):
    """Seats as teletext blocks, one per seat: solid = won (or not up this year), outline = leading,
    white outline = not decided. Filled column by column, Democrats from the left, Republicans from the right."""
    segs = [(t['total']['D'], COL['D'], COL['D']), (t['lead']['D'], COL['D'], BLACK), (t['total']['I'], COL['I'], COL['I']), (t['lead']['I'], COL['I'], BLACK),
            (0, WHITE, BLACK), (t['lead']['R'], COL['R'], BLACK), (t['total']['R'], COL['R'], COL['R'])]
    used = sum(s[0] for s in segs)
    rest = max(0, SIZE[level] - used)
    segs[4] = (rest, WHITE, BLACK)
    seats = [(ring, fill) for n, ring, fill in segs for _ in range(n)]
    rows, w = BAR[level]
    cols = -(-len(seats) // rows)
    grid = [[None] * cols for _ in range(rows)]
    for i, s in enumerate(seats):
        grid[i % rows][i // rows] = s
    hgt = 6 if level == 'house' else 14
    trs = ''.join('<TR>' + ''.join(block(s[0], s[1], w, hgt) if s else '<TD></TD>' for s in row) + '</TR>' for row in grid)
    bar = f'<TABLE BORDER="0" CELLPADDING="2" CELLSPACING="2" BGCOLOR="{BLACK}">{trs}</TABLE>\n'
    what = {'senate': 'seats', 'house': 'seats', 'governor': 'governorships'}[level]
    dlab = 'Democrats + independents' if level == 'senate' else 'Democrats'
    din = t['total']['D'] + (t['total']['I'] if level == 'senate' else 0)
    lead = lambda p: f" + {t['lead'][p]} leading" if t['lead'][p] else ''
    parts = [font(f"{dlab} {din}{lead('D')}", COL['D'], True)]
    if level != 'senate' and t['total']['I']:
        parts.append(font(f"Independents {t['total']['I']}", COL['I'], True))
    parts.append(font(f"Republicans {t['total']['R']}{lead('R')}", COL['R'], True))
    note = f"{rest} not decided yet" if year == 2026 and rest else ''
    maj = f"; {MAJ[level]} for a majority" if level != 'governor' else ''
    if level == 'senate' and year == 2026:
        maj += " (a 50-50 tie goes to Vice President Vance's party)"
    key = 'Solid = won or not up this year. Outline = leading. White outline = not decided.' if year == 2026 else 'Includes seats not up this year.'
    return (bar + f'<FONT FACE="{FACE}" SIZE="2">{" &nbsp;|&nbsp; ".join(parts)}{" &nbsp;|&nbsp; " + note if note else ""}<BR>'
            f'<FONT COLOR="{GREEN}">{SIZE[level]} {what}{maj}. {key}</FONT></FONT>\n')


def takeaway(level, year, races, t, S):
    n = len(races); decided = sum(1 for r in races if r['win'])
    net = lambda p: t['flips_to'][p] - t['flips_from'][p]
    if year == 2024:
        gainer = 'R' if net('R') > 0 else 'D' if net('D') > 0 else None
        g = f" and gained {abs(net(gainer))} {'seat' if abs(net(gainer)) == 1 else 'seats'}" if gainer else ', with no seats changing parties'
        flipped = [S['names'][r['state']] for r in races if r['flip']]
        lst = ', '.join(flipped[:-1]) + ' and ' + flipped[-1] if len(flipped) > 1 else (flipped[0] if flipped else '')
        if level == 'senate':
            hi, lo = max(t['total']['R'], t['total']['D']), min(t['total']['R'], t['total']['D'])
            return (f"<B>{'Republicans' if t['total']['R'] > t['total']['D'] else 'Democrats'} won the Senate majority, {hi}-{lo}.</B> Of the {n} Senate races in 2024, "
                    f"Republicans won {t['won']['R']}{g}{f' (flipping {lst})' if flipped else ''}; Democrats and independents who caucus with them won {t['won']['D'] + t['won']['I']}.")
        if level == 'house':
            fewer = t['before']['R'] - t['won']['R']
            return (f"<B>Republicans kept the House, {t['won']['R']}-{t['won']['D']}.</B> They won {t['won']['R']} of the 435 districts, "
                    f"{f'{fewer} fewer than they held before the election' if fewer > 0 else 'about as many as before'}.")
        return (f"<B>Republicans won {t['won']['R']} of the {n} governor races in 2024</B>{g}; Democrats won {t['won']['D']}. "
                f"After the election Republicans held {t['total']['R']} governorships and Democrats {t['total']['D']}.")
    if not any(r['total'] for r in races):
        if level == 'senate':
            held = t['not_up']['R'] + sum(1 for r in races if r['hc'] == 'R')
            return (f"<B>{n} Senate seats are on the ballot in 2026</B> (33 regular races plus specials in Florida and Ohio). Republicans hold {held} seats now; "
                    f"Democrats need a net gain of 4 seats for a majority (51), since Vice President Vance breaks ties.")
        if level == 'house':
            return (f"<B>All 435 House seats are on the ballot.</B> Republicans hold {t['before']['R']} seats now (including vacancies, by the last member's party); "
                    f"218 is a majority. Nine states vote under new maps drawn since 2024.")
        return (f"<B>{n} governorships are up in 2026.</B> Republicans hold {t['before']['R']} governorships now and Democrats {t['before']['D']}; "
                f"{sum(1 for r in races if r['hc'] == 'R')} of the seats up are held by Republicans.")
    lead = 'R' if t['total']['R'] + t['lead']['R'] > t['total']['D'] + t['lead']['D'] else 'D'
    what = {'senate': 'Senate', 'house': 'House', 'governor': 'governor'}[level]
    ctl = '' if level == 'governor' else (f"<B>{PLURAL[lead]} will control the {what}</B> ({t['total'][lead]} seats). " if t['total'][lead] >= MAJ[level] else '')
    fl = '; '.join(f"{PLURAL[p]} have flipped {t['flips_to'][p]}" for p in 'RDI' if t['flips_to'][p])
    dl = 'Democrats and allied independents' if level == 'senate' else 'Democrats'
    ds = t['total']['D'] + (t['total']['I'] if level == 'senate' else 0)
    return (f"{ctl}{decided} of {n} {what} races called. Republicans have {t['total']['R']}{'' if level == 'house' else ' seats'} (leading in {t['lead']['R']} more), "
            f"{dl} {ds} (leading in {t['lead']['D']} more). {fl + '.' if fl else ''}")


def cand_lines(r, limit=None, show_votes=True):
    cs = r['cands'] if limit is None else r['cands'][:limit]
    out = []
    for c in cs:
        mark = ' <B>*</B>' if c['winner'] or (r['year'] == 2024 and c is r['win']) else ''
        inc = ' (i)' if c.get('incumbent') else ''
        name = font(h(c['name']), pcol(c['party']), bool(mark))
        if r['total'] and show_votes:
            out.append(f"{name} ({c['party']}){inc}{mark} &nbsp; {num(c['votes'])} &nbsp; {pct(c['share'])}")
        elif c['unopposed']:
            out.append(f"{name} ({c['party']}){inc}{mark} &nbsp; unopposed")
        else:
            out.append(f"{name} ({c['party']}){inc}{mark}")
    more = len(r['cands']) - len(cs)
    if more > 0:
        out.append(f'<FONT COLOR="{GREY}">+ {more} other{"s" if more > 1 else ""}</FONT>')
    return '<BR>'.join(out) or f'<FONT COLOR="{GREY}">No candidates listed</FONT>'


def holder_txt(r):
    hd = r['holder']
    if not hd:
        return ''
    t = f"{h(hd['name'])} ({hd['party']})" + (', vacant' if hd.get('vacant') else '')
    if r['flip']:
        t += f"<BR><B>FLIP: {PLURAL.get(side(r['wc']), r['wc'])} gain</B>"
    elif r['lead_flip']:
        t += f"<BR>{PLURAL.get(side(r['wc']), r['wc'])} leading for a pickup"
    elif r['redrawn']:
        t += f'<BR><FONT COLOR="{GREY}">new map</FONT>'
    return t


def status_cell(r):
    if r['win']:
        if r['unopposed'] and not r['total']:
            return 'Unopposed'
        return '<B>Called</B>' if r['year'] == 2026 else 'Final'
    if r['total']:
        return 'Counting' + ('' if r['reporting'] is None else f"<BR>{r['reporting']:.0f}% in")
    return f'<FONT COLOR="{GREY}">Not counted yet</FONT>'


def TH(cols):
    return f'<TR BGCOLOR="{BLUE}">' + ''.join(f'<TH ALIGN="LEFT"><FONT FACE="{FACE}" SIZE="2" COLOR="{YELLOW}">{c}</FONT></TH>' for c in cols) + '</TR>\n'


def TD(x, extra=''):
    return f'<TD VALIGN="TOP"{extra}><FONT FACE="{FACE}" SIZE="2">{x}</FONT></TD>'


def race_table(level, races, polls, link_prefix, show_poll):
    """Senate/governor style: one row per race with every leading candidate."""
    cols = ['Race', 'Candidates (votes, share)', 'Margin', 'Status', 'Seat held by']
    if show_poll:
        cols.append('Final poll avg')
    out = ['<TABLE BORDER="0" CELLPADDING="4" CELLSPACING="0" WIDTH="100%">\n', TH(cols)]
    for r in races:
        row = [TD(f'<A HREF="{link_prefix}st/{r["state"]}.html"><B>{h(r["label"])}</B></A>'), TD(cand_lines(r, 4)), TD(margin_txt(r)), TD(status_cell(r)), TD(holder_txt(r))]
        if show_poll:
            rec = poll_rec(polls, level, r)
            row.append(TD(pair_label(rec['pair'], rec['final']['m']) if rec else f'<FONT COLOR="{GREY}">no polls</FONT>'))
        out.append('<TR>' + ''.join(row) + '</TR>\n')
    out.append('</TABLE>\n')
    return ''.join(out)


def house_table(races, S, link_prefix):
    """Compact: one row per district, grouped by state."""
    out = ['<TABLE BORDER="0" CELLPADDING="3" CELLSPACING="0" WIDTH="100%">\n', TH(['District', 'Leader / winner', 'Votes', 'Margin', 'Status', 'Held by'])]
    cur = None
    for r in races:
        if r['state'] != cur:
            cur = r['state']
            k = sum(1 for x in races if x['state'] == cur)
            out.append(f'<TR><TD COLSPAN="6"><BR><FONT FACE="{FACE}" SIZE="3" COLOR="{YELLOW}"><A NAME="{cur}"></A><B><A HREF="{link_prefix}st/{cur}.html">{h(S["names"][cur]).upper()}</A></B>'
                       f' &nbsp; {k} seat{"s" if k > 1 else ""}{" &nbsp; (new map this year)" if r["redrawn"] else ""}</FONT></TD></TR>\n')
        top = r['top']
        if top:
            mark = ' <B>*</B>' if r['win'] else ''
            who = f"{font(h(top['name']), pcol(top['party']), bool(r['win']))} ({top['party']}){mark}"
        else:
            names = [c for c in r['cands'] if c['party'] in ('R', 'D') or c['incumbent']][:3]
            who = ' v '.join(f"{font(h(c['name']), pcol(c['party']))} ({c['party']})" for c in names) or f'<FONT COLOR="{GREY}">-</FONT>'
        votes = f"{num(top['votes'])} ({pct(top['share'])})" if r['total'] and top else ''
        out.append('<TR>' + TD(h(r['short'])) + TD(who) + TD(votes) + TD(margin_txt(r)) + TD(status_cell(r)) + TD(holder_txt(r)) + '</TR>\n')
    out.append('</TABLE>\n')
    return ''.join(out)


# ---------- teletext block map ----------
def map_color(r):
    """(color, pattern) for a state's race: solid = won, check = leading, white = not counted yet,
    sparse white dots = no race (a pattern, not a color, so it can't be read as a party)."""
    if not r:
        return WHITE, 'dots'
    if r['win']:
        return COL.get(side(r['wc']), WHITE), 'solid'
    if r['total'] and r['lead']:
        return COL.get(side(r['wc']), WHITE), 'check'
    return WHITE, 'solid'


def label_fg(bg):
    return WHITE if bg in (BLUE, BLACK) else BLACK


def lit(pat, r, c):
    """Is this block lit for the pattern? solid: all; check: every other; dots: one in four."""
    return pat == 'solid' or (pat == 'check' and (r + c) % 2 == 0) or (pat == 'dots' and r % 2 == 0 and c % 2 == 0)


def block_map(mosaic, spots, color_of, link_prefix):
    """The U.S. drawn in teletext blocks: one table cell per block, runs of one color merged, two-letter state
    labels linking to the state pages. A spacer row of single cells pins every column's width for old browsers."""
    cols = len(mosaic[0])
    at = {tuple(v): st for st, v in spots.items()}
    trs = ['<TR>' + ''.join(f'<TD WIDTH="{MAP_W}"></TD>' for _ in range(cols)) + '</TR>']
    for ri, row in enumerate(mosaic):
        cells = []   # [bg, span, label]
        c = 0
        while c < cols:
            st, border = row[c]
            if (ri, c) in at:
                lab = at[(ri, c)]
                bg, pat = color_of(lab)
                bg = BLACK if pat == 'dots' else bg
                cells.append([bg, 2, f'<A HREF="{link_prefix}st/{lab}.html"><FONT SIZE="1" COLOR="{label_fg(bg)}"><B>{lab}</B></FONT></A>'])
                c += 2
                continue
            if not st or border:
                bg = BLACK
            else:
                col, pat = color_of(st)
                bg = col if lit(pat, ri, c) else BLACK
            if cells and cells[-1][0] == bg and not cells[-1][2]:
                cells[-1][1] += 1
            else:
                cells.append([bg, 1, ''])
            c += 1
        tds = []
        for bg, span, lab in cells:
            cs = f' COLSPAN="{span}"' if span > 1 else ''
            tds.append(f'<TD BGCOLOR="{bg}"{cs} HEIGHT="{MAP_H}"{" ALIGN=CENTER" if lab else ""}>{lab or "<FONT SIZE=1>&nbsp;</FONT>"}</TD>')
        trs.append('<TR>' + ''.join(tds) + '</TR>')
    return (f'<TABLE BORDER="0" CELLPADDING="0" CELLSPACING="0" BGCOLOR="{BLACK}" WIDTH="{cols * MAP_W}">\n' + '\n'.join(trs) + '\n</TABLE>\n')


STATE_W, STATE_H = 12, 18   # one block of a state outline, in pixels


def state_blocks(lines, col=YELLOW):
    """One state's outline in yellow teletext blocks (runs of lit or dark blocks merged into one cell)."""
    cols = max(len(l) for l in lines)
    trs = ['<TR>' + ''.join(f'<TD WIDTH="{STATE_W}"></TD>' for _ in range(cols)) + '</TR>']
    for l in lines:
        l = l.ljust(cols)
        runs, i = [], 0
        while i < cols:
            j = i
            while j < cols and l[j] == l[i]:
                j += 1
            runs.append((l[i] == '#', j - i)); i = j
        trs.append('<TR>' + ''.join(f'<TD BGCOLOR="{col if on else BLACK}"{f" COLSPAN={n}" if n > 1 else ""} HEIGHT="{STATE_H}"><FONT SIZE="1">&nbsp;</FONT></TD>'
                                    for on, n in runs) + '</TR>')
    return f'<TABLE BORDER="0" CELLPADDING="0" CELLSPACING="0" BGCOLOR="{BLACK}" WIDTH="{cols * STATE_W}">\n' + '\n'.join(trs) + '\n</TABLE>\n'


def swatch(col, pat='solid'):
    if pat in ('check', 'dots'):
        q = [col if lit(pat, r, c) else BLACK for r in (0, 1) for c in (0, 1)]
        return (f'<TD><TABLE BORDER="0" CELLPADDING="0" CELLSPACING="0"><TR><TD BGCOLOR="{q[0]}" WIDTH="8" HEIGHT="7"></TD><TD BGCOLOR="{q[1]}" WIDTH="8"></TD></TR>'
                f'<TR><TD BGCOLOR="{q[2]}" WIDTH="8" HEIGHT="7"></TD><TD BGCOLOR="{q[3]}" WIDTH="8"></TD></TR></TABLE></TD>')
    return f'<TD BGCOLOR="{col}" WIDTH="16"><FONT SIZE="1">&nbsp;</FONT></TD>'


def small_boxes(color_of, spots, link_prefix, states):
    """States too small to label on the map, each as a block of its color plus a link."""
    miss = [s for s in SMALL_NOTE if s in states and s not in spots] + sorted(s for s in states if s not in spots and s not in SMALL_NOTE)
    if not miss:
        return ''
    cells = []
    for st in miss:
        col, pat = color_of(st)
        cells.append(swatch(col, pat) + f'<TD><FONT FACE="{FACE}" SIZE="2">&nbsp;<A HREF="{link_prefix}st/{st}.html"><B>{st}</B></A>&nbsp;&nbsp;</FONT></TD>')
    return (f'<TABLE BORDER="0" CELLPADDING="1" CELLSPACING="2"><TR><TD><FONT FACE="{FACE}" SIZE="2" COLOR="{GREEN}">Small states:&nbsp;</FONT></TD>'
            + ''.join(cells) + '</TR></TABLE>\n')


def map_legend(year):
    items = [(COL['D'], 'solid', 'Dem. won'), (COL['R'], 'solid', 'Rep. won'), (COL['I'], 'solid', 'Ind. won')]
    if year == 2026:
        items += [(COL['D'], 'check', 'Dem. leads'), (COL['R'], 'check', 'Rep. leads'), (WHITE, 'solid', 'not counted yet')]
    items.append((WHITE, 'dots', 'no race'))
    cells = ''.join(swatch(c, p) + f'<TD><FONT FACE="{FACE}" SIZE="2">&nbsp;{t}&nbsp;&nbsp;</FONT></TD>' for c, p, t in items)
    return f'<TABLE BORDER="0" CELLPADDING="1" CELLSPACING="2"><TR>{cells}</TR></TABLE>\n'


def menu(year, links):
    """Teletext index lines: name ...... page number."""
    rows = ''.join(f'<TR><TD><FONT FACE="{FACE}" SIZE="3"><A HREF="{href}">{label}</A></FONT></TD><TD ALIGN="RIGHT"><FONT FACE="{FACE}" SIZE="3" COLOR="{YELLOW}">{n}</FONT></TD></TR>'
                   for label, href, n in links)
    return f'<TABLE BORDER="0" CELLPADDING="2" CELLSPACING="0" WIDTH="420">{rows}</TABLE>\n'


# ---------- pages ----------
def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='latin-1', newline='\n') as f:
        f.write(text)


def build_year(year, M, S, polls, status, mosaic, mspots, arts, out_dir):
    depth0 = 0 if year == 2026 else 1
    refresh = year == 2026 and status and status['phase'] != 'final'
    races = {lv: M[lv][year] for lv in LEVELS}
    T = {lv: tally(lv, year, races[lv], S) for lv in LEVELS}
    by_state = {}
    for lv in LEVELS:
        for r in races[lv]:
            by_state.setdefault(r['state'], {}).setdefault(lv, []).append(r)
    states = sorted(S['names'])
    states = [s for s in states if s != 'DC']
    show_poll = year == 2026 and bool(polls)
    P = lambda k: pno(k, year)

    def colorer(level):
        def f(st):
            rs = by_state.get(st, {}).get(level, [])
            if not rs:
                return map_color(None)
            # two Senate races in one state: color by the first called/leading one
            rs = sorted(rs, key=lambda r: (not r['win'], not r['total']))
            return map_color(rs[0])
        return f

    def para(x):
        return f'<P><FONT FACE="{FACE}" SIZE="2">{x}</FONT></P>\n'

    def emit(kind, title, body, band_text, bg, fg):
        write(os.path.join(out_dir, FILES[kind]), page(title, body, depth0, year, status, refresh, kind, band_text, bg, fg))

    index_links = [('National overview', FILES['national'], P('national')), ('Senate race by race', FILES['senate'], P('senate')),
                   ('House, all 435 seats', FILES['house'], P('house')), ('Governors', FILES['governor'], P('governor')),
                   ('States A-Z', FILES['states'], P('states'))]
    index_links.append(('2024 results', '2024/index.html', 600) if year == 2026 else ('2026 results', '../index.html', 100))

    # --- front page: the Senate map in blocks ---
    sen = colorer('senate')
    body = [block_map(mosaic, mspots, sen, ''), small_boxes(sen, mspots, '', states), map_legend(year),
            para('Pick a state for every race there.'),
            h2(f'<A HREF="{FILES["senate"]}">SENATE</A> &nbsp; {P("senate")}'), balance('senate', T['senate'], year),
            para(takeaway('senate', year, races['senate'], T['senate'], S)),
            h2('INDEX'), menu(year, index_links)]
    emit('front', f'Senate map {year} (retro)', ''.join(body), 'SENATE MAP', RED, WHITE)

    # --- national overview ---
    body = []
    for lv in LEVELS:
        body.append(h2(f'<A HREF="{PAGE[lv]}">{LNAME[lv].upper()}{"S" if lv == "governor" else ""}</A> &nbsp; {P(lv)}'))
        body.append(balance(lv, T[lv], year))
        body.append(para(takeaway(lv, year, races[lv], T[lv], S)))
    body += [h2('PAGES IN THIS SECTION'), menu(year, [('Senate map', FILES['front'], P('front'))] + index_links[1:])]
    emit('national', f'U.S. Election Results {year} (retro)', ''.join(body), 'NATIONAL', BLUE, WHITE)

    # --- Senate / Governor ---
    for lv, bg, fg in [('senate', RED, WHITE), ('governor', YELLOW, BLACK)]:
        kind = lv
        b = [balance(lv, T[lv], year), para(takeaway(lv, year, races[lv], T[lv], S))]
        if lv == 'senate':
            b.append(para(f'Map of the Senate races: <A HREF="{FILES["front"]}">page {P("front")}</A>.'))
        else:
            col = colorer(lv)
            b += [block_map(mosaic, mspots, col, ''), small_boxes(col, mspots, '', states), map_legend(year)]
        b += [h2(f'ALL {len(races[lv])} RACES'),
              para(f'<B>*</B> = winner{" (called by CivicAPI; unofficial until certified)" if year == 2026 else ""}. (i) = incumbent. '
                   f'Margin = leader minus runner-up, in points.{" Poll average: D+ means the Democrat led (likely voters, since Aug. 1)." if show_poll else ""}'),
              race_table(lv, races[lv], polls, '', show_poll)]
        emit(kind, f'{LNAME[lv]} {year} (retro)', ''.join(b), 'SENATE' if lv == 'senate' else 'GOVERNORS', bg, fg)

    # --- House ---
    hr = races['house']
    R = sum(c['votes'] for r in hr for c in r['cands'] if c['party'] == 'R'); D = sum(c['votes'] for r in hr for c in r['cands'] if c['party'] == 'D')
    TT = sum(r['total'] for r in hr)
    nat = (f"<B>National House vote:</B> {'R' if R >= D else 'D'}+{abs(R - D) / TT * 100:.1f} ({num(R)} Republican, {num(D)} Democratic votes"
           f"{' counted so far' if year == 2026 else ''}; unopposed seats add no votes)." if TT else '<B>National House vote:</B> not counted yet.')
    gen = ''
    if year == 2026 and polls and polls.get('generic'):
        g = polls['generic']
        gen = f" Final generic-ballot polling average: {pair_label(g['pair'], g['final']['m'])} ({g['final']['n']} national polls of likely voters)."
    b = [balance('house', T['house'], year),
         para(f'{takeaway("house", year, hr, T["house"], S)}<BR><BR>{nat}{gen}'),
         h2('JUMP TO A STATE'),
         para(' '.join(f'<A HREF="#{s}">{s}</A>' for s in sorted({r["state"] for r in hr}))),
         para('<B>*</B> = winner. Pick a state for every candidate. Flips are not marked in states with a new map this year.'),
         house_table(hr, S, '')]
    emit('house', f'U.S. House {year} (retro)', ''.join(b), 'HOUSE', GREEN, BLACK)

    # --- States A-Z ---
    snum = {st: (200 if year == 2026 else 700) + i + 1 for i, st in enumerate(states)}
    rows = ['<TABLE BORDER="0" CELLPADDING="3" CELLSPACING="0" WIDTH="100%">\n', TH(['Page', 'State', 'Senate', 'Governor', 'House seats'])]
    for st in states:
        s = by_state.get(st, {})
        def cell(lv):
            rs = s.get(lv, [])
            if not rs:
                return '<FONT COLOR="{}">-</FONT>'.format(GREEN)
            return '<BR>'.join((font(h(r['top']['name']), pcol(r['top']['party']), bool(r['win'])) + f" ({r['top']['party']}) {'won' if r['win'] else 'leads'}")
                               if r['top'] else ('up' if lv != 'senate' or len(rs) == 1 else 'up (special)') for r in rs)
        hs = s.get('house', [])
        hcount = {p: sum(1 for r in hs if r['top'] and side(r['wc']) == p) for p in 'DRI'}
        hc = f"{len(hs)}" + (f" &nbsp; {font(str(hcount['D']) + ' D', COL['D'])} {font(str(hcount['R']) + ' R', COL['R'])}" if any(hcount.values()) else '')
        rows.append('<TR>' + TD(font(str(snum[st]), YELLOW)) + TD(f'<A HREF="st/{st}.html"><B>{h(S["names"][st])}</B></A>') + TD(cell('senate')) + TD(cell('governor')) + TD(hc) + '</TR>\n')
    rows.append('</TABLE>\n')
    emit('states', f'States A-Z {year} (retro)', ''.join(rows), 'STATES A-Z', CYAN, BLACK)

    # --- one page per state ---
    for i, st in enumerate(states):
        s = by_state.get(st, {})
        name = S['names'][st]
        prev_st, next_st = states[i - 1], states[(i + 1) % len(states)]
        b = [f'<FONT FACE="{FACE}" SIZE="2">&lt;&lt; <A HREF="{prev_st}.html">{h(S["names"][prev_st])}</A> <FONT COLOR="{YELLOW}">{snum[prev_st]}</FONT> &nbsp; | &nbsp; '
             f'<A HREF="../states.html">All states</A> <FONT COLOR="{YELLOW}">{P("states")}</FONT> &nbsp; | &nbsp; '
             f'<A HREF="{next_st}.html">{h(S["names"][next_st])}</A> <FONT COLOR="{YELLOW}">{snum[next_st]}</FONT> &gt;&gt;</FONT>\n',
             '<BR>' + state_blocks(arts[st])]
        summary = []
        for lv in LEVELS:
            for r in s.get(lv, []):
                if lv != 'house' and r['top']:
                    summary.append(f"{LNAME[lv]}{' (special)' if r['seat'] == 'special' else ''}: {font(h(r['top']['name']), pcol(r['top']['party']), True)} "
                                   f"{'won' if r['win'] else 'leads'} ({margin_txt(r)})")
        hs = s.get('house', [])
        if hs and any(r['top'] for r in hs):
            hcount = {p: sum(1 for r in hs if r['top'] and side(r['wc']) == p) for p in 'DRI'}
            summary.append(f"U.S. House: {font(str(hcount['D']) + ' D', COL['D'], True)}, {font(str(hcount['R']) + ' R', COL['R'], True)}"
                           + (f", {hcount['I']} other" if hcount['I'] else '') + (' (won or leading)' if year == 2026 else ''))
        if summary:
            b.append(para('<BR>'.join(summary)))
        for lv in ['senate', 'governor']:
            rs = s.get(lv, [])
            title = LNAME[lv].upper()
            if not rs:
                b.append(h2(title) + para(f'<FONT COLOR="{GREEN}">Not on the ballot in {year}.</FONT>'))
                continue
            b.append(h2(title))
            b.append(race_table(lv, rs, polls, '../', show_poll).replace('<A HREF="../st/', '<A HREF="'))
        b.append(h2(f'U.S. HOUSE ({len(hs)} SEAT{"S" if len(hs) != 1 else ""})'))
        if hs and hs[0]['redrawn']:
            b.append(para('New district map this year; seat holders are from the old districts, so flips are not marked.'))
        if hs:
            tb = ['<TABLE BORDER="0" CELLPADDING="4" CELLSPACING="0" WIDTH="100%">\n', TH(['District', 'Candidates (votes, share)', 'Margin', 'Status', 'Seat held by'])]
            for r in hs:
                tb.append('<TR>' + TD(f'<B>{h(r["short"])}</B>') + TD(cand_lines(r)) + TD(margin_txt(r)) + TD(status_cell(r)) + TD(holder_txt(r)) + '</TR>\n')
            tb.append('</TABLE>\n')
            b.append(''.join(tb))
        b.append(para('<B>*</B> = winner. (i) = incumbent.'))
        write(os.path.join(out_dir, 'st', f'{st}.html'),
              page(f'{name} {year} (retro)', ''.join(b), depth0 + 1, year, status, refresh, 'states', h(name).upper(), MAGENTA, WHITE, num=snum[st]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='us/data')
    ap.add_argument('--out', default='us/retro')
    ap.add_argument('--years', default='2026,2024')
    ap.add_argument('--ascii', action='store_true', help='redraw the ASCII art and block map file first')
    a = ap.parse_args()
    art_file = os.path.join(a.data, 'retro_ascii.json')
    art = json.load(open(art_file)) if os.path.exists(art_file) and not a.ascii else None
    if art is None or 'mosaic' not in art or 'state_blocks' not in art:
        import retro_ascii as A
        shapes = A.load_shapes(os.path.join(a.data, 'us_states_albers.json'))
        if art is None:
            g = A.us_grid(shapes, 100)
            art = {'grid': [[[c['st'], c['ch']] if c else None for c in row] for row in g], 'spots': A.label_spots(g, set(shapes) - {'DC'}),
                   'states': {s: A.state_art(shapes[s]) for s in sorted(shapes) if s != 'DC'}}
        art['mosaic'], art['mosaic_spots'] = A.mosaic_grid(shapes)
        art['state_blocks'] = {s: A.state_blocks(shapes[s]) for s in sorted(shapes) if s != 'DC'}
        json.dump(art, open(art_file, 'w'), separators=(',', ':'))
    rd = lambda f: list(csv.DictReader(open(os.path.join(a.data, f), encoding='utf-8')))
    results, live = rd('us_results.csv'), rd('live_2026.csv')
    S = json.load(open(os.path.join(a.data, 'us_seats.json')))
    try:
        st = json.load(open(os.path.join(a.data, 'live_status.json')))
        status = st[0] if isinstance(st, list) else st
    except (OSError, ValueError):
        status = None
    try:
        polls = json.load(open(os.path.join(a.data, 'polls.json')))
    except (OSError, ValueError):
        polls = None
    M = {lv: {y: build(lv, y, results, live, S) for y in (2024, 2026)} for lv in LEVELS}
    mspots = {k: tuple(v) for k, v in art['mosaic_spots'].items()}
    for y in [int(x) for x in a.years.split(',')]:
        build_year(y, M, S, polls, status, art['mosaic'], mspots, art['state_blocks'], a.out if y == 2026 else os.path.join(a.out, str(y)))
    n = sum(len(fs) for _, _, fs in os.walk(a.out))
    print(json.dumps({'out': a.out, 'files': n, 'phase': (status or {}).get('phase')}))


if __name__ == '__main__':
    main()
