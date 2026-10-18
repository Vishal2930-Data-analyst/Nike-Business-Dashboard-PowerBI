"""Static validation of model.bim: DAX column/measure references, bracket balance,
relationship columns, sortBy columns, M column references vs CSV headers.
Usage: python check_model.py <model.bim> <DataFolder>  -> prints PASS/FAIL lines, exit 1 on failure."""
import json, re, sys, csv
from pathlib import Path

bim = json.load(open(sys.argv[1], encoding='utf-8'))
data = Path(sys.argv[2])
model = bim['model']
cols = {t['name']: {c['name'] for c in t.get('columns', [])} for t in model['tables']}
measures = {m['name'] for t in model['tables'] for m in t.get('measures', [])}
results = []
def check(name, ok, detail=''):
    results.append((name, ok, detail))

def strip_strings(expr):
    return re.sub(r'"(?:[^"]|"")*"', '""', expr)

colref = re.compile(r"(?:'([^']+)'|\b([A-Za-z_][A-Za-z0-9_]*))\[([^\]]+)\]")
bad = []
def dax_items():
    for t in model['tables']:
        for m in t.get('measures', []):
            yield f"measure [{m['name']}]", '\n'.join(m['expression']) if isinstance(m['expression'], list) else m['expression']
        for c in t.get('columns', []):
            if c.get('type') == 'calculated':
                yield f"column {t['name']}[{c['name']}]", c['expression']

n = 0
for label, expr in dax_items():
    n += 1
    e = strip_strings(expr)
    if e.count('(') != e.count(')') or e.count('[') != e.count(']') or e.count('{') != e.count('}'):
        bad.append(f'{label}: unbalanced brackets')
    spans = []
    for mo in colref.finditer(e):
        tbl = mo.group(1) or mo.group(2)
        col = mo.group(3)
        spans.append(mo.span(3))
        if tbl not in cols:
            bad.append(f'{label}: unknown table {tbl}')
        elif col not in cols[tbl]:
            bad.append(f'{label}: unknown column {tbl}[{col}]')
    covered = set()
    for a, b in spans:
        covered.update(range(a - 1, b + 1))
    for mo in re.finditer(r'\[([^\]]+)\]', e):
        if mo.start() in covered:
            continue
        if mo.group(1) not in measures:
            bad.append(f'{label}: unknown measure [{mo.group(1)}]')
check(f'DAX references resolve ({n} expressions)', not bad, '; '.join(bad[:10]))

# measure names unique and not clashing with columns
allm = [m['name'] for t in model['tables'] for m in t.get('measures', [])]
check('Measure names unique', len(allm) == len(set(allm)))
check('Every measure has a format string or is text', all(
    m.get('formatString') or 'Label' in m['name'] or 'Text' in m['name'] or 'Color' in m['name'] or 'Disclaimer' in m['name']
    for t in model['tables'] for m in t.get('measures', [])))

# relationships
rbad = [f"{r['fromTable']}[{r['fromColumn']}]->{r['toTable']}[{r['toColumn']}]" for r in model['relationships']
        if r['fromColumn'] not in cols.get(r['fromTable'], ()) or r['toColumn'] not in cols.get(r['toTable'], ())]
check('Relationship columns exist', not rbad, ', '.join(rbad))
active = {}
for r in model['relationships']:
    if r.get('isActive', True):
        key = (r['fromTable'], r['toTable'])
        active[key] = active.get(key, 0) + 1
check('At most one active relationship per table pair', all(v == 1 for v in active.values()))

# sortBy
sb = [f"{t['name']}[{c['name']}]" for t in model['tables'] for c in t.get('columns', [])
      if c.get('sortByColumn') and c['sortByColumn'] not in cols[t['name']]]
check('sortByColumn targets exist', not sb, ', '.join(sb))

# date table
dt = [t for t in model['tables'] if t.get('dataCategory') == 'Time']
check('Exactly one table marked as Date table with a key Date column',
      len(dt) == 1 and any(c.get('isKey') and c['dataType'] == 'dateTime' for c in dt[0]['columns']))

# M: column names referenced in TransformColumnTypes / fnRequireColumns exist in CSV headers
mbad = []
for t in model['tables']:
    for p in t.get('partitions', []):
        if p['source']['type'] != 'm':
            continue
        code = '\n'.join(p['source']['expression'])
        f = re.search(r'fnLoadCsv\("([^"]+)"\)', code)
        if not f:
            continue
        header = next(csv.reader(open(data / f.group(1), encoding='utf-8-sig')))
        req = re.search(r'fnRequireColumns\(Source, \{([^}]*)\}', code).group(1)
        names = re.findall(r'"([^"]+)"', req)
        missing = [x for x in names if x not in header]
        if missing:
            mbad.append(f"{t['name']}: {missing}")
        typed = re.findall(r'\{"([^"]+)", (?:type \w+|Int64\.Type)\}', code)
        if set(typed) != set(names):
            mbad.append(f"{t['name']}: typed columns differ from required columns")
        # model source columns must be produced by the query
        produced = set(names) | set(re.findall(r'Table\.AddColumn\([^,]+, "([^"]+)"', code))
        for old, new in re.findall(r'\{"([^"]+)", "([^"]+)"\}', ' '.join(re.findall(r'Table\.RenameColumns\([^,]+, \{(.*?)\}\)', code))):
            produced.discard(old); produced.add(new)
        for c in t['columns']:
            if c.get('type') in ('calculated', 'calculatedTableColumn'):
                continue
            if c['sourceColumn'] not in produced:
                mbad.append(f"{t['name']}[{c['name']}] not produced by M")
check('Power Query columns match CSV headers and model columns', not mbad, '; '.join(mbad))

ok = all(r[1] for r in results)
for name, passed, detail in results:
    print(('PASS' if passed else 'FAIL') + f': {name}' + (f' -- {detail}' if detail and not passed else ''))
sys.exit(0 if ok else 1)
