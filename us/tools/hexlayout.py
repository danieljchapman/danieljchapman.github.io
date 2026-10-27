"""House tile map that keeps the shape of the U.S.: one hexagon per district, every state one connected piece.

1. Lay a pointy-top hex grid over the lower-48 outline (us-atlas nation-albers-10m) at the spacing that puts exactly
   432 cell centers inside it (435 minus Alaska's 1 and Hawaii's 2), trimming or adding boundary cells to hit 432.
2. Match districts to cells by minimum total squared distance (Hungarian algorithm) using each district's real position
   (Census gazetteer interior point, projected with d3.geoAlbersUsa — the projection of the us-atlas file). This is a
   discrete density-equalizing map: crowded areas spread out, empty ones fill in, relative positions are kept.
3. Repair: swap the states of neighboring cells (simulated annealing) to make every state a single connected piece and
   keep states compact, while staying close to the matched positions.
4. Re-match districts to cells inside each state by geography. Alaska and Hawaii go below the Southwest, as on most maps.
Usage: python3 hexlayout2.py NATION_TOPOJSON CD_ALBERS.json OUT.json [PREVIEW.png]
Output: {"hexes": {"TX-07": [col, row], ...}, "labels": {"TX": [x, y]}, "ncols": n, "nrows": n}
Coordinates: odd-r offset; center x = col + 0.5 * (row & 1), y = row * sqrt(3)/2 (hex width = 1).
"""
import json, math, random, sys
from collections import defaultdict, deque
import numpy as np
from matplotlib.path import Path
from scipy.optimize import linear_sum_assignment

SQ3 = math.sqrt(3) / 2


def decode_rings(topo, obj):
    """Polygon rings (absolute coordinates) of a TopoJSON object."""
    tr = topo.get('transform')
    arcs = []
    for arc in topo['arcs']:
        x = y = 0; pts = []
        for dx, dy in arc:
            x += dx; y += dy
            pts.append((x * tr['scale'][0] + tr['translate'][0], y * tr['scale'][1] + tr['translate'][1]) if tr else (dx, dy))
        arcs.append(pts)
    def ring(ix):
        out = []
        for i in ix:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(a if not out else a[1:])
        return out
    rings = []
    for g in topo['objects'][obj]['geometries']:
        polys = g['arcs'] if g['type'] == 'MultiPolygon' else [g['arcs']]
        for poly in polys:
            for r in poly:
                rings.append(ring(r))
    return rings


def state_rings(topo, fips):
    """{state abbr: [rings]} from us-atlas states (geometry id = FIPS)."""
    tr = topo['transform']
    arcs = []
    for arc in topo['arcs']:
        x = y = 0; pts = []
        for dx, dy in arc:
            x += dx; y += dy
            pts.append((x * tr['scale'][0] + tr['translate'][0], y * tr['scale'][1] + tr['translate'][1]))
        arcs.append(pts)
    out = {}
    for g in topo['objects']['states']['geometries']:
        st = fips.get(g['id'])
        if not st: continue
        polys = g['arcs'] if g['type'] == 'MultiPolygon' else [g['arcs']]
        for poly in polys:
            ring = []
            for i in poly[0]:
                a = arcs[i] if i >= 0 else arcs[~i][::-1]
                ring.extend(a if not ring else a[1:])
            out.setdefault(st, []).append(ring)
    return out


def dist_to_rings(pts, rings):
    """Distance from each point to the union of polygons (0 inside)."""
    pts = np.asarray(pts, float)
    inside = np.zeros(len(pts), bool)
    best = np.full(len(pts), np.inf)
    for rg in rings:
        R = np.asarray(rg, float)
        if len(R) and not np.allclose(R[0], R[-1]): R = np.vstack([R, R[:1]])
        inside |= Path(R).contains_points(pts)
        A, B = R[:-1], R[1:]
        AB = B - A; L2 = (AB ** 2).sum(1) + 1e-12
        AP = pts[:, None, :] - A[None, :, :]
        t = np.clip((AP * AB[None]).sum(-1) / L2[None], 0, 1)
        d = np.sqrt(((AP - t[..., None] * AB[None]) ** 2).sum(-1)).min(1)
        best = np.minimum(best, d)
    best[inside] = 0
    return best


