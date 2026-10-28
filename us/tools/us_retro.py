#!/usr/bin/env python3
"""Retro National pages (us/retro/): plain HTML 3.2 for old browsers (an iMac G3 with IE 5, Classilla, early Safari).

No JavaScript, no CSS, no images: tables, <FONT> colors and ASCII-art maps in <PRE>. Built from the same files as
the National page, and rebuilt by the election-night workflow after every update (us/tools/fetch_live.sh), so it
is as current as the main page. Pages reload themselves every 2 minutes until every 2026 race is called.

Usage: python3 us/tools/us_retro.py [--data us/data] [--out us/retro]
       python3 us/tools/us_retro.py --ascii   (redraw data/retro_ascii.json from the state shapes; needs numpy + matplotlib)
The ASCII art is drawn once (retro_ascii.py) and saved, so the election-night build needs only the standard library.
Writes: index.html, senate.html, house.html, governors.html, states.html, st/XX.html, and the same set for 2024
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
# colors: dark = won, light = leading (web-safe-ish, readable on white)
COL = {'R': '#CC0000', 'D': '#0033CC', 'I': '#663399', 'L': '#996600', 'G': '#006600'}
LIGHT = {'R': '#FF9999', 'D': '#99BBFF', 'I': '#CC99FF'}
GREY, DIM, PEND = '#808080', '#C0C0C0', '#999999'
NAVY = '#000080'
REFRESH = 120
SMALL_NOTE = ['VT', 'NH', 'MA', 'RI', 'CT', 'NJ', 'DE', 'MD', 'HI']


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
    return COL.get(p, GREY)


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
def page(title, body, depth, year, status, refresh):
    up = '../' * depth
    yr = '' if year == 2026 else '2024/'
    other = f'{up}2024/index.html' if year == 2026 else f'{up}index.html'
    nav = ' | '.join([f'<A HREF="{up}{yr}index.html">Home</A>', f'<A HREF="{up}{yr}senate.html">Senate</A>', f'<A HREF="{up}{yr}house.html">House</A>',
                      f'<A HREF="{up}{yr}governors.html">Governors</A>', f'<A HREF="{up}{yr}states.html">States A-Z</A>',
                      f'<A HREF="{other}">{"2024 results" if year == 2026 else "2026 results"}</A>'])
    meta = f'<META HTTP-EQUIV="Refresh" CONTENT="{REFRESH}">\n' if refresh else ''
    live = ''
    if year == 2026 and status:
        if status['phase'] == 'pre-election':
            msg = 'Election Day is Tuesday, Nov. 3. Results appear here as polls close (first closings 6 pm ET) and update every few minutes through the night.'
        elif status['phase'] == 'counting':
            msg = f"<B>COUNTING</B> &nbsp; {status['called']} of {status['races']} races called"
        else:
            msg = f"All {status['races']} races called. Unofficial until certified."
        live = (f'<TABLE WIDTH="100%" CELLPADDING="4" CELLSPACING="0" BORDER="0"><TR><TD BGCOLOR="#FFFFCC"><FONT FACE="Arial,Helvetica" SIZE="2">{msg}'
                f'<BR>Last update: {h(et(status["updated_at"]))}{" &nbsp; This page reloads every 2 minutes." if refresh else ""}</FONT></TD></TR></TABLE>\n')
    return f"""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<HTML>
