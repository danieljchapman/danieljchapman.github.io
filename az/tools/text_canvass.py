"""Read an Arizona state canvass PDF that has a text layer (2016, 2022) into the same rows as ocr_canvass.py."""
import re, subprocess, sys, json, html
sys.path.insert(0, '/home/claude/work')
from ocr_canvass import COUNTIES, RACE

PARTYHDR = {'Republican': 'REP', 'Democratic': 'DEM', 'Libertarian': 'LBT', 'Green': 'GRN', 'None': 'NONE', 'Constitution': 'CON', 'Independent': 'IND', 'Nonpartisan': 'NON'}


def pages(pdf):
    x = subprocess.run(['pdftotext', '-bbox-layout', pdf, '-'], capture_output=True, text=True).stdout
    for pg in re.findall(r'<page.*?</page>', x, re.S):
        lines = []
        for ln in re.findall(r'<line.*?</line>', pg, re.S):
            ws = [(float(a), float(b), float(c), float(d), html.unescape(t)) for a, b, c, d, t in re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', ln)]
            if ws: lines.append(ws)
        # merge lines on the same baseline (pdftotext splits table rows into blocks)
        rows = []
        for ws in sorted(lines, key=lambda w: (round(w[0][3]), w[0][0])):
            y = ws[0][3]
            for r in rows:
                if abs(r['y'] - y) < 3: r['w'] += ws; break
            else: rows.append({'y': y, 'w': list(ws)})
        for r in rows: r['w'].sort()
        yield sorted(rows, key=lambda r: r['y'])


def interp(v):
    known = [i for i, x in enumerate(v) if x is not None]
    out = []
    for i, x in enumerate(v):
        if x is not None: out.append(x); continue
        lo = max([k for k in known if k < i], default=None); hi = min([k for k in known if k > i], default=None)
        if lo is None: lo, hi = hi, min(k for k in known if k > hi)
        if hi is None: hi, lo = lo, max(k for k in known if k < lo)
        out.append(v[lo] + (v[hi] - v[lo]) * (i - lo) / (hi - lo))
    return out


def main(pdf, out):
    rows, race, party = [], None, None
    for pi, lines in enumerate(pages(pdf)):
        hdr = next((l for l in lines if any(w[4] == 'Apache' for w in l['w']) and any(w[4] == 'Maricopa' for w in l['w'])), None)
        if not hdr: continue
        pos = {}
        for x0, y0, x1, y1, t in hdr['w']:
            for c in COUNTIES:
                if t == c.split()[0] or t == c.split()[-1]: pos.setdefault(c, x1)
        if 'Santa Cruz' in pos and 'Pinal' in pos and pos['Santa Cruz'] < pos['Pinal']: del pos['Santa Cruz']
        right = interp([pos.get(c) for c in COUNTIES])
        first = right[0] - (right[1] - right[0])
        for l in lines:
            if l['y'] <= hdr['y']: continue
            ws = l['w']
            # glue split numbers like '201 ,578'
            g = []
            for w in ws:
                if g and re.match(r'^[,.]\d', w[4]) and w[0] - g[-1][2] < 12: g[-1] = (g[-1][0], g[-1][1], w[2], w[3], g[-1][4] + w[4])
                else: g.append(w)
            lab = ' '.join(w[4] for w in g if w[2] < first + 5).strip()
            nums = [w for w in g if w[2] >= first + 5]
            text = ' '.join(w[4] for w in g)
            if lab.strip(' *') in PARTYHDR: party = PARTYHDR[lab.strip(' *')]; continue
            m = RACE.search(text)
            if m and not re.match(r'^\(\w', lab):
                race = m.group(1); party = None
                if not race.startswith('Total'): continue
                lab = race
            if not race or not nums: continue
            cells = [''] * 16
            for w in nums:
                xc = w[2]
                i = min(range(16), key=lambda k: abs(right[k] - xc))
                cells[i] = (cells[i] + w[4]) if cells[i] else w[4]
            if party and not lab.startswith('('): lab = f'({party}) ' + lab
            rows.append({'page': pi + 1, 'race': race, 'label': lab, 'cells': cells, 'raw': text})
    json.dump(rows, open(out, 'w'), indent=0)
    print(len(rows), 'rows')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