def axial(c, r): return (c - (r - (r & 1)) // 2, r)
def offset(q, r): return (q + (r - (r & 1)) // 2, r)
DIRS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
def nbrs(a): return [(a[0] + dq, a[1] + dr) for dq, dr in DIRS]
def center(a):
    c, r = offset(*a)
    return (c + 0.5 * (r & 1), r * SQ3)


def grid_inside(paths, bbox, s, ox=0.0, oy=0.0):
    """Axial cells whose centers (in map units, spacing s) fall inside the outline."""
    x0, y0, x1, y1 = bbox
    cells = {}
    rmax = int((y1 - y0) / (s * SQ3)) + 2
    cmax = int((x1 - x0) / s) + 2
    for r in range(-1, rmax):
        for c in range(-1, cmax):
            X = x0 + ox + (c + 0.5 * (r & 1)) * s
            Y = y0 + oy + r * SQ3 * s
            if any(p.contains_point((X, Y)) for p in paths):
                cells[axial(c, r)] = (X, Y)
    return cells


def main(nation_path, cd_path, out_path, preview=None):
    states_path = nation_path.replace('nation-albers', 'states-albers')
    random.seed(1)
    topo = json.load(open(nation_path))
    rings = decode_rings(topo, 'nation')
    cd = {k: tuple(v) for k, v in json.load(open(cd_path)).items()}
    main48 = {k: v for k, v in cd.items() if k[:2] not in ('AK', 'HI')}
    N = len(main48)
    assert N == 432, N
    # lower-48 rings: those containing a lower-48 district point, plus big ones nearby (skip the AK/HI insets)
    xs = [p[0] for p in main48.values()]; ys = [p[1] for p in main48.values()]
    paths = []
    for rg in rings:
        if len(rg) < 30:
            continue
        P = Path(rg)
        # keep rings that hold a lower-48 district point (the mainland; drops the Alaska/Hawaii insets and small islands)
        if not P.contains_points(np.array(list(main48.values()))).any():
            continue
        paths.append(P)
    # ---- partial cartogram: warp the outline, the state borders and the district points so crowded areas grow ----
    FIPS = {'01': 'AL', '04': 'AZ', '05': 'AR', '06': 'CA', '08': 'CO', '09': 'CT', '10': 'DE', '12': 'FL', '13': 'GA', '16': 'ID', '17': 'IL', '18': 'IN', '19': 'IA', '20': 'KS', '21': 'KY', '22': 'LA', '23': 'ME', '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN', '28': 'MS', '29': 'MO', '30': 'MT', '31': 'NE', '32': 'NV', '33': 'NH', '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND', '39': 'OH', '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI', '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT', '50': 'VT', '51': 'VA', '53': 'WA', '54': 'WV', '55': 'WI', '56': 'WY'}
    srings = state_rings(json.load(open(states_path)), FIPS)
    outline = [np.asarray(p.vertices, float) for p in paths]
    srings = {S: [np.asarray(r, float) for r in rs] for S, rs in srings.items()}
    pts = {k: np.asarray(v, float) for k, v in main48.items()}
    WARP = float(__import__('os').environ.get('HEX_WARP', '0.3'))   # share of the density-equalizing displacement applied per round
    ROUNDS = int(__import__('os').environ.get('HEX_ROUNDS', '3'))
    SIG = float(__import__('os').environ.get('HEX_SIGMA', '70'))
    for rnd in range(ROUNDS):
        pp = [Path(o) for o in outline]
        bb = (min(o[:, 0].min() for o in outline), min(o[:, 1].min() for o in outline), max(o[:, 0].max() for o in outline), max(o[:, 1].max() for o in outline))
        lo_, hi_ = 3.0, 80.0
        for _ in range(30):
            sp = (lo_ + hi_) / 2
            if len(grid_inside(pp, bb, sp)) > N: lo_ = sp
            else: hi_ = sp
        cl = grid_inside(pp, bb, hi_)
        ks_ = sorted(pts); cl_ = list(cl.values())
        Dm = np.array([pts[k] for k in ks_]); Cm = np.array(cl_)
        r_, c_ = linear_sum_assignment(((Dm[:, None] - Cm[None]) ** 2).sum(-1))
        disp = Cm[c_] - Dm[r_]
        src = Dm[r_]
        def field(P):
            P = np.asarray(P, float)
            out = np.zeros_like(P)
            for i0 in range(0, len(P), 4000):
                Q = P[i0:i0 + 4000]
                w = np.exp(-((Q[:, None] - src[None]) ** 2).sum(-1) / (2 * SIG * SIG)) + 1e-12
                out[i0:i0 + 4000] = (w[..., None] * disp[None]).sum(1) / w.sum(1)[:, None]
            return out
        mv = np.sqrt((disp ** 2).sum(1)).mean()
        print(f'warp round {rnd}: mean displacement {mv:.1f}')
        outline = [o + WARP * field(o) for o in outline]
        srings = {S: [r + WARP * field(r) for r in rs] for S, rs in srings.items()}
        P_all = np.array([pts[k] for k in ks_]); F_all = field(P_all)
        pts = {k: P_all[i] + WARP * F_all[i] for i, k in enumerate(ks_)}
    paths = [Path(o) for o in outline]
    main48 = {k: tuple(v) for k, v in pts.items()}
    bbox = (min(p.get_extents().x0 for p in paths), min(p.get_extents().y0 for p in paths),
            max(p.get_extents().x1 for p in paths), max(p.get_extents().y1 for p in paths))
    # spacing with ~432 cells
    lo, hi = 5.0, 60.0
    for _ in range(40):
        s = (lo + hi) / 2
        n = len(grid_inside(paths, bbox, s))
        if n > N: lo = s
        else: hi = s
    s = hi
    cells = grid_inside(paths, bbox, s)
    print('spacing', round(s, 2), 'cells', len(cells))
    # hit exactly N: drop cells with fewest neighbors / add empty cells with most neighbors (ties: nearest to the outline center)
    while len(cells) != N:
        if len(cells) > N:
            k = min(cells, key=lambda a: (sum(n in cells for n in nbrs(a)), -abs(cells[a][1] - 300)))
            del cells[k]
        else:
            cand = {n for a in cells for n in nbrs(a) if n not in cells}
            k = max(cand, key=lambda a: sum(n in cells for n in nbrs(a)))
            c, r = offset(*k)
            cells[k] = (bbox[0] + (c + 0.5 * (r & 1)) * s, bbox[1] + r * SQ3 * s)
    # fill holes (empty cells surrounded by 5–6 cells) by moving in the loneliest boundary cell
    for _ in range(50):
        hole = [a for a in {n for c in cells for n in nbrs(c) if n not in cells} if sum(n in cells for n in nbrs(a)) >= 5]
        if not hole: break
        k = min(cells, key=lambda a: sum(n in cells for n in nbrs(a)))
        del cells[k]
        a = hole[0]; c, r = offset(*a)
        cells[a] = (bbox[0] + (c + 0.5 * (r & 1)) * s, bbox[1] + r * SQ3 * s)
    keys = sorted(main48)
    clist = sorted(cells)
    D = np.array([main48[k] for k in keys]); C = np.array([cells[a] for a in clist])
    cost = ((D[:, None, :] - C[None, :, :]) ** 2).sum(-1) / (s * s)   # in squared hex widths
    ri, ci = linear_sum_assignment(cost)
    at = {clist[j]: keys[i] for i, j in zip(ri, ci)}                  # cell -> district
    target = {keys[i]: C[j] for i, j in zip(ri, ci)}
    dpos = {k: np.array(main48[k]) for k in keys}
    print('matched; mean distance (hex widths)', round(float(np.sqrt(cost[ri, ci]).mean()), 2))

    # ---- repair: each state one piece, compact, near its districts' real positions ----
    st = {a: at[a][:2] for a in at}
    states = sorted(set(st.values()))
    size = defaultdict(int)
    for v in st.values(): size[v] += 1
    # each state's "home": the center of the cells the matching gave it (the matching has already spread out crowded areas)
    ALPHA = float(__import__('os').environ.get('HEX_ALPHA', '0.5'))   # 0 = spread-out positions only, 1 = true centers only
    home = {S: (1 - ALPHA) * np.mean([target[k] for k in keys if k[:2] == S], axis=0) + ALPHA * np.mean([dpos[k] for k in keys if k[:2] == S], axis=0) for S in states}
    cxy = {a: np.array(cells[a]) for a in cells}
    CCa = np.array([cxy[a] for a in clist])
    terr = {S: dict(zip(clist, dist_to_rings(CCa, srings[S]) / s)) for S in states}   # hexes from the state's real borders
    WT = float(__import__('os').environ.get('HEX_TERR', '2'))
    def ccost(a, S): return ((cxy[a] - home[S]) ** 2).sum() / (s * s) + WT * terr[S][a] ** 2
    # capacity-constrained assignment: each state gets exactly its seat count, cells as close to its home as possible
    slots = [S for S in states for _ in range(size[S])]
    HM = np.array([home[S] for S in slots]); CC = np.array([cxy[a] for a in clist])
    r3, c3 = linear_sum_assignment(np.array([[ccost(a, S) for a in clist] for S in slots]))
    st = {clist[j]: slots[i] for i, j in zip(r3, c3)}

    def comps(S):
        mine = [a for a in st if st[a] == S]
        seen, out = set(), []
        for a in mine:
            if a in seen: continue
            q = deque([a]); seen.add(a); comp = [a]
            while q:
                b = q.popleft()
                for n in nbrs(b):
                    if n in st and st[n] == S and n not in seen:
                        seen.add(n); q.append(n); comp.append(n)
            out.append(comp)
        return out

    def state_cost(S):
        cs = comps(S)
        big = max(cs, key=len)
        bc = np.mean([cxy[a] for a in big], axis=0)
        pen = 0.0
        for c in cs:
            if c is big: continue
            for a in c: pen += 60 + np.linalg.norm(cxy[a] - bc) / s * 8
        return pen + sum(ccost(a, S) for a in st if st[a] == S)

    def border(a):
        return sum(1 for n in nbrs(a) if n in st and st[n] != st[a])

    sc = {S: state_cost(S) for S in states}
    edge = sum(border(a) for a in st) / 2
    LAMB = 0.8
    total = sum(sc.values()) + LAMB * edge
    print('start cost', round(total, 1), 'pieces', sum(len(comps(S)) for S in states))
    pairs = [(a, n) for a in st for n in nbrs(a) if n in st and a < n]
    T = 1.0
    for it in range(250000):
        a, b = random.choice(pairs)
        A, B = st[a], st[b]
        if A == B: continue
        local = set([a, b] + nbrs(a) + nbrs(b))
        before_e = sum(border(x) for x in local if x in st)
        oldA, oldB = sc[A], sc[B]
        st[a], st[b] = B, A
        after_e = sum(border(x) for x in local if x in st)
        nA, nB = state_cost(A), state_cost(B)
        d = (nA + nB - oldA - oldB) + LAMB * (after_e - before_e) / 2
        if d <= 0 or random.random() < math.exp(-d / T):
            sc[A], sc[B] = nA, nB; total += d
        else:
            st[a], st[b] = A, B
        if it % 1000 == 0:
            T = max(0.01, T * 0.975)
        if it % 50000 == 0:
            print(it, round(total, 1), 'pieces', sum(len(comps(S)) for S in states), 'T', round(T, 3))
    pieces = {S: len(comps(S)) for S in states}
    bad = {S: n for S, n in pieces.items() if n > 1}
    print('non-contiguous states:', bad)
    # ---- districts inside each state, by geography ----
    hexes = {}
    for S in states:
        ks = [k for k in keys if k[:2] == S]
        cs = [a for a in st if st[a] == S]
        P_ = np.array([dpos[k] for k in ks]); H = np.array([cxy[a] for a in cs])
        if len(ks) > 1:
            nz = lambda X: (X - X.mean(0)) / (X.std(0) + 1e-9)
            cost2 = ((nz(P_)[:, None, :] - nz(H)[None, :, :]) ** 2).sum(-1) + ((P_[:, None, :] - H[None, :, :]) ** 2).sum(-1) / (s * s) * 0.05
            r2, c2 = linear_sum_assignment(cost2)
        else:
            r2, c2 = [0], [0]
        for i, j in zip(r2, c2):
            hexes[ks[i]] = offset(*cs[j])
    # Alaska and Hawaii: below the Southwest
    lab_rows = [v[1] for v in hexes.values()]; lab_cols = [v[0] for v in hexes.values()]
    ca = [v for k, v in hexes.items() if k[:2] == 'CA']
    base_r = max(lab_rows) - 1
    if base_r & 1: base_r -= 1
    c0 = min(c for c, r in ca)
    hexes['AK-00'] = (c0, base_r)
    hexes['HI-01'] = (c0 + 3, base_r + 1)
    hexes['HI-02'] = (c0 + 4, base_r + 1)
    occupied = {}
    for k, v in hexes.items():
        assert v not in occupied, (k, occupied.get(v)); occupied[v] = k
    mc = min(v[0] for v in hexes.values()); mr = min(v[1] for v in hexes.values())
    if mr & 1: mr -= 1
    hexes = {k: [v[0] - mc, v[1] - mr] for k, v in sorted(hexes.items())}
    labels = {}
    for S in sorted({k[:2] for k in hexes}):
        pts = np.array([(c + 0.5 * (r & 1), r * SQ3) for k, (c, r) in hexes.items() if k[:2] == S])
        m = pts.mean(0)
        best = min(pts, key=lambda p: ((p - m) ** 2).sum())   # put the label on a hex of the state (not in a gap)
        labels[S] = [round(float(best[0]), 3), round(float(best[1]), 3)]
    # debug: real map position of each district's hex and the real state containing it
    inv = {}
    for a, S in st.items(): pass
    res_dbg = {}
    for S in states:
        for a in [a for a in st if st[a] == S]:
            home_state = min(states, key=lambda T: terr[T][a])
            res_dbg.setdefault(S, []).append((round(float(cxy[a][0])), round(float(cxy[a][1])), home_state))
    json.dump(res_dbg, open(out_path.replace('.json', '_dbg.json'), 'w'))
    inside = sum(1 for S, v in res_dbg.items() for x in v if x[2] == S)
    print('hexes inside their real state:', inside, 'of', len(st))
    res = {'hexes': hexes, 'labels': labels, 'ncols': max(v[0] for v in hexes.values()) + 2, 'nrows': max(v[1] for v in hexes.values()) + 1}
    json.dump(res, open(out_path, 'w'), separators=(',', ':'))
    print('wrote', len(hexes), res['ncols'], res['nrows'])
    if preview:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
        from matplotlib.patches import RegularPolygon
        import colorsys, hashlib
        fig, ax = plt.subplots(figsize=(15, 9.5))
        for k, (c, r) in hexes.items():
            h = int(hashlib.md5(k[:2].encode()).hexdigest()[:6], 16) / 0xffffff
            ax.add_patch(RegularPolygon((c + 0.5 * (r & 1), -r * SQ3), 6, radius=0.577, facecolor=colorsys.hsv_to_rgb(h, 0.4, 0.93), edgecolor='white', lw=0.6))
        for S, (x, y) in labels.items():
            ax.text(x, -y, S, ha='center', va='center', fontsize=8, weight='bold')
        ax.set_xlim(-1, res['ncols']); ax.set_ylim(-res['nrows'] * SQ3 - 1, 1); ax.set_aspect('equal'); ax.axis('off')
        plt.savefig(preview, dpi=85, bbox_inches='tight')


if __name__ == '__main__':
    main(*sys.argv[1:])
