"""Writes the Power BI semantic model (TMSL model.bim inside a PBIP SemanticModel folder)
plus Power_Query_M_Code.txt and DAX_Measures.txt."""
import json, sys, uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import model_def as md

OUT = Path(sys.argv[1])            # .../PowerBI
NAME = 'Nike_Business_Dashboard'
SM = OUT / f'{NAME}.SemanticModel'
NS = uuid.UUID('6f1c2b8e-1d2a-4b7c-9a51-2e0c8f3d9a10')
def tag(*parts):
    return str(uuid.uuid5(NS, '|'.join(parts)))

def mlit(v):
    return '"' + v.replace('"', '""') + '"'

def lines(s):
    return s.split('\n')

def column(t, c):
    col = {'name': c['name'], 'dataType': c['dtype'], 'lineageTag': tag(t, c['name']),
           'sourceColumn': c['name'], 'summarizeBy': c.get('summ', 'none')}
    if c.get('fmt'):
        col['formatString'] = c['fmt']
    if c.get('hidden'):
        col['isHidden'] = True
    if c.get('sortBy'):
        col['sortByColumn'] = c['sortBy']
    if c.get('dataCategory'):
        col['dataCategory'] = c['dataCategory']
    ann = [{'name': 'SummarizationSetBy', 'value': 'User'}]
    if c['dtype'] == 'dateTime':
        ann.append({'name': 'UnderlyingDateTimeDataType', 'value': 'Date'})
    col['annotations'] = ann
    return col

tables = []
for t in md.TABLES:
    cols = [column(t['name'], c) for c in t['columns'] + t['extra_cols'] if c.get('model', True)]
    if t['date_table']:
        for c in cols:
            if c['name'] == 'Date':
                c['isKey'] = True
    for cc in t['calc_cols']:
        cols.append({'type': 'calculated', 'name': cc['name'], 'dataType': cc['dtype'], 'isDataTypeInferred': False,
                     'expression': cc['expr'], 'formatString': cc['fmt'], 'lineageTag': tag(t['name'], cc['name']),
                     'summarizeBy': 'none', 'description': cc['desc'],
                     'annotations': [{'name': 'SummarizationSetBy', 'value': 'User'},
                                     {'name': 'UnderlyingDateTimeDataType', 'value': 'Date'}]})
    tb = {'name': t['name'], 'description': t['desc'], 'lineageTag': tag(t['name']), 'columns': cols,
          'partitions': [{'name': t['name'], 'mode': 'import',
                          'source': {'type': 'm', 'expression': lines(md.m_query(t))}}],
          'annotations': [{'name': 'PBI_ResultType', 'value': 'Table'}]}
    if t['date_table']:
        tb['dataCategory'] = 'Time'
    if t['hierarchies']:
        tb['hierarchies'] = [{'name': h, 'lineageTag': tag(t['name'], 'h', h),
                              'levels': [{'name': lv, 'ordinal': i, 'column': lv, 'lineageTag': tag(t['name'], h, lv)}
                                         for i, lv in enumerate(levels)]}
                             for h, levels in t['hierarchies']]
    tables.append(tb)

measures = []
for m in md.MEASURES:
    me = {'name': m['name'], 'expression': lines(m['expr']), 'displayFolder': m['folder'],
          'lineageTag': tag('_Measures', m['name'])}
    if m['fmt']:
        me['formatString'] = m['fmt']
        if '$' in m['fmt']:
            me['annotations'] = [{'name': 'PBI_FormatHint', 'value': '{"currencyCulture":"en-US"}'}]
    if m['desc']:
        me['description'] = m['desc']
    measures.append(me)

tables.append({'name': '_Measures', 'description': 'Dedicated measure table. All report KPIs live here.',
               'lineageTag': tag('_Measures'),
               'columns': [{'type': 'calculatedTableColumn', 'name': 'Value', 'dataType': 'int64', 'isHidden': True,
                            'isNameInferred': True, 'isDataTypeInferred': True, 'sourceColumn': '[Value]',
                            'formatString': '0', 'summarizeBy': 'none', 'lineageTag': tag('_Measures', 'Value'),
                            'annotations': [{'name': 'SummarizationSetBy', 'value': 'User'}]}],
               'measures': measures,
               'partitions': [{'name': '_Measures', 'mode': 'import', 'source': {'type': 'calculated', 'expression': '{0}'}}]})

rels = []
for ft, fc, tt, tc, active in md.RELATIONSHIPS:
    r = {'name': tag('rel', ft, fc, tt), 'fromTable': ft, 'fromColumn': fc, 'toTable': tt, 'toColumn': tc}
    if not active:
        r['isActive'] = False
    rels.append(r)

