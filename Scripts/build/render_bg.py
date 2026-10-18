"""Render page wallpaper PNGs (3200x1800, i.e. 2x of the 1600x900 canvas) from report_def.
Also writes the HTML sources so designers can tweak and re-render."""
import sys, re, html
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import report_def as R
from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
import os
ICONS = Path(os.environ.get('LUCIDE_ICONS', '/home/claude/npm/node_modules/lucide-static/icons'))  # npm i lucide-static

def icon(name, size=18, color='#171717', stroke=2):
    svg = (ICONS / f'{name}.svg').read_text()
    svg = re.sub(r'<!--.*?-->', '', svg, flags=re.S)
    svg = re.sub(r'width="\d+"', f'width="{size}"', svg, count=1)
    svg = re.sub(r'height="\d+"', f'height="{size}"', svg, count=1)
    svg = svg.replace('stroke="currentColor"', f'stroke="{color}"').replace('stroke-width="2"', f'stroke-width="{stroke}"')
    return svg

def esc(s):
    return html.escape(s or '')

def abs_div(x, y, w=None, h=None, style='', inner=''):
    ws = f'width:{w}px;' if w is not None else ''
    hs = f'height:{h}px;' if h is not None else ''
    return f'<div style="position:absolute;left:{x}px;top:{y}px;{ws}{hs}{style}">{inner}</div>'

MARK = '''<svg width="34" height="22" viewBox="0 0 34 22"><path d="M2 20 L14 2 L20 2 L10 20 Z" fill="#fff"/>
<path d="M14 20 L26 2 L32 2 L22 20 Z" fill="#fff" opacity=".55"/></svg>'''

def sidebar(active):
    parts = [abs_div(0, 0, R.SIDEBAR_W, R.H, 'background:#111111;')]
    parts.append(abs_div(24, 26, inner=MARK))
    parts.append(abs_div(66, 24, 120, style='color:#fff;font:800 13px/1.15 Inter;letter-spacing:.08em;',
                         inner='RETAIL<br><span style="font-weight:500;color:#A3A3A3;letter-spacing:.12em;font-size:10px">ANALYTICS</span>'))
    for i, (label, ic, key) in enumerate(R.NAV):
        y = R.NAV_Y0 + i * R.NAV_STEP
        on = key == active
        bg = 'background:#262626;' if on else ''
        col = '#FFFFFF' if on else '#A3A3A3'
        parts.append(abs_div(12, y, 176, R.NAV_H, f'{bg}border-radius:9px;'))
        if on:
            parts.append(abs_div(12, y + 9, 3, 20, 'background:#fff;border-radius:2px;'))
        parts.append(abs_div(28, y + 10, inner=icon(ic, 18, col)))
        parts.append(abs_div(58, y, 120, R.NAV_H, f'color:{col};font:{600 if on else 500} 13.5px/{R.NAV_H}px Inter;', esc(label)))
    # promo panel
    px, py, pw, ph = 12, 600, 176, 288
    promo = f'''<svg width="{pw}" height="{ph}" viewBox="0 0 {pw} {ph}" style="position:absolute;left:0;top:0">
      <defs><linearGradient id="pg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#262626"/><stop offset="1" stop-color="#050505"/></linearGradient>
      <radialGradient id="glow" cx=".55" cy=".62" r=".55"><stop offset="0" stop-color="#ffffff" stop-opacity=".22"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></radialGradient></defs>
      <rect width="{pw}" height="{ph}" rx="14" fill="url(#pg)"/>
      <rect width="{pw}" height="{ph}" rx="14" fill="url(#glow)"/>
      {''.join(f'<path d="M-10 {200 + k*9} C 50 {150 + k*7}, 120 {175 + k*6}, {pw+10} {120 + k*5}" stroke="#fff" stroke-opacity="{0.5 - k*0.045:.3f}" stroke-width="{2.4 - k*0.18:.2f}" fill="none"/>' for k in range(10))}
      <circle cx="150" cy="190" r="70" fill="none" stroke="#fff" stroke-opacity=".10" stroke-width="18"/>
      <circle cx="150" cy="190" r="40" fill="none" stroke="#fff" stroke-opacity=".16" stroke-width="2"/>
      {''.join(f'<rect x="{20 + (k*37)%70}" y="{150 + k*8}" width="{60 + (k*29)%80}" height="2.2" rx="1.1" fill="#fff" opacity="{0.15 + (k%4)*0.12:.2f}" transform="skewX(-20)"/>' for k in range(8))}
      <path d="M18 214 L60 198 L104 206 L158 182" stroke="#fff" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="158" cy="182" r="4" fill="#fff"/>
    </svg>'''
    parts.append(abs_div(px, py, pw, ph, 'border-radius:14px;overflow:hidden;', promo +
                         abs_div(16, 18, 150, inner='<div style="color:#fff;font:900 25px/1.02 Inter;letter-spacing:-.01em">MOVE<br>PEOPLE<br>FORWARD.</div>') +
                         abs_div(16, 236, 150, inner='<div style="color:#D4D4D4;font:500 11.5px/1.35 Inter">Performance inspires<br>progress.</div>')))
    return ''.join(parts)