<HEAD>
<TITLE>{h(title)}</TITLE>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=iso-8859-1">
{meta}</HEAD>
<BODY BGCOLOR="#FFFFFF" TEXT="#000000" LINK="#0000CC" VLINK="#551A8B" ALINK="#FF0000">
<TABLE WIDTH="100%" CELLPADDING="6" CELLSPACING="0" BORDER="0"><TR><TD BGCOLOR="{NAVY}">
<FONT FACE="Arial,Helvetica" COLOR="#FFFFFF" SIZE="5"><B>U.S. ELECTION RESULTS {year}</B></FONT><BR>
<FONT FACE="Arial,Helvetica" COLOR="#CCCCFF" SIZE="2">Senate &middot; House &middot; Governors &nbsp;--&nbsp; retro edition</FONT>
</TD></TR></TABLE>
<FONT FACE="Arial,Helvetica" SIZE="2">[ {nav} ]</FONT>
<HR>
{live}{body}
<HR>
<FONT FACE="Arial,Helvetica" SIZE="1">{source_line(year, status)}<BR>
Plain-HTML edition for older computers: no scripts, no images. The full interactive page is at
<A HREF="{up}../index.html?year={year}">danieljchapman.github.io/us/</A> (needs a modern browser).</FONT>
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
    return f'<P><FONT FACE="Arial,Helvetica" SIZE="4" COLOR="{NAVY}"><B>{text}</B></FONT></P>\n'


def balance(level, t, year):
    """Seat bar as a row of colored table cells (600 pixels = the whole chamber)."""
    W = 600
    segs = [('D', t['total']['D'], COL['D']), ('Dl', t['lead']['D'], LIGHT['D']), ('I', t['total']['I'], COL['I']), ('Il', t['lead']['I'], LIGHT['I']),
            ('U', 0, '#E0E0E0'), ('Rl', t['lead']['R'], LIGHT['R']), ('R', t['total']['R'], COL['R'])]
    used = sum(s[1] for s in segs)
    segs[4] = ('U', SIZE[level] - used, '#E0E0E0')
    cells = ''.join(f'<TD BGCOLOR="{c}" WIDTH="{max(1, round(n * W / SIZE[level]))}">&nbsp;</TD>' for _, n, c in segs if n > 0)
    what = {'senate': 'seats', 'house': 'seats', 'governor': 'governorships'}[level]
    dlab = 'Democrats + independents' if level == 'senate' else 'Democrats'
    din = t['total']['D'] + (t['total']['I'] if level == 'senate' else 0)
    lead = lambda p: f" + {t['lead'][p]} leading" if t['lead'][p] else ''
    parts = [font(f"{dlab} {din}{lead('D')}", COL['D'], True)]
    if level != 'senate' and t['total']['I']:
        parts.append(font(f"Independents {t['total']['I']}", COL['I'], True))
    parts.append(font(f"Republicans {t['total']['R']}{lead('R')}", COL['R'], True))
    rest = SIZE[level] - used
    note = f"{rest} not decided yet" if year == 2026 and rest else ''
    maj = f"; {MAJ[level]} for a majority" if level != 'governor' else ''
    if level == 'senate' and year == 2026:
        maj += " (a 50-50 tie goes to Vice President Vance's party)"
    key = 'Dark = won or not up this year, light = leading.' if year == 2026 else 'Includes seats not up this year.'
    return (f'<TABLE CELLPADDING="0" CELLSPACING="0" BORDER="1"><TR><TD><TABLE CELLPADDING="0" CELLSPACING="0" BORDER="0" WIDTH="{W}" HEIGHT="22"><TR>{cells}</TR></TABLE></TD></TR></TABLE>\n'
            f'<FONT FACE="Arial,Helvetica" SIZE="2">{" &nbsp;|&nbsp; ".join(parts)}{" &nbsp;|&nbsp; " + note if note else ""}<BR>'
            f'<FONT COLOR="{GREY}">{SIZE[level]} {what}{maj}. {key}</FONT></FONT>\n')


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
    return '<TR BGCOLOR="#DDDDEE">' + ''.join(f'<TH ALIGN="LEFT"><FONT FACE="Arial,Helvetica" SIZE="2">{c}</FONT></TH>' for c in cols) + '</TR>\n'


def TD(x, extra=''):
    return f'<TD VALIGN="TOP"{extra}><FONT SIZE="2">{x}</FONT></TD>'