expressions = [{'name': 'DataFolder', 'kind': 'm', 'lineageTag': tag('expr', 'DataFolder'),
                'description': 'Folder that contains the supplied CSV files (end with a backslash).',
                'expression': mlit(md.DEFAULT_DATA_FOLDER) +
                ' meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
                'annotations': [{'name': 'PBI_ResultType', 'value': 'Text'}]}]
for fn, code in md.M_FUNCTIONS.items():
    expressions.append({'name': fn, 'kind': 'm', 'lineageTag': tag('expr', fn), 'expression': lines(code),
                        'annotations': [{'name': 'PBI_ResultType', 'value': 'Function'}]})

query_order = ['DataFolder'] + list(md.M_FUNCTIONS) + [t['name'] for t in md.TABLES]
model = {'compatibilityLevel': 1567, 'model': {
    'culture': 'en-US', 'defaultPowerBIDataSourceVersion': 'powerBI_V3', 'discourageImplicitMeasures': True,
    'sourceQueryCulture': 'en-US', 'dataAccessOptions': {'legacyRedirects': True, 'returnErrorValuesAsNull': True},
    'tables': tables, 'relationships': rels, 'expressions': expressions,
    'annotations': [{'name': '__PBI_TimeIntelligenceEnabled', 'value': '0'},
                    {'name': 'PBI_QueryOrder', 'value': json.dumps(query_order)},
                    {'name': 'PBIDesktopVersion', 'value': '2.140.1454.0 (25.02)'}]}}

SM.mkdir(parents=True, exist_ok=True)
(SM / '.pbi').mkdir(exist_ok=True)
(SM / 'model.bim').write_text(json.dumps(model, indent=2, ensure_ascii=False), encoding='utf-8')
(SM / 'definition.pbism').write_text(json.dumps({'version': '4.1', 'settings': {}}, indent=2), encoding='utf-8')
(SM / '.platform').write_text(json.dumps({
    '$schema': 'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json',
    'metadata': {'type': 'SemanticModel', 'displayName': NAME},
    'config': {'version': '2.0', 'logicalId': tag('logical', 'model')}}, indent=2), encoding='utf-8')
(SM / '.pbi' / 'editorSettings.json').write_text(json.dumps({
    'version': '1.0', 'autodetectRelationships': False, 'parallelQueryLoading': True,
    'relationshipImportEnabled': True, 'shouldNotifyUserOfNameConflictResolution': True}, indent=2), encoding='utf-8')

# ---------------- human-readable exports
pq = ['// ==========================================================================',
      '// Nike Business Dashboard - Power Query (M) code',
      '// Exactly the queries embedded in Nike_Business_Dashboard.SemanticModel/model.bim',
      '// Synthetic demonstration data - not official Nike business figures.',
      '// ==========================================================================', '',
      '// ---- Parameter: DataFolder (Home > Transform data > Manage parameters)',
      f'DataFolder = {mlit(md.DEFAULT_DATA_FOLDER)} meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]', '']
for fn, code in md.M_FUNCTIONS.items():
    pq += [f'// ---- Function: {fn}', f'{fn} =', code, '']
for t in md.TABLES:
    pq += [f'// ---- Query: {t["name"]}' + (f'  (source file: {t["file"]})' if t['file'] else '  (generated calendar)'),
           f'// {t["desc"]}', f'{t["name"]} =', md.m_query(t), '']
(OUT / 'Power_Query_M_Code.txt').write_text('\n'.join(pq), encoding='utf-8')

dx = ['// ==========================================================================',
      '// Nike Business Dashboard - DAX measures (table: _Measures)',
      f'// {len(md.MEASURES)} measures, grouped by display folder. Identical to model.bim.',
      '// Synthetic demonstration data - not official Nike business figures.',
      '// ==========================================================================', '',
      '// ---- Calculated column (DimCustomer)']
for t in md.TABLES:
    for cc in t['calc_cols']:
        dx += [f'// {cc["desc"]}', f"{t['name']}[{cc['name']}] =", '    ' + cc['expr'], '']
folder = None
for m in md.MEASURES:
    if m['folder'] != folder:
        folder = m['folder']
        dx += ['', '// ' + '=' * 70, f'// {folder}', '// ' + '=' * 70, '']
    if m['desc']:
        dx.append(f'// {m["desc"]}')
    if m['fmt']:
        dx.append(f'// Format string: {m["fmt"]}')
    body = m['expr'] if m['expr'].startswith('\n') or '\n' in m['expr'] else m['expr']
    dx.append(f"[{m['name']}] =")
    dx += ['    ' + l for l in body.strip('\n').split('\n')]
    dx.append('')
(OUT / 'DAX_Measures.txt').write_text('\n'.join(dx), encoding='utf-8')
print('model written:', len(tables), 'tables,', len(measures), 'measures,', len(rels), 'relationships')