def box(x, y, w, h, radius=10, extra=''):
    return abs_div(x, y, w, h, f'background:#fff;border:1px solid {R.C_BORDER};border-radius:{radius}px;box-sizing:border-box;{extra}')

def header():
    p = [box(216, 12, 384, 40), abs_div(229, 24, inner=icon('search', 16, '#6B7280'))]
    p += [box(1000, 12, 92, 40), abs_div(1014, 24, inner=icon('rotate-ccw', 15, '#171717')),
          abs_div(1036, 12, 50, 40, 'font:600 12.5px/40px Inter;color:#171717', 'Reset')]
    p += [box(1104, 12, 250, 40), abs_div(1113, 24, inner=icon('calendar', 16, '#6B7280'))]
    p += [box(1366, 12, 150, 40), abs_div(1375, 24, inner=icon('globe', 16, '#6B7280'))]
    p += [abs_div(1528, 22, inner=icon('bell', 19, '#171717')),
          abs_div(1541, 21, 7, 7, 'background:#E11D48;border-radius:50%;border:1.5px solid #F5F6F8')]
    p += [abs_div(1554, 18, 28, 28, 'border-radius:50%;background:linear-gradient(135deg,#404040,#111);', abs_div(6, 6, inner=icon('user', 16, '#fff')))]
    return ''.join(p)

def banner(e):
    x, y, w, h = e['x'], e['y'], e['w'], e['h']
    lanes = []
    for k in range(7):
        y1 = h + 10 - k * 2
        lanes.append(f'<path d="M {w*0.42 + k*70} {h+4} C {w*0.62 + k*40} {h*0.35}, {w*0.80 + k*12} {h*0.10}, {w+20} {-6 + k*9}" '
                     f'stroke="#ffffff" stroke-opacity="{0.95 - k*0.08:.2f}" stroke-width="{3.2 - k*0.25:.2f}" fill="none"/>')
    streaks = ''.join(f'<rect x="{w*0.50 + i*58}" y="{12 + (i*23) % 50}" width="{40 + (i*17)%60}" height="2" rx="1" fill="#171717" opacity="{0.05 + (i%3)*0.03:.2f}"/>' for i in range(10))
    svg = f'''<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="position:absolute;left:0;top:0">
      <defs><linearGradient id="bg1" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".45" stop-color="#F7F7F8"/><stop offset="1" stop-color="#D9DBDF"/></linearGradient>
      <linearGradient id="trk" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#e5e7eb" stop-opacity="0"/><stop offset=".5" stop-color="#cfd2d8"/><stop offset="1" stop-color="#9ca3af"/></linearGradient></defs>
      <rect width="{w}" height="{h}" rx="12" fill="url(#bg1)"/>
      <path d="M {w*0.40} {h} C {w*0.60} {h*0.30}, {w*0.82} {h*0.02}, {w} {-2} L {w} {h} Z" fill="url(#trk)" opacity=".9"/>
      {''.join(lanes)}{streaks}
    </svg>'''
    t = abs_div(24, 12, 900, inner=f'<div style="font:800 28px/1.15 Inter;color:#171717;letter-spacing:-.02em">{esc(e["title"])}</div>'
                f'<div style="font:400 13px/1.4 Inter;color:#6B7280;margin-top:6px">{esc(e["subtitle"])}</div>')
    tag = abs_div(w - 168, 14, 150, inner='<div style="font:700 10.5px/1.45 Inter;letter-spacing:.32em;color:#171717;text-align:right">SPORT<br>CHANGES<br>EVERYTHING</div>')
    return abs_div(x, y, w, h, f'border-radius:12px;overflow:hidden;border:1px solid {R.C_BORDER};box-sizing:border-box;', svg + t + tag)

