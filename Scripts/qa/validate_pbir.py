"""Validate a PBIR report folder against the official Microsoft Fabric JSON schemas
(github.com/microsoft/json-schemas), plus semantic checks:
- every object/property used inside visual 'objects' exists for that visual type in the official
  Power BI report-theme schema (github.com/microsoft/powerbi-desktop-samples)
- every field reference resolves to a column/measure in model.bim
- page navigation targets exist; resource images exist; z-order unique; visuals inside canvas.
Usage: python validate_pbir.py <Report folder> <model.bim> <json-schemas root> <theme schema>"""
import json, sys, re
from pathlib import Path
import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

REPORT, BIM, SCHEMAS, THEME_SCHEMA = map(Path, sys.argv[1:5])
PREFIX = 'https://developer.microsoft.com/json-schemas/'

def retrieve(uri):
    path = SCHEMAS / uri.replace(PREFIX, '')
    return Resource.from_contents(json.loads(path.read_text(encoding='utf-8')), default_specification=DRAFT7)
registry = Registry(retrieve=retrieve)
validators = {}
def validate(doc, schema_uri):
    if schema_uri not in validators:
        schema = retrieve(schema_uri).contents
        validators[schema_uri] = jsonschema.Draft7Validator(schema, registry=registry)
    return list(validators[schema_uri].iter_errors(doc))

results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))

defn = REPORT / 'definition'
files = sorted(defn.rglob('*.json'))
schema_errors = []
for f in files:
    d = json.loads(f.read_text(encoding='utf-8'))
    errs = validate(d, d['$schema'])
    for e in errs[:3]:
        schema_errors.append(f'{f.relative_to(REPORT)} {list(e.path)}: {e.message[:160]}')
check(f'PBIR files valid against official Fabric schemas ({len(files)} files)', not schema_errors, '\n   '.join(schema_errors[:15]))

pbir = json.loads((REPORT / 'definition.pbir').read_text())
errs = validate(dict(pbir, **{'$schema': PREFIX + 'fabric/item/report/definitionProperties/1.0.0/schema.json'}),
                PREFIX + 'fabric/item/report/definitionProperties/1.0.0/schema.json')
check('definition.pbir valid (definitionProperties 1.0.0)', not errs, str(errs[:1]))
plat = json.loads((REPORT / '.platform').read_text())
errs = validate(plat, plat['$schema'])
check('.platform valid (gitIntegration platformProperties 2.0.0)', not errs, str(errs[:1]))

# ---------- semantic checks
bim = json.loads(BIM.read_text(encoding='utf-8'))['model']
fields = {(t['name'], c['name']) for t in bim['tables'] for c in t.get('columns', [])}
fields |= {(t['name'], m['name']) for t in bim['tables'] for m in t.get('measures', [])}
measures = {(t['name'], m['name']) for t in bim['tables'] for m in t.get('measures', [])}

def walk(o, fn):
    if isinstance(o, dict):
        fn(o)
        for v in o.values():
            walk(v, fn)
    elif isinstance(o, list):
        for v in o:
            walk(v, fn)

bad_fields = []
def field_check(o):
    for kind in ('Column', 'Measure'):
        if kind in o and isinstance(o[kind], dict) and 'Property' in o[kind]:
            ent = o[kind]['Expression']['SourceRef'].get('Entity')
            key = (ent, o[kind]['Property'])
            if key not in fields or (kind == 'Measure' and key not in measures):
                bad_fields.append(f'{kind} {ent}[{o[kind]["Property"]}]')
pages = {p.parent.name: json.loads(p.read_text()) for p in (defn / 'pages').glob('*/page.json')}
visuals = {}
for vf in (defn / 'pages').glob('*/visuals/*/visual.json'):
    visuals[vf] = json.loads(vf.read_text(encoding='utf-8'))
for d in list(visuals.values()) + list(pages.values()):
    walk(d, field_check)
check(f'All field references resolve to model columns/measures ({len(visuals)} visuals)', not bad_fields, ', '.join(sorted(set(bad_fields))[:10]))

# theme-schema catalogue of valid objects/properties per visual type
TS = json.loads(THEME_SCHEMA.read_text(encoding='utf-8'))
D = TS['definitions']
def res(n, depth=0):
    while isinstance(n, dict) and '$ref' in n:
        n = D[n['$ref'].split('/')[-1]]
    if isinstance(n, dict) and 'allOf' in n and depth < 5:
        merged = {'properties': {}}
        for part in n['allOf']:
            merged['properties'].update(res(part, depth + 1).get('properties', {}))
        return merged
    return n
