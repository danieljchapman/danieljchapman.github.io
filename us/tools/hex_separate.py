"""Pull the states of the House tile map slightly apart: a small offset per state so that every hex is at least
1 + GAP hex widths from any hex of another state (inside a state hexes stay adjacent, 1 apart).
Adds "offsets": {"TX": [dx, dy]} (layout units, hex width = 1) to the layout file.
Usage: python3 hex_separate.py us_hex.json [GAP]
"""
import json, math, sys
import numpy as np

SQ3 = math.sqrt(3) / 2


def main(path, gap=0.35):
    L = json.load(open(path))
    keys = sorted(L['hexes'])
    st = [k[:2] for k in keys]
    P = np.array([(c + 0.5 * (r & 1), r * SQ3) for c, r in (L['hexes'][k] for k in keys)])
    states = sorted(set(st))
    idx = {S: i for i, S in enumerate(states)}
    si = np.array([idx[s] for s in st])
    off = np.zeros((len(states), 2))
    # start by spreading every state a little away from the map's center, then fix the gaps pair by pair
    cen = np.array([P[si == i].mean(0) for i in range(len(states))])
    off = (cen - P.mean(0)) * 0.03
    want = 1 + gap
    diff_state = si[:, None] != si[None, :]
    for it in range(4000):
        Q = P + off[si]
        D = Q[:, None, :] - Q[None, :, :]
        d = np.sqrt((D ** 2).sum(-1)) + 1e-9
        bad = diff_state & (d < want)
        n = bad.sum() // 2
        if not n:
            break
        push = np.where(bad[..., None], D / d[..., None] * (want - d)[..., None], 0).sum(1)   # per hex
        step = np.zeros_like(off)
        np.add.at(step, si, push)
        cnt = np.bincount(si, minlength=len(states))[:, None]
        off += 0.6 * step / np.sqrt(np.maximum(cnt, 1))
        off -= 0.002 * off   # mild pull back so states don't drift further than needed
    Q = P + off[si]
    D = np.sqrt(((Q[:, None] - Q[None]) ** 2).sum(-1))
    print('iterations', it, 'min gap between states', round(float(D[diff_state].min()) - 1, 3), 'largest offset', round(float(np.abs(off).max()), 2))
    L['offsets'] = {S: [round(float(off[i, 0]), 3), round(float(off[i, 1]), 3)] for S, i in idx.items()}
    json.dump(L, open(path, 'w'), separators=(',', ':'))


if __name__ == '__main__':
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 0.35)
