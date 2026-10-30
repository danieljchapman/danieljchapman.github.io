"""Read an Arizona state canvass (scanned) into rows: page, race, label, [16 cells].
Cells are OCR'd one by one (digits only) from the 300-dpi page image, using the county header for column positions."""
import csv, glob, re, subprocess, sys, json, concurrent.futures as cf
from PIL import Image

COUNTIES = ['Apache', 'Cochise', 'Coconino', 'Gila', 'Graham', 'Greenlee', 'La Paz', 'Maricopa', 'Mohave', 'Navajo', 'Pima', 'Pinal', 'Santa Cruz', 'Yavapai', 'Yuma', 'TOTAL']
RACE = re.compile(r'(President of the United States|U\.?S\.?,? Senator|U\.?S\.?,? Representative in Congress ?-? ?District N[oa][.,]? ?\d+|Governor|Secretary of State|Attorney General|State Treasurer|Superintendent of Public Instruction|State Mine Inspector|Corporation Commissioner(?: - Short Term)?|State Senat\w* ?[-~—]? ?District N[oa][.,]? ?\d+|State Representat\w* ?[-~—]? ?District N[oa][.,]? ?\d+|PROPOSITION \d+|Justice of the Arizona Supreme Court|Judge of the Court of Appeals|Total Ballots Cast|Total Eligible Registration)')


def lines_of(tsv):
    L = {}
    for r in csv.DictReader(open(tsv), delimiter='\t', quoting=csv.QUOTE_NONE):
        if r['level'] != '5' or not r['text'].strip():
            continue
        k = (r['block_num'], r['par_num'], r['line_num'])
        L.setdefault(k, []).append((int(r['left']), int(r['top']), int(r['width']), int(r['height']), r['text']))
    out = []
    for ws in L.values():
        ws.sort()
        out.append({'x0': min(w[0] for w in ws), 'y0': min(w[1] for w in ws), 'y1': max(w[1] + w[3] for w in ws), 'words': ws, 'text': ' '.join(w[4] for w in ws)})
    return sorted(out, key=lambda l: l['y0'])


def columns(lines):
    """Right edges of the 16 number columns (numbers are right-aligned under their county name)."""
    for l in lines:
        if 'Apache' in l['text'] and 'Maricopa' in l['text']:
            pos = {}
            for x, y, w, h, t in l['words']:
                t = t.strip('|')
                for c in COUNTIES:
                    if t == c.split()[-1] or (t == c.split()[0] and c not in ('La Paz', 'Santa Cruz')):
                        pos.setdefault(c, x + w)
            v = [pos.get(c) for c in COUNTIES]
            known = [i for i, x in enumerate(v) if x is not None]
            for i in range(16):
                if v[i] is None:
                    lo = max([k for k in known if k < i], default=None); hi = min([k for k in known if k > i], default=None)
                    v[i] = v[lo] + (v[hi] - v[lo]) * (i - lo) / (hi - lo)
            return v, l['y0'] + 25
    return None, None


def cell_ocr(args):
    img, box = args
    im = Image.open(img).crop(box)
    p = subprocess.run(['tesseract', 'stdin', 'stdout', '--psm', '7', '-c', 'tessedit_char_whitelist=0123456789,'], input=_png(im), capture_output=True)
    return p.stdout.decode().strip()


def _png(im):
    import io
    b = io.BytesIO(); im.save(b, 'PNG'); return b.getvalue()


PARTYHDR = {'REPUBLICAN': 'REP', 'DEMOCRATIC': 'DEM', 'LIBERTARIAN': 'LBT', 'GREEN': 'GRN', 'CONSTITUTION': 'CON', 'INDEPENDENT': 'IND', 'NONE': 'NONE', 'NO LABELS': 'NL', 'NONPARTISAN': 'NON'}


def main(year_dir, out):
    import os
    cfile = year_dir + '/cell_cache.json'
    cache = json.load(open(cfile)) if os.path.exists(cfile) else {}
    old = {(r['page'], r['raw']): r['cells'] for r in (json.load(open(out)) if os.path.exists(out) else [])}
    rows, jobs = [], []
    race = None; party = None
    for png in sorted(glob.glob(year_dir + '/p-*.png')):
        tsv = png[:-4] + '.tsv'
        lines = lines_of(tsv)
        cx, hy = columns(lines)
        if not cx:
            continue
        bounds = [cx[0] - (cx[1] - cx[0]) * 0.9] + [cx[i] + 14 for i in range(15)] + [min(Image.open(png).size[0] - 5, cx[15] + 40)]
        for l in lines:
            if l['y0'] <= hy: continue
            m = RACE.search(l['text'])
            label_words = [w for w in l['words'] if w[0] + w[2] < bounds[0] + 10]
            label = ' '.join(w[4] for w in label_words).strip(' |:;.,-~_')
            hdr = re.sub(r'[^A-Za-z ]', '', l['text']).strip().upper()
            if hdr in PARTYHDR: party = PARTYHDR[hdr]; continue
            if m and (not re.search(r'\(\w{2,4}\)', l['text'][:12])):
                race = m.group(1); party = None
                if not race.startswith('Total'):
                    continue
                label = race
            if not race: continue
            if party and race.startswith('President') and re.search(r', ?President', label) and not label.startswith('('):
                label = f'({party}) ' + label
            if not (re.search(r'\((REP|DEM|LBT|LIB|GRN|IND|NPP|NONE|NON|ATP|TOR|CON|\w{2,5})\)', label) or label.startswith('Total') or re.match(r'^(YES|NO)\b', label) or re.search(r'Be retained', label)):
                continue
            y0, y1 = l['y0'] - 6, l['y1'] + 6
            i = len(rows)
            rows.append({'page': png.split('/')[-1], 'race': race, 'label': label, 'cells': [None] * 16, 'raw': l['text']})
            if (rows[-1]['page'], l['text']) in old: rows[-1]['cells'] = old[(rows[-1]['page'], l['text'])]; continue
            for c in range(16):
                jobs.append((i, c, (png, (int(bounds[c]) + 4, y0, int(bounds[c + 1]), y1))))
    key = lambda j: j[2][0].split('/')[-1] + '|' + ','.join(map(str, j[2][1]))
    todo = [j for j in jobs if key(j) not in cache]
    with cf.ThreadPoolExecutor(4) as ex:
        res = list(ex.map(cell_ocr, [j[2] for j in todo]))
    for j, t in zip(todo, res): cache[key(j)] = t
    json.dump(cache, open(cfile, 'w'))
    for j in jobs:
        rows[j[0]]['cells'][j[1]] = cache[key(j)]
    print(len(todo), 'new cells')
    json.dump(rows, open(out, 'w'), indent=0)
    print(len(rows), 'rows')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
