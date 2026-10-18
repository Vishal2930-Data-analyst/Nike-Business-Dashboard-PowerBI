"""Layout QA: no unintended overlap between native visuals; every visual inside its card shell or a header/title zone;
KPI cards bound to measures (no hard-coded numbers)."""
import sys, itertools
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'build'))  # Scripts/build when run from Scripts/qa
import report_def as R
res = []
def inter(a, b):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    return max(0, min(ax + aw, bx + bw) - max(ax, bx)) * max(0, min(ay + ah, by + bh) - max(ay, by))
bad, outside, hard = [], [], []
for pg in R.PAGES:
    vis = pg.vis
    for a, b in itertools.combinations(vis, 2):
        if inter(a['pos'], b['pos']) > 2:
            overlay = {a['kind'], b['kind']} == {'card', 'donut'} and (a.get('category') or b.get('category'))
            if not overlay:
                bad.append(f"{pg.display}: {a['kind']}@{[round(x) for x in a['pos']]} x {b['kind']}@{[round(x) for x in b['pos']]}")
    shells = [e for e in pg.bg if e['t'] in ('shell', 'kpi', 'slicerbox')]
    for v in vis:
        x, y, w, h = v['pos']
        if v['kind'] in ('nav',) and x < 200:
            continue
        inside = any(s['x'] - 1 <= x and x + w <= s['x'] + s['w'] + 1 and s['y'] - 1 <= y and y + h <= s['y'] + s['h'] + 1 for s in shells)
        zone = y + h <= 112 or v['kind'] in ('nav', 'clear', 'back')
        if not (inside or zone):
            outside.append(f"{pg.display}: {v['kind']}@{[round(t) for t in v['pos']]}")
        if v['kind'] == 'card' and v['field'][2] != 'M':
            hard.append(pg.display)
n = sum(len(p.vis) for p in R.PAGES)
res.append(('No unintended overlap between visuals (only donut centre-label overlays)', not bad, '; '.join(bad[:6])))
res.append(('Every visual sits inside its card shell / header zone', not outside, '; '.join(outside[:6])))
res.append(('All cards display measures (no hard-coded values)', not hard, ','.join(hard)))
fails = 0
for name, ok, det in res:
    fails += not ok; print(('PASS' if ok else 'FAIL') + f': {name} ({n} visuals)' + ('' if ok else '\n   ' + det))
sys.exit(1 if fails else 0)