def race_table(level, races, polls, link_prefix, show_poll):
    """Senate/governor style: one row per race with every leading candidate."""
    cols = ['Race', 'Candidates (votes, share)', 'Margin', 'Status', 'Seat held by']
    if show_poll:
        cols.append('Final poll avg')
    out = ['<TABLE BORDER="1" CELLPADDING="3" CELLSPACING="0" WIDTH="100%">\n', TH(cols)]
    for i, r in enumerate(races):
        bg = ' BGCOLOR="#F4F4F4"' if i % 2 else ''
        row = [TD(f'<A HREF="{link_prefix}st/{r["state"]}.html"><B>{h(r["label"])}</B></A>'), TD(cand_lines(r, 4)), TD(margin_txt(r)), TD(status_cell(r)), TD(holder_txt(r))]
        if show_poll:
            rec = poll_rec(polls, level, r)
            row.append(TD(pair_label(rec['pair'], rec['final']['m']) if rec else f'<FONT COLOR="{GREY}">no polls</FONT>'))
        out.append(f'<TR{bg}>' + ''.join(row) + '</TR>\n')
    out.append('</TABLE>\n')
    return ''.join(out)


def house_table(races, S, link_prefix):
    """Compact: one row per district, grouped by state."""
    out = ['<TABLE BORDER="1" CELLPADDING="2" CELLSPACING="0" WIDTH="100%">\n', TH(['District', 'Leader / winner', 'Votes', 'Margin', 'Status', 'Held by'])]
    cur = None
    for r in races:
        if r['state'] != cur:
            cur = r['state']
            k = sum(1 for x in races if x['state'] == cur)
            out.append(f'<TR BGCOLOR="#EEEEEE"><TD COLSPAN="6"><FONT FACE="Arial,Helvetica" SIZE="2"><B><A HREF="{link_prefix}st/{cur}.html">{h(S["names"][cur])}</A></B>'
                       f' &nbsp; {k} seat{"s" if k > 1 else ""}{" &nbsp; (new map this year)" if r["redrawn"] else ""}</FONT></TD></TR>\n')
        top = r['top']
        if top:
            mark = ' <B>*</B>' if r['win'] else ''
            who = f"{font(h(top['name']), pcol(top['party']), bool(r['win']))} ({top['party']}){mark}"
        else:
            names = [c for c in r['cands'] if c['party'] in ('R', 'D') or c['incumbent']][:3]
            who = ' v. '.join(f"{font(h(c['name']), pcol(c['party']))} ({c['party']})" for c in names) or f'<FONT COLOR="{GREY}">-</FONT>'
        votes = f"{num(top['votes'])} ({pct(top['share'])})" if r['total'] and top else ''
        out.append('<TR>' + TD(h(r['short'])) + TD(who) + TD(votes) + TD(margin_txt(r)) + TD(status_cell(r)) + TD(holder_txt(r)) + '</TR>\n')
    out.append('</TABLE>\n')
    return ''.join(out)


# ---------- ASCII maps ----------
def map_color(r):
    """(color, fill char) for a state's race on the national map."""
    if not r:
        return DIM, '.'
    if r['win']:
        return COL.get(side(r['wc'])), '#'
    if r['total'] and r['lead']:
        return COL.get(side(r['wc'])), '+'
    return PEND, ':'


def us_map(grid, spots, color_of, link_prefix, labels_linked=True):
    """National ASCII map in <PRE>, states colored by color_of(st) -> (color, fill), labels link to state pages."""
    lines = []
    for ri, row in enumerate(grid):
        cells = []   # (color, html)
        c = 0
        while c < len(row):
            cell = row[c]
            if cell and (ri, c) == spots.get(cell['st']):
                st = cell['st']; col, _ = color_of(st)
                lab = font(f'<B>{st}</B>', GREY if col == DIM else col)
                cells.append((None, f'<A HREF="{link_prefix}st/{st}.html">{lab}</A>' if labels_linked else lab))
                c += 2; continue
            if not cell:
                cells.append(('', ' '))
            else:
                col, fill = color_of(cell['st'])
                ch = cell['ch'] if cell['ch'] else fill
                cells.append((col, html.escape(ch, quote=False)))
            c += 1
        # merge runs of the same color into one <FONT>
        out, run_col, run = [], None, []
        def flush():
            if run:
                txt = ''.join(run)
                out.append(f'<FONT COLOR="{run_col}">{txt}</FONT>' if run_col else txt)
        for col, txt in cells:
            if col is None:
                flush(); run.clear(); run_col = None; out.append(txt); continue
            if col != run_col:
                flush(); run.clear(); run_col = col
            run.append(txt)
        flush()
        lines.append(''.join(out).rstrip())
    return '<PRE>' + '\n'.join(lines) + '</PRE>\n'


