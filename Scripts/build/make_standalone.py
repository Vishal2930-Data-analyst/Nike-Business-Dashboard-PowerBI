"""Inline all preview assets (scripts, fonts, page backgrounds) into one self-contained HTML file."""
import base64, re, sys
from pathlib import Path
PRE = Path(sys.argv[1]); OUT = Path(sys.argv[2])
html = (PRE / 'index.html').read_text(encoding='utf-8')
a = PRE / 'assets'
def b64(p):
    return base64.b64encode(p.read_bytes()).decode()
fonts = ''.join(f"@font-face{{font-family:Inter;font-weight:{w};src:url(data:font/woff2;base64,{b64(a / f'inter-latin-{w}-normal.woff2')}) format('woff2')}}\n"
                for w in (400, 500, 600, 700, 800))
html = re.sub(r'<!--FONTS-->.*?<!--/FONTS-->', lambda m: fonts, html, flags=re.S)
bgs = {p.stem.replace('bg_', ''): 'data:image/webp;base64,' + b64(p) for p in sorted(a.glob('bg_*.webp'))}
import json
scripts = '<script>window.NIKE_BG=' + json.dumps(bgs) + ';</script>\n'
for name in ['echarts.min.js', 'data.js', 'spec.js', 'engine.js', 'app.js']:
    code = (a / name).read_text(encoding='utf-8').replace('</script', '<\\/script')
    scripts += f'<script>/* {name} */\n{code}\n</script>\n'
html = re.sub(r'<!--SCRIPTS-->.*?<!--/SCRIPTS-->', lambda m: scripts, html, flags=re.S)
OUT.write_text(html, encoding='utf-8')
print(OUT, round(OUT.stat().st_size / 1e6, 2), 'MB')
