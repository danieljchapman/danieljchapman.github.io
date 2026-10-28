"""ASCII-art state shapes for the retro pages (us/retro/), drawn from data/us_states_albers.json.

Each character cell is sampled on a fine grid. Cells fully inside a state are filled; cells on a coast or
border get an edge character chosen from which quarters of the cell are covered (/ \\ | - and so on), so the
outlines look drawn rather than stair-stepped.
"""
import json
import numpy as np
from matplotlib.path import Path

FIPS = {'01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA', '08': 'CO', '09': 'CT', '10': 'DE', '11': 'DC', '12': 'FL', '13': 'GA', '15': 'HI',
        '16': 'ID', '17': 'IL', '18': 'IN', '19': 'IA', '20': 'KS', '21': 'KY', '22': 'LA', '23': 'ME', '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN',
        '28': 'MS', '29': 'MO', '30': 'MT', '31': 'NE', '32': 'NV', '33': 'NH', '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND', '39': 'OH',
        '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI', '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT', '50': 'VT', '51': 'VA', '53': 'WA',
        '54': 'WV', '55': 'WI', '56': 'WY'}
ASPECT = 1.9          # a monospace character is about 1.9 times as tall as it is wide
SUB = 4               # samples per cell side (4 x 4)

# quarters covered (top-left, top-right, bottom-left, bottom-right) -> character
EDGE = {(1, 1, 1, 1): None, (0, 0, 0, 0): ' ',
        (1, 1, 0, 0): '"', (0, 0, 1, 1): '_', (1, 0, 1, 0): '|', (0, 1, 0, 1): '|',
        (1, 0, 0, 0): "'", (0, 1, 0, 0): "'", (0, 0, 1, 0): '.', (0, 0, 0, 1): '.',
        (1, 1, 1, 0): '/', (0, 1, 1, 1): '/', (1, 1, 0, 1): '\\', (1, 0, 1, 1): '\\',
        (1, 0, 0, 1): '\\', (0, 1, 1, 0): '/'}


def load_shapes(path):
    """{state: [Path, ...]} (outer rings and holes; holes handled by even-odd counting) in Albers pixels."""
    t = json.load(open(path))
    sx, sy = t['transform']['scale']; tx, ty = t['transform']['translate']
    arcs = []
    for a in t['arcs']:
        x = y = 0; pts = []
        for dx, dy in a:
            x += dx; y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(ids):
        out = []
        for i in ids:
            pts = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(pts if not out else pts[1:])
        return out

    shapes = {}
    for g in t['objects']['states']['geometries']:
        st = FIPS.get(str(g['id']).zfill(2))
        if not st:
            continue
        polys = g['arcs'] if g['type'] == 'MultiPolygon' else [g['arcs']]
        shapes[st] = [Path(ring(r)) for poly in polys for r in poly]
    return shapes


def _inside(paths, pts):
    """Even-odd test over all rings of one state."""
    n = np.zeros(len(pts), dtype=int)
    for p in paths:
        n += p.contains_points(pts)
    return n % 2 == 1


def _grid(bbox, cols):
    x0, y0, x1, y1 = bbox
    cw = (x1 - x0) / cols
    ch = cw * ASPECT
    rows = max(1, int(np.ceil((y1 - y0) / ch)))
    # center the shape vertically in the rows
    y0 -= (rows * ch - (y1 - y0)) / 2
    return x0, y0, cw, ch, rows


def _samples(x0, y0, cw, ch, rows, cols):
    """(rows, cols, SUB, SUB, 2) sample points."""
    f = (np.arange(SUB) + 0.5) / SUB
    xs = x0 + (np.arange(cols)[:, None] + f[None, :]) * cw          # cols x SUB
    ys = y0 + (np.arange(rows)[:, None] + f[None, :]) * ch          # rows x SUB
    X = np.broadcast_to(xs[None, :, None, :], (rows, cols, SUB, SUB))
    Y = np.broadcast_to(ys[:, None, :, None], (rows, cols, SUB, SUB))
    return np.stack([X, Y], -1).reshape(-1, 2)


def _quarters(cov):
    """cov: (rows, cols, SUB, SUB) bool -> (rows, cols, 4) quarter coverage (>= half of the quarter)."""
    h = SUB // 2
    q = [cov[..., :h, :h], cov[..., :h, h:], cov[..., h:, :h], cov[..., h:, h:]]
    return np.stack([x.mean(axis=(-1, -2)) >= 0.5 for x in q], -1)


def _edge_char(q, frac):
    key = tuple(int(v) for v in q)
    if key == (0, 0, 0, 0):
        return '.' if frac > 0.12 else ' '
    return EDGE[key]


def _area(p):
    v = p.vertices
    return abs(np.dot(v[:-1, 0], v[1:, 1]) - np.dot(v[1:, 0], v[:-1, 1])) / 2