def small_boxes(color_of, spots, link_prefix, states):
    """States too small to label on the map, as a row of colored links."""
    miss = [s for s in SMALL_NOTE if s in states and s not in spots] + sorted(s for s in states if s not in spots and s not in SMALL_NOTE)
    if not miss:
        return ''
    parts = []
    for st in miss:
        col, fill = color_of(st)
        parts.append(f'<A HREF="{link_prefix}st/{st}.html">{font("<B>" + st + "</B>", GREY if col == DIM else col)}</A> <TT>{font(fill * 2, col)}</TT>')
    return f'<FONT FACE="Arial,Helvetica" SIZE="2">Small states: &nbsp; {" &nbsp; ".join(parts)}</FONT><BR>\n'


def map_legend(year):
    k = lambda ch, col, txt: f'<TT>{font(ch * 3, col)}</TT> {txt}'
    items = [k('#', COL['D'], 'Democrat won'), k('#', COL['R'], 'Republican won'), k('#', COL['I'], 'Independent won')]
    if year == 2026:
        items += [k('+', COL['D'], 'Dem. leading'), k('+', COL['R'], 'Rep. leading'), k(':', PEND, 'not counted yet')]
    items.append(k('.', DIM, 'no race'))
    return f'<FONT FACE="Arial,Helvetica" SIZE="2">{" &nbsp; ".join(items)}</FONT><BR>\n'


# ---------- pages ----------
def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='latin-1', newline='\n') as f:
        f.write(text)