def catalog(vt):
    node = res(TS['properties']['visualStyles']['properties'][vt]['properties']['*'])
    out = {}
    for ob, on in node.get('properties', {}).items():
        on = res(on)
        it = res(on.get('items', on))
        out[ob] = {p: res(v) for p, v in it.get('properties', {}).items()}
    return out
cats = {}
bad_props, bad_types = [], []
for vf, d in visuals.items():
    vt = d['visual']['visualType']
    cats.setdefault(vt, catalog(vt))
    for ob, arr in d['visual'].get('objects', {}).items():
        if ob not in cats[vt]:
            bad_props.append(f'{vt}.{ob}')
            continue
        for e in arr:
            for prop, val in e['properties'].items():
                if prop not in cats[vt][ob]:
                    bad_props.append(f'{vt}.{ob}.{prop}')
                    continue
                spec = cats[vt][ob][prop]
                lit = val.get('expr', {}).get('Literal', {}).get('Value') if isinstance(val, dict) else None
                if lit is None:
                    continue
                t = spec.get('type')
                if t == 'integer' and not re.fullmatch(r'-?\d+[LD]', lit):
                    bad_types.append(f'{vt}.{ob}.{prop}={lit} (integer)')
                if t == 'number' and not re.fullmatch(r'-?[\d.]+[DL]', lit):
                    bad_types.append(f'{vt}.{ob}.{prop}={lit} (number)')
                if t == 'boolean' and lit not in ('true', 'false'):
                    bad_types.append(f'{vt}.{ob}.{prop}={lit} (boolean)')
                if t == 'string' and not lit.startswith("'"):
                    bad_types.append(f'{vt}.{ob}.{prop}={lit} (string)')
                enum = spec.get('enum') or [x.get('const') for x in spec.get('anyOf', []) if isinstance(x, dict) and 'const' in x]
                if enum and lit.startswith("'") and lit.strip("'") not in enum:
                    bad_types.append(f'{vt}.{ob}.{prop}={lit} not in {enum[:8]}')
check('Visual formatting objects/properties exist for each visual type (official theme schema catalogue)',
      not bad_props, ', '.join(sorted(set(bad_props))))
check('Formatting literal types match the catalogue (integer/number/boolean/string/enum)', not bad_types,
      ', '.join(sorted(set(bad_types))[:12]))

# navigation & resources
page_names = set(pages)
order = json.loads((defn / 'pages' / 'pages.json').read_text())['pageOrder']
check('pages.json pageOrder matches page folders', set(order) == page_names and len(order) == len(page_names))
nav_bad = []
for vf, d in visuals.items():
    for e in d['visual'].get('visualContainerObjects', {}).get('visualLink', []):
        ns = e['properties'].get('navigationSection')
        if ns and ns['expr']['Literal']['Value'].strip("'") not in page_names:
            nav_bad.append(str(vf))
check('Every page-navigation button targets an existing page', not nav_bad)
rep = json.loads((defn / 'report.json').read_text())
items = [i for pkg in rep['resourcePackages'] for i in pkg['items']]
missing = [i['path'] for pkg in rep['resourcePackages'] for i in pkg['items']
           if not (REPORT / 'StaticResources' / pkg['name'] / i['path']).exists()]
check('All registered resources (theme, base theme, page images) exist on disk', not missing, str(missing))
reg_names = {i['name'] for i in items}
img_bad = []
for pg in pages.values():
    walk(pg, lambda o: img_bad.append(o['ResourcePackageItem']['ItemName'])
         if 'ResourcePackageItem' in o and o['ResourcePackageItem']['ItemName'] not in reg_names else None)
check('Page background images are registered in report.json', not img_bad, str(img_bad))

geo_bad, z_bad = [], []
by_page = {}
for vf, d in visuals.items():
    p = d['position']; pg = vf.parent.parent.parent.name
    if p['x'] < 0 or p['y'] < 0 or p['x'] + p['width'] > pages[pg]['width'] + 0.5 or p['y'] + p['height'] > pages[pg]['height'] + 0.5:
        geo_bad.append(f'{pages[pg]["displayName"]}:{d["name"]}')
    by_page.setdefault(pg, []).append(p['z'])
for pg, zs in by_page.items():
    if len(zs) != len(set(zs)):
        z_bad.append(pg)
check('All visuals lie inside the 1600x900 canvas', not geo_bad, ', '.join(geo_bad[:5]))
check('z-order unique per page', not z_bad)
names = [d['name'] for d in visuals.values()]
check('Visual names unique and <= 50 chars', len(names) == len(set(names)) and all(len(n) <= 50 for n in names))

ok = all(r[1] for r in results)
for n, passed, det in results:
    print(('PASS' if passed else 'FAIL') + ': ' + n + (('\n   ' + det) if det and not passed else ''))
sys.exit(0 if ok else 1)
