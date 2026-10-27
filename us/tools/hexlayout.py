"""Build a hex tile layout of the 435 U.S. House districts.

Each state is a connected blob of hexes placed near its real position; districts are assigned to the
state's hexes by geography (Census 2024 gazetteer interior points for the 119th Congress).
Usage: python3 hexlayout.py GAZETTEER.txt OUT.json
Output: {"hexes": {"TX-07": [col, row], ...}, "states": {"TX": [x, y] label hex}, "ncols": n, "nrows": n}
Hexes are pointy-top in odd-r offset coordinates: x = col + 0.5 * (row & 1), y = row * sqrt(3)/2.
"""
import csv, json, math, sys
import numpy as np
from scipy.optimize import linear_sum_assignment

SQ3 = math.sqrt(3) / 2


def albers(lon, lat, lat0=37.5, lon0=-96.0, p1=29.5, p2=45.5):
    r = math.radians
    n = (math.sin(r(p1)) + math.sin(r(p2))) / 2
    c = math.cos(r(p1)) ** 2 + 2 * n * math.sin(r(p1))
    rho0 = math.sqrt(c - 2 * n * math.sin(r(lat0))) / n
    rho = math.sqrt(c - 2 * n * math.sin(r(lat))) / n
    th = n * r(lon - lon0)
    return rho * math.sin(th), rho0 - rho * math.cos(th)  # y up


def to_xy(col, row):
    return col + 0.5 * (row & 1), row * SQ3


def neighbors(col, row):
    if row & 1:
        d = [(1, 0), (-1, 0), (0, -1), (1, -1), (0, 1), (1, 1)]
    else:
        d = [(1, 0), (-1, 0), (-1, -1), (0, -1), (-1, 1), (0, 1)]
    return [(col + a, row + b) for a, b in d]


def main(gaz, out):
    pts = {}
    for r in csv.DictReader(open(gaz), delimiter='\t'):
        r = {k.strip(): v.strip() for k, v in r.items()}
        if not r['GEOID'][2:].isdigit():
            continue
        st, cd = r['USPS'], int(r['GEOID'][2:])
        if st in ('DC', 'PR') or cd == 98:
            continue
        lon, lat = float(r['INTPTLONG']), float(r['INTPTLAT'])
        pts[(st, cd)] = (lon, lat)
    assert len(pts) == 435, len(pts)
    proj = {}
    for k, (lon, lat) in pts.items():
        if k[0] == 'AK':
            proj[k] = (-0.30, -0.20)   # tucked under the west coast, like most national maps
        elif k[0] == 'HI':
            proj[k] = (-0.20, -0.22)
        else:
            proj[k] = albers(lon, lat)
    states = sorted({k[0] for k in pts})
    count = {s: sum(1 for k in pts if k[0] == s) for s in states}
    # scale: lower-48 width ~ 34 hexes
    xs = [p[0] for k, p in proj.items() if k[0] not in ('AK', 'HI')]
    ys = [p[1] for k, p in proj.items() if k[0] not in ('AK', 'HI')]
    W = 30.0
    s = W / (max(xs) - min(xs))
    x0, y1 = min(xs), max(ys)
    grid = {k: ((p[0] - x0) * s + 1.5, (y1 - p[1]) * s + 1.5) for k, p in proj.items()}  # y down

    # state centers = mean of district points; then spread state discs so they don't overlap
    cen = {st: np.mean([grid[k] for k in grid if k[0] == st], axis=0) for st in states}
    rad = {st: math.sqrt(count[st] * SQ3 / math.pi) * 1.0 + 0.15 for st in states}
    pos = {st: cen[st].copy() for st in states}
    for it in range(3000):
        for i, a in enumerate(states):
            for b in states[i + 1:]:
                d = pos[b] - pos[a]
                dist = float(np.hypot(*d)) or 1e-6
                need = rad[a] + rad[b]
                if dist < need:
                    push = (need - dist) / 2 * d / dist
                    wa, wb = count[b] / (count[a] + count[b]), count[a] / (count[a] + count[b])  # big states move less
                    pos[a] -= push * 2 * wa * 0.5
                    pos[b] += push * 2 * wb * 0.5
        for st in states:  # pull back toward the real spot
            pos[st] += (cen[st] - pos[st]) * (0.06 if count[st] <= 2 else 0.02)
    # grow blobs: big states first, each from the hex nearest its disc center
    taken, blobs = {}, {}
    order = sorted(states, key=lambda st: -count[st])
    for st in order:
        cx, cy = pos[st]
        row = int(round(cy / SQ3))
        col = int(round(cx - 0.5 * (row & 1)))
        # nearest free hex to the center
        best = None
        for dr in range(-6, 7):
            for dc in range(-6, 7):
                h = (col + dc, row + dr)
                if h in taken:
                    continue
                x, y = to_xy(*h)
                d = (x - cx) ** 2 + (y - cy) ** 2
                if best is None or d < best[0]:
                    best = (d, h)
        blob = [best[1]]
        taken[best[1]] = st
        while len(blob) < count[st]:
            cand = {}
            for h in blob:
                for n in neighbors(*h):
                    if n in taken or n[1] < 0:
                        continue
                    x, y = to_xy(*n)
                    # distance to center, plus a small bonus for hexes touching more of the blob (compact shapes)
                    touch = sum(1 for m in neighbors(*n) if taken.get(m) == st)
                    cand[n] = (x - cx) ** 2 + (y - cy) ** 2 - 0.35 * touch
            if not cand:
                raise SystemExit(f'{st}: boxed in')
            h = min(cand, key=cand.get)
            blob.append(h)
            taken[h] = st
        blobs[st] = blob
    # assign districts inside each state by geography (normalized coordinates, least squares)
    hexes = {}
    for st in states:
        ks = sorted(k for k in pts if k[0] == st)
        hs = blobs[st]
        if len(ks) == 1:
            hexes[f'{st}-{ks[0][1]:02d}'] = list(hs[0])
            continue
        P = np.array([grid[k] for k in ks])
        H = np.array([to_xy(*h) for h in hs])
        norm = lambda A: (A - A.mean(0)) / (A.std(0) + 1e-9)
        Pn, Hn = norm(P), norm(H)
        cost = ((Pn[:, None, :] - Hn[None, :, :]) ** 2).sum(-1)
        ri, ci = linear_sum_assignment(cost)
        for i, j in zip(ri, ci):
            hexes[f'{st}-{ks[i][1]:02d}'] = list(hs[j])
    # shift so the smallest col/row is 0
    mc = min(h[0] for h in hexes.values()); mr = min(h[1] for h in hexes.values())
    if mr & 1:
        mr -= 1  # keep row parity so the odd-r offset stays correct
    for k in hexes:
        hexes[k] = [hexes[k][0] - mc, hexes[k][1] - mr]
    labels = {}
    for st in states:
        xy = np.array([to_xy(*hexes[k]) for k in hexes if k.startswith(st + '-')])
        labels[st] = [round(float(v), 2) for v in xy.mean(0)]
    res = {'hexes': dict(sorted(hexes.items())), 'labels': labels,
           'ncols': max(h[0] for h in hexes.values()) + 2, 'nrows': max(h[1] for h in hexes.values()) + 1}
    json.dump(res, open(out, 'w'))
    print(len(hexes), res['cols'], res['rows'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