def build_year(year, M, S, polls, status, grid, spots, arts, out_dir):
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

    def colorer(level):
        def f(st):
            rs = by_state.get(st, {}).get(level, [])
            if not rs:
                return map_color(None)
            # two Senate races in one state: color by the first called/leading one
            rs = sorted(rs, key=lambda r: (not r['win'], not r['total']))
            return map_color(rs[0])
        return f

    # --- home ---
    body = []
    for lv in LEVELS:
        body.append(h2(f'<A HREF="{PAGE[lv]}">{LNAME[lv]}{"s" if lv == "governor" else ""}</A>'))
        body.append(balance(lv, T[lv], year))
        body.append(f'<P><FONT FACE="Arial,Helvetica" SIZE="2">{takeaway(lv, year, races[lv], T[lv], S)}</FONT></P>\n')
    body.append(h2('Pick a state'))
    body.append('<FONT FACE="Arial,Helvetica" SIZE="2">Click a state\'s initials for every race in that state. Map colors show the Senate races.</FONT>\n')
    body.append(us_map(grid, spots, colorer('senate'), ''))
    body.append(small_boxes(colorer('senate'), spots, '', states))
    body.append(map_legend(year))
    write(os.path.join(out_dir, 'index.html'), page(f'U.S. Election Results {year} (retro)', ''.join(body), depth0, year, status, refresh))

    # --- Senate / Governor ---
    for lv in ['senate', 'governor']:
        b = [h2(f'{LNAME[lv]} {year}'), balance(lv, T[lv], year),
             f'<P><FONT FACE="Arial,Helvetica" SIZE="2">{takeaway(lv, year, races[lv], T[lv], S)}</FONT></P>\n',
             us_map(grid, spots, colorer(lv), ''), small_boxes(colorer(lv), spots, '', states), map_legend(year),
             h2(f'All {len(races[lv])} races'),
             f'<FONT FACE="Arial,Helvetica" SIZE="2"><B>*</B> = winner{" (called by CivicAPI; unofficial until certified)" if year == 2026 else ""}. (i) = incumbent. '
             f'Margin = leader minus runner-up, in points.{" Poll average: D+ means the Democrat led (likely voters, since Aug. 1)." if show_poll else ""}</FONT><BR><BR>\n',
             race_table(lv, races[lv], polls, '', show_poll)]
        write(os.path.join(out_dir, PAGE[lv]), page(f'{LNAME[lv]} {year} (retro)', ''.join(b), depth0, year, status, refresh))

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
    b = [h2(f'U.S. House {year}'), balance('house', T['house'], year),
         f'<P><FONT FACE="Arial,Helvetica" SIZE="2">{takeaway("house", year, hr, T["house"], S)}<BR><BR>{nat}{gen}</FONT></P>\n',
         '<FONT FACE="Arial,Helvetica" SIZE="2">Jump to: ' + ' '.join(f'<A HREF="#{s}">{s}</A>' for s in sorted({r["state"] for r in hr})) + '</FONT><BR><BR>\n',
         f'<FONT FACE="Arial,Helvetica" SIZE="2"><B>*</B> = winner. Click a state for every candidate. Flips are not marked in states with a new map this year.</FONT><BR><BR>\n',
         house_table(hr, S, '').replace('<TR BGCOLOR="#EEEEEE"><TD COLSPAN="6"><FONT FACE="Arial,Helvetica" SIZE="2"><B><A HREF="st/',
                                         '<TR BGCOLOR="#EEEEEE"><TD COLSPAN="6"><FONT FACE="Arial,Helvetica" SIZE="2"><B><A NAME="@@"></A><A HREF="st/')]
    body = ''.join(b)
    # anchors for the jump list
    body = re.sub(r'<A NAME="@@"></A><A HREF="st/(\w\w)\.html">', lambda m: f'<A NAME="{m.group(1)}"></A><A HREF="st/{m.group(1)}.html">', body)
    write(os.path.join(out_dir, 'house.html'), page(f'U.S. House {year} (retro)', body, depth0, year, status, refresh))

    # --- States A-Z ---
    rows = ['<TABLE BORDER="1" CELLPADDING="3" CELLSPACING="0">\n', TH(['State', 'Senate', 'Governor', 'House seats'])]
    for st in states:
        s = by_state.get(st, {})
        def cell(lv):
            rs = s.get(lv, [])
            if not rs:
                return f'<FONT COLOR="{GREY}">-</FONT>'
            return '<BR>'.join((font(h(r['top']['name']), pcol(r['top']['party']), bool(r['win'])) + f" ({r['top']['party']}) {'won' if r['win'] else 'leads'}")
                               if r['top'] else ('up' if lv != 'senate' or len(rs) == 1 else 'up (special)') for r in rs)
        hs = s.get('house', [])
        hcount = {p: sum(1 for r in hs if r['top'] and side(r['wc']) == p) for p in 'DRI'}
        hc = f"{len(hs)}" + (f" &nbsp; {font(str(hcount['D']) + ' D', COL['D'])} {font(str(hcount['R']) + ' R', COL['R'])}" if any(hcount.values()) else '')
        rows.append('<TR>' + TD(f'<A HREF="st/{st}.html"><B>{h(S["names"][st])}</B></A>') + TD(cell('senate')) + TD(cell('governor')) + TD(hc) + '</TR>\n')
    rows.append('</TABLE>\n')
    write(os.path.join(out_dir, 'states.html'), page(f'States A-Z {year} (retro)', h2(f'Every state, {year}') + ''.join(rows), depth0, year, status, refresh))

    # --- one page per state ---
    for i, st in enumerate(states):
        s = by_state.get(st, {})
        name = S['names'][st]
        prev_st, next_st = states[i - 1], states[(i + 1) % len(states)]
        b = [f'<FONT FACE="Arial,Helvetica" SIZE="2">&lt;&lt; <A HREF="{prev_st}.html">{h(S["names"][prev_st])}</A> &nbsp; | &nbsp; '
             f'<A HREF="../states.html">All states</A> &nbsp; | &nbsp; <A HREF="{next_st}.html">{h(S["names"][next_st])}</A> &gt;&gt;</FONT>\n',
             h2(f'{h(name).upper()} &nbsp; {year}'),
             '<TABLE BORDER="0" CELLPADDING="0" CELLSPACING="0"><TR><TD BGCOLOR="#000000"><PRE><FONT COLOR="#33FF33">\n'
             + '\n'.join(html.escape(' ' + l, quote=False) for l in arts[st]) + '\n</FONT></PRE></TD></TR></TABLE>\n']
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
            b.append('<P><FONT FACE="Arial,Helvetica" SIZE="2">' + '<BR>'.join(summary) + '</FONT></P>\n')
        for lv in ['senate', 'governor']:
            rs = s.get(lv, [])
            title = LNAME[lv]
            if not rs:
                b.append(h2(title) + f'<FONT FACE="Arial,Helvetica" SIZE="2" COLOR="{GREY}">Not on the ballot in {year}.</FONT>\n')
                continue
            b.append(h2(title))
            b.append(race_table(lv, rs, polls, '../', show_poll).replace('<A HREF="../st/', '<A HREF="'))
        b.append(h2(f'U.S. House ({len(hs)} seat{"s" if len(hs) != 1 else ""})'))
        if hs and hs[0]['redrawn']:
            b.append(f'<FONT FACE="Arial,Helvetica" SIZE="2">New district map this year; seat holders are from the old districts, so flips are not marked.</FONT><BR><BR>\n')
        if hs:
            tb = ['<TABLE BORDER="1" CELLPADDING="3" CELLSPACING="0" WIDTH="100%">\n', TH(['District', 'Candidates (votes, share)', 'Margin', 'Status', 'Seat held by'])]
            for j, r in enumerate(hs):
                bg = ' BGCOLOR="#F4F4F4"' if j % 2 else ''
                tb.append(f'<TR{bg}>' + TD(f'<B>{h(r["short"])}</B>') + TD(cand_lines(r)) + TD(margin_txt(r)) + TD(status_cell(r)) + TD(holder_txt(r)) + '</TR>\n')
            tb.append('</TABLE>\n')
            b.append(''.join(tb))
        b.append(f'<P><FONT FACE="Arial,Helvetica" SIZE="2"><B>*</B> = winner. (i) = incumbent.</FONT></P>\n')
        write(os.path.join(out_dir, 'st', f'{st}.html'), page(f'{name} {year} (retro)', ''.join(b), depth0 + 1, year, status, refresh))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='us/data')
    ap.add_argument('--out', default='us/retro')
    ap.add_argument('--years', default='2026,2024')
    ap.add_argument('--ascii', action='store_true', help='redraw the ASCII art file first')
    a = ap.parse_args()
    art_file = os.path.join(a.data, 'retro_ascii.json')
    if a.ascii or not os.path.exists(art_file):
        import retro_ascii as A
        shapes = A.load_shapes(os.path.join(a.data, 'us_states_albers.json'))
        g = A.us_grid(shapes, 100)
        spots = A.label_spots(g, set(shapes) - {'DC'})
        art = {'grid': [[[c['st'], c['ch']] if c else None for c in row] for row in g], 'spots': spots,
               'states': {s: A.state_art(shapes[s]) for s in sorted(shapes) if s != 'DC'}}
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
    art = json.load(open(art_file))
    grid = [[{'st': c[0], 'ch': c[1]} if c else None for c in row] for row in art['grid']]
    spots = {k: tuple(v) for k, v in art['spots'].items()}
    arts = art['states']
    for y in [int(x) for x in a.years.split(',')]:
        build_year(y, M, S, polls, status, grid, spots, arts, a.out if y == 2026 else os.path.join(a.out, str(y)))
    n = sum(len(fs) for _, _, fs in os.walk(a.out))
    print(json.dumps({'out': a.out, 'files': n, 'phase': (status or {}).get('phase')}))


if __name__ == '__main__':
    main()