def shell(e):
    x, y, w, h = e['x'], e['y'], e['w'], e['h']
    inner = ''
    if e.get('title'):
        inner += abs_div(16, 13, w - 140, style='font:700 14px/1.2 Inter;color:#171717;white-space:nowrap', inner=esc(e['title']))
    if e.get('subtitle'):
        inner += abs_div(16, 32, w - 32, style='font:400 11px/1.2 Inter;color:#6B7280;white-space:nowrap;overflow:hidden;text-overflow:ellipsis', inner=esc(e['subtitle']))
    if e.get('link'):
        inner += abs_div(w - 96, 9, 84, 26, 'font:600 12px/26px Inter;color:#171717;text-align:right;display:flex;justify-content:flex-end;align-items:center;gap:2px',
                         f'{esc(e["link"])}{icon("chevron-right", 14, "#171717")}')
    return abs_div(x, y, w, h, f'background:#fff;border:1px solid {R.C_BORDER};border-radius:12px;box-sizing:border-box;', inner)

def kpi(e):
    x, y, w, h = e['x'], e['y'], e['w'], e['h']
    right = 84 if e['spark'] else 14
    inner = abs_div(14, 16, 40, 40, 'border-radius:50%;background:#F3F4F6;display:flex;align-items:center;justify-content:center',
                    icon(e['icon'], 20, '#171717'))
    inner += abs_div(62, 11, w - 62 - right, style='font:700 10px/1.2 Inter;letter-spacing:.06em;color:#6B7280;text-align:center;white-space:nowrap',
                     inner=esc(e['label']))
    if e['spark']:
        inner += abs_div(w - 86, 16, 1, h - 32, 'background:#F0F1F3')
    return abs_div(x, y, w, h, f'background:#fff;border:1px solid {R.C_BORDER};border-radius:12px;box-sizing:border-box;', inner)

def slicerbox(e):
    x, y, w, h = e['x'], e['y'], e['w'], e['h']
    return abs_div(x, y, w, h, f'background:#fff;border:1px solid {R.C_BORDER};border-radius:10px;box-sizing:border-box;',
                   abs_div(12, 0, 90, h, 'font:600 11px/34px Inter;color:#6B7280;white-space:nowrap', esc(e['label'])))

def pill(e):
    x, y, w, h = e['x'], e['y'], e['w'], e['h']
    return abs_div(x, y, w, h, f'background:#111;border-radius:10px;display:flex;align-items:center;justify-content:center;gap:8px;color:#fff;font:600 13px Inter',
                   icon(e['icon'], 16, '#fff') + esc(e['text']))

def text(e):
    style = f'font:{e["weight"]} {e["size"]}px/1.25 Inter;color:{e["color"]};white-space:nowrap;'
    if e.get('size', 12) >= 20:
        style += 'letter-spacing:-.02em;'
    return abs_div(e['x'], e['y'], e.get('w'), style=style, inner=esc(e['text']))

RENDER = {'shell': shell, 'kpi': kpi, 'banner': banner, 'text': text, 'slicerbox': slicerbox, 'pill': pill,
          'header': lambda e: header()}

def page_html(pg, overlay=False):
    body = [sidebar(pg.active_nav)]
    for e in pg.bg:
        body.append(RENDER[e['t']](e))
    if overlay:  # QA overlay of native visual rectangles
        colors = {'card': '#2563eb', 'spark': '#16a34a', 'line': '#9333ea', 'bar': '#ea580c', 'donut': '#db2777',
                  'table': '#0891b2', 'slicer': '#ca8a04', 'nav': '#dc2626', 'clear': '#dc2626', 'back': '#dc2626'}
        for v in pg.vis:
            x, y, w, h = v['pos']
            body.append(abs_div(x, y, w, h, f'outline:1.5px dashed {colors[v["kind"]]};background:{colors[v["kind"]]}14;box-sizing:border-box',
                                f'<span style="font:600 9px Inter;color:{colors[v["kind"]]};background:#fff">{v["kind"]}</span>'))
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
    html,body{{margin:0;padding:0}} body{{width:{R.W}px;height:{R.H}px;background:{R.C_BG};position:relative;overflow:hidden;
    font-family:Inter,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}}</style></head><body>{''.join(body)}</body></html>'''

if __name__ == '__main__':
    src = OUT / 'html'; src.mkdir(exist_ok=True)
    qa = OUT / 'qa_overlay'; qa.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg_ = b.new_page(viewport={'width': R.W, 'height': R.H}, device_scale_factor=2)
        pg1 = b.new_page(viewport={'width': R.W, 'height': R.H}, device_scale_factor=1)
        for pg in R.PAGES:
            h = page_html(pg)
            (src / f'bg_{pg.key}.html').write_text(h, encoding='utf-8')
            pg_.set_content(h); pg_.wait_for_timeout(150)
            pg_.screenshot(path=str(OUT / f'bg_{pg.key}.png'), full_page=False)
            pg1.set_content(page_html(pg, overlay=True)); pg1.wait_for_timeout(100)
            pg1.screenshot(path=str(qa / f'overlay_{pg.key}.png'))
        b.close()
    print('rendered', len(R.PAGES))