def state_art(paths, cols=56, max_rows=22, fill='#'):
    """A single state's outline as a list of strings (no color). Islands and lakes under 1% of the state's
    largest ring are left out; at this size they only leave stray specks."""
    big = max(_area(p) for p in paths)
    paths = [p for p in paths if _area(p) >= 0.01 * big]
    allp = np.vstack([p.vertices for p in paths])
    x0, y0 = allp.min(0); x1, y1 = allp.max(0)
    w, h = x1 - x0, y1 - y0
    # fit width, then shrink if too tall
    c = cols
    if h / (w / c * ASPECT) > max_rows:
        c = max(8, int(max_rows * ASPECT * w / h))
    pad = w / c * 0.5
    bx = (x0 - pad, y0 - pad * ASPECT * 0.5, x1 + pad, y1 + pad * ASPECT * 0.5)
    c += 1
    gx, gy, cw, ch, rows = _grid(bx, c)
    cov = _inside(paths, _samples(gx, gy, cw, ch, rows, c)).reshape(rows, c, SUB, SUB)
    q = _quarters(cov); frac = cov.mean(axis=(-1, -2))
    lines = []
    for r in range(rows):
        s = ''.join(fill if q[r, k].all() else _edge_char(q[r, k], frac[r, k]) for k in range(c))
        lines.append(s.rstrip())
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def us_grid(shapes, cols=100):
    """National map: per cell, the state that covers it (or None), its coverage quarters, and border flags.
    Returns rows of cells: dict(st, ch) where ch is the character to draw before coloring/labels."""
    allp = np.vstack([p.vertices for ps in shapes.values() for p in ps])
    x0, y0 = allp.min(0) - 2; x1, y1 = allp.max(0) + 2
    gx, gy, cw, ch, rows = _grid((x0, y0, x1, y1), cols)
    pts = _samples(gx, gy, cw, ch, rows, cols)
    owner = np.full(len(pts), -1)
    names = sorted(shapes)
    for i, st in enumerate(names):
        p = shapes[st]
        allv = np.vstack([q.vertices for q in p])
        bx0, by0 = allv.min(0); bx1, by1 = allv.max(0)
        m = (pts[:, 0] >= bx0) & (pts[:, 0] <= bx1) & (pts[:, 1] >= by0) & (pts[:, 1] <= by1)
        idx = np.where(m)[0]
        if len(idx):
            owner[idx[_inside(p, pts[idx])]] = i
    owner = owner.reshape(rows, cols, SUB, SUB)
    # cell owner = most common state among its samples (ties: first found)
    grid = []
    for r in range(rows):
        row = []
        for c in range(cols):
            o = owner[r, c].ravel()
            o = o[o >= 0]
            if not len(o):
                row.append(None); continue
            vals, cnt = np.unique(o, return_counts=True)
            s = vals[cnt.argmax()]
            cov = owner[r, c] == s
            row.append({'st': names[s], 'q': _quarters(cov[None, None])[0, 0], 'frac': cov.mean()})
        grid.append(row)
    # characters: coast cells by coverage; interior cells next to another state (right or below) get a border mark
    for r in range(rows):
        for c in range(cols):
            cell = grid[r][c]
            if not cell:
                continue
            q = cell['q']
            if not q.all():
                cell['ch'] = _edge_char(q, cell['frac']); cell['kind'] = 'edge'
                continue
            right = grid[r][c + 1] if c + 1 < cols else None
            below = grid[r + 1][c] if r + 1 < rows else None
            br = bool(right and right['st'] != cell['st'])
            bb = bool(below and below['st'] != cell['st'])
            if br and bb:
                cell['ch'], cell['kind'] = '|', 'border'
            elif br:
                cell['ch'], cell['kind'] = '|', 'border'
            elif bb:
                cell['ch'], cell['kind'] = '_', 'border'
            else:
                cell['ch'], cell['kind'] = None, 'fill'
    # trim empty rows top and bottom
    while grid and all(c is None for c in grid[0]):
        grid.pop(0)
    while grid and all(c is None for c in grid[-1]):
        grid.pop()
    return grid


def label_spots(grid, states):
    """Best cell to start each state's two-letter label: two adjacent fill cells farthest from the state's edge.
    States with no room are left out (the page lists them beside the map)."""
    rows, cols = len(grid), len(grid[0])
    best = {}
    for r in range(rows):
        for c in range(cols - 1):
            a, b = grid[r][c], grid[r][c + 1]
            if not a or not b or a['st'] != b['st'] or a.get('kind') != 'fill' or b.get('kind') != 'fill':
                continue
            st = a['st']
            # distance to the nearest cell of another state / outside, in cell units (y doubled for aspect)
            d = 99
            for rr in range(max(0, r - 4), min(rows, r + 5)):
                for cc in range(max(0, c - 8), min(cols, c + 10)):
                    o = grid[rr][cc]
                    if not o or o['st'] != st or o.get('kind') != 'fill':
                        dd = max(abs(rr - r) * ASPECT, min(abs(cc - c), abs(cc - c - 1)))
                        d = min(d, dd)
            if d > best.get(st, (-1,))[0]:
                best[st] = (d, r, c)
    return {st: (v[1], v[2]) for st, v in best.items() if st in states}
