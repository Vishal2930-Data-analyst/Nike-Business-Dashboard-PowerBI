"""Emit the PBIR report folder (Nike_Business_Dashboard.Report) from report_def.PAGES."""
import json, sys, hashlib, shutil, uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import report_def as R
import model_def as MD

OUT = Path(sys.argv[1])                 # .../PowerBI
BG_DIR = Path(sys.argv[2])              # rendered background PNGs (bg_<key>.png)
BASE_THEME = Path(sys.argv[3])          # CY24SU10.json
THEME = Path(sys.argv[4])               # Nike_Business_Theme.json
NAME = 'Nike_Business_Dashboard'
RP = OUT / f'{NAME}.Report'
DEF = RP / 'definition'
SCHEMA = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition'
VC_SCHEMA = f'{SCHEMA}/visualContainer/1.5.0/schema.json'
FONT = "'''Segoe UI'', wf_segoe-ui_normal, helvetica, arial, sans-serif'"
FONT_SB = "'''Segoe UI Semibold'', wf_segoe-ui_semibold, helvetica, arial, sans-serif'"
FONT_B = "'''Segoe UI Bold'', wf_segoe-ui_bold, helvetica, arial, sans-serif'"

MEASURES = {mm['name'] for mm in MD.MEASURES}
COLUMNS = {(t['name'], c['name']) for t in MD.TABLES for c in t['columns'] + t['extra_cols'] + t['calc_cols']}

# ------------------------------------------------------------- literal helpers
def L(v):
    if isinstance(v, bool):
        s = 'true' if v else 'false'
    elif isinstance(v, int) and not isinstance(v, bool):
        s = f'{v}D'
    elif isinstance(v, float):
        s = f'{v:g}D'
    else:
        s = "'" + str(v).replace("'", "''") + "'"
    return {'expr': {'Literal': {'Value': s}}}
def LL(n):
    return {'expr': {'Literal': {'Value': f'{int(n)}L'}}}
def RAW(s):
    return {'expr': {'Literal': {'Value': s}}}
def COL(hex_):
    return {'solid': {'color': L(hex_)}}
def MCOL(measure):
    assert measure in MEASURES, measure
    return {'solid': {'color': {'expr': {'Measure': {'Expression': {'SourceRef': {'Entity': '_Measures'}}, 'Property': measure}}}}}
def obj(props, selector=None):
    o = {'properties': props}
    if selector:
        o['selector'] = selector
    return o

def fexpr(f):
    t, n, kind, _ = f
    if kind == 'M':
        assert n in MEASURES, f'unknown measure {n}'
        return {'Measure': {'Expression': {'SourceRef': {'Entity': t}}, 'Property': n}}
    assert (t, n) in COLUMNS, f'unknown column {t}[{n}]'
    return {'Column': {'Expression': {'SourceRef': {'Entity': t}}, 'Property': n}}
def qref(f):
    return f'{f[0]}.{f[1]}'
def proj(f, active=None):
    p = {'field': fexpr(f), 'queryRef': qref(f), 'nativeQueryRef': f[3] or f[1]}
    if f[3]:
        p['displayName'] = f[3]
    if active is not None:
        p['active'] = active
    return p
def sort(f, direction='Descending'):
    return {'sort': [{'field': fexpr(f), 'direction': direction}], 'isDefaultSort': False}
def scope(f, value):
    return {'data': [{'scopeId': {'Comparison': {'ComparisonKind': 0, 'Left': fexpr(f), 'Right': {'Literal': {'Value': "'" + value.replace("'", "''") + "'"}}}}}]}
WILD = {'data': [{'dataViewWildcard': {'matchingOption': 1}}]}

def vco(header=False, tooltip_bg=True, title=None):
    o = {'title': [obj({'show': L(False)})] if not title else [obj({'show': L(True), 'text': L(title)})],
         'background': [obj({'show': L(False)})],
         'border': [obj({'show': L(False)})],
         'dropShadow': [obj({'show': L(False)})],
         'padding': [obj({'top': L(0), 'bottom': L(0), 'left': L(0), 'right': L(0)})],
         'visualHeader': [obj({'show': L(header)})]}
    if tooltip_bg:
        o['visualTooltip'] = [obj({'background': COL('#FFFFFF'), 'titleFontColor': COL(R.C_TEXT2),
                                   'valueFontColor': COL(R.C_TEXT), 'fontSize': L(9)})]
    return o

def axis_common(font=9, color=R.C_TEXT2):
    return {'fontSize': L(font), 'labelColor': COL(color), 'fontFamily': L(FONT.strip("'")) if False else RAW(FONT),
            'showAxisTitle': L(False)}

# ------------------------------------------------------------- visual builders
def v_card(v):
    props = {'fontSize': L(float(v['size'])), 'fontFamily': RAW(FONT_B if v.get('bold') else FONT),
             'color': MCOL(v['color_measure'][1]) if v.get('color_measure') else COL(v['color'])}
    if v.get('units') is not None and v['field'][1] not in ('',):
        props['labelDisplayUnits'] = L(int(v.get('units', 0)))
        props['labelPrecision'] = LL(v.get('precision', 0))
    objects = {'labels': [obj(props)],
               'categoryLabels': [obj({'show': L(bool(v.get('category'))), 'color': COL(R.C_TEXT2), 'fontSize': L(8),
                                       'fontFamily': RAW(FONT)})],
               'wordWrap': [obj({'show': L(False)})]}
    return {'visualType': 'card',
            'query': {'queryState': {'Values': {'projections': [proj(v['field'])]}}},
            'objects': objects, 'visualContainerObjects': vco(), 'drillFilterOtherVisuals': True}

def v_spark(v):
    return {'visualType': 'lineChart',
            'query': {'queryState': {'Category': {'projections': [proj(R.MONTH, True)]},
                                     'Y': {'projections': [proj(v['field'])]}}},
            'objects': {'categoryAxis': [obj({'show': L(False), 'gridlineShow': L(False)})],
                        'valueAxis': [obj({'show': L(False), 'gridlineShow': L(False)})],
                        'legend': [obj({'show': L(False)})],
                        'labels': [obj({'show': L(False)})],
                        'lineStyles': [obj({'strokeWidth': L(2), 'showMarker': L(False)})],
                        'dataPoint': [obj({'fill': COL('#9CA3AF')})]},
            'visualContainerObjects': vco(), 'drillFilterOtherVisuals': True}

def v_line(v):
    # optional drill levels above the displayed level (e.g. Quarter > Month = monthly/quarterly toggle via drill up/down)
    qs = {'Category': {'projections': [proj(d, False) for d in v.get('drill', [])] + [proj(v['cat'], True)]},
          'Y': {'projections': [proj(f) for f in v['y']]}}
    if v['tooltips']:
        qs['Tooltips'] = {'projections': [proj(f) for f in v['tooltips']]}
    va = axis_common()
    va.update({'show': L(True), 'gridlineShow': L(True), 'gridlineColor': COL('#E7E9ED'), 'gridlineStyle': L('dashed')})
    if v.get('units'):
        va['labelDisplayUnits'] = L(int(v['units']))
    ca = axis_common()
    ca.update({'show': L(True), 'gridlineShow': L(False)})
    dp = []
    if v.get('colors'):
        for f in v['y']:
            dp.append(obj({'fill': COL(v['colors'][f[1]])}, {'metadata': qref(f)}))
    else:
        dp.append(obj({'fill': COL(R.C_TEXT)}))
    objects = {'categoryAxis': [obj(ca)], 'valueAxis': [obj(va)],
               'legend': [obj({'show': L(bool(v.get('legend'))), 'position': L('Top'), 'fontSize': L(9),
                               'labelColor': COL(R.C_TEXT2), 'showTitle': L(False)})],
               'labels': [obj({'show': L(False)})],
               'lineStyles': [obj({'strokeWidth': L(3), 'showMarker': L(True), 'markerSize': L(4)})],
               'dataPoint': dp}
    return {'visualType': 'lineChart', 'query': {'queryState': qs, 'sortDefinition': sort(v['cat'], 'Ascending')},
            'objects': objects, 'visualContainerObjects': vco(header=True), 'drillFilterOtherVisuals': True}

def v_bar(v):
    chart = v.get('chart', 'barChart')
    qs = {'Category': {'projections': [proj(v['cat'], True)]},
          'Y': {'projections': [proj(f) for f in v['y']]}}
    if v['tooltips']:
        qs['Tooltips'] = {'projections': [proj(f) for f in v['tooltips']]}
    ca = axis_common(v.get('cat_font', 9), R.C_TEXT)
    ca.update({'show': L(True), 'innerPadding': LL(30 if chart != 'clusteredBarChart' else 22),
               'maxMarginFactor': LL(40), 'concatenateLabels': L(False)})
    va = {'show': L(False), 'gridlineShow': L(False), 'showAxisTitle': L(False)}
    lab = {'show': L(v.get('labels', True) is not False), 'fontSize': L(8 if v.get('cat_font') else 9), 'color': COL(R.C_TEXT), 'fontFamily': RAW(FONT)}
    if v.get('units'):
        lab['labelDisplayUnits'] = L(int(v['units']))
        lab['labelPrecision'] = LL(1)
    dp = []
    if v.get('colors'):
        for k, col in v['colors'].items():
            dp.append(obj({'fill': COL(col)}, scope(v['cat'], k)))
    elif v.get('color_measure'):
        dp.append(obj({'fill': COL(R.C_TEXT)}))
        dp.append(obj({'fill': MCOL(v['color_measure'][1])}, WILD))
    elif v.get('series_colors'):
        for f in v['y']:
            dp.append(obj({'fill': COL(v['series_colors'][f[1]])}, {'metadata': qref(f)}))
    else:
        dp.append(obj({'fill': COL(v.get('single_color') or R.C_TEXT)}))
    objects = {'categoryAxis': [obj(ca)], 'valueAxis': [obj(va)], 'labels': [obj(lab)],
               'legend': [obj({'show': L(bool(v.get('legend'))), 'position': L('Top'), 'fontSize': L(9),
                               'labelColor': COL(R.C_TEXT2), 'showTitle': L(False)})],
               'dataPoint': dp}
    if chart in ('barChart', 'columnChart'):
        objects['totals'] = [obj({'show': L(False)})]
    sort_field = v['cat'] if (v['cat'][1] in ('Month Short', 'Quarter', 'Age_Group')) else v['y'][0]
    direction = 'Ascending' if sort_field is v['cat'] else 'Descending'
    return {'visualType': chart, 'query': {'queryState': qs, 'sortDefinition': sort(sort_field, direction)},
            'objects': objects, 'visualContainerObjects': vco(header=True), 'drillFilterOtherVisuals': True}

def v_donut(v):
    qs = {'Category': {'projections': [proj(v['cat'], True)]}, 'Y': {'projections': [proj(v['y'])]}}
    if v['tooltips']:
        qs['Tooltips'] = {'projections': [proj(f) for f in v['tooltips']]}
    objects = {'legend': [obj({'show': L(bool(v['legend'])), 'position': L('BottomCenter'), 'fontSize': L(8),
                               'labelColor': COL(R.C_TEXT2), 'showTitle': L(False)})],
               'labels': [obj({'show': L(bool(v['legend'])), 'labelStyle': L('Percent of total'), 'fontSize': L(8),
                               'color': COL(R.C_TEXT), 'position': L('preferOutside'), 'labelPrecision': LL(0)})],
               'slices': [obj({'innerRadiusRatio': LL(66)})],
               'dataPoint': [obj({'fill': COL(col)}, scope(v['cat'], k)) for k, col in v['colors'].items()]}
    return {'visualType': 'donutChart', 'query': {'queryState': qs, 'sortDefinition': sort(v['y'])},
            'objects': objects, 'visualContainerObjects': vco(header=True), 'drillFilterOtherVisuals': True}

def v_table(v):
    projs = [proj(f) for f in v['columns']]
    for pj, f in zip(projs, v['columns']):
        if v.get('formats', {}).get(f[1]) == 'K':
            pj['format'] = '\\$#,0,"K"'      # visual-level format string: thousands, e.g. $160K
    f = v['font']
    objects = {
        'columnHeaders': [obj({'fontSize': L(f), 'fontColor': COL(R.C_TEXT2), 'backColor': COL('#FFFFFF'),
                               'fontFamily': RAW(FONT_SB), 'wordWrap': L(False)})],
        'values': [obj({'fontSize': L(f), 'fontColorPrimary': COL(R.C_TEXT), 'fontColorSecondary': COL(R.C_TEXT),
                        'backColorPrimary': COL('#FFFFFF'), 'backColorSecondary': COL('#FFFFFF'),
                        'fontFamily': RAW(FONT), 'wordWrap': L(False)})],
        'grid': [obj({'gridHorizontal': L(True), 'gridHorizontalColor': COL('#EEF0F3'), 'gridVertical': L(False),
                      'outlineColor': COL('#E7E9ED'), 'rowPadding': L(2)})],
        'total': [obj({'totals': L(bool(v['totals'])), 'fontSize': L(f), 'fontColor': COL(R.C_TEXT)})],
        'columnWidth': [obj({'value': L(float(w))}, {'metadata': qref(col)}) for col, w in zip(v['columns'], v['widths'])],
    }
    for key, measure in v['color_rules'].items():
        target = next(col for col in v['columns'] if col[1] == key or qref(col) == key)
        objects['values'].append(obj({'fontColor': MCOL(measure)}, {'data': [{'dataViewWildcard': {'matchingOption': 1}}],
                                                                   'metadata': qref(target)}))
    return {'visualType': 'tableEx',
            'query': {'queryState': {'Values': {'projections': projs}}, 'sortDefinition': sort(v['sort'], v['sort_dir'])},
            'objects': objects, 'visualContainerObjects': vco(header=True), 'drillFilterOtherVisuals': True}

def v_slicer(v):
    objects = {'data': [obj({'mode': L(v['mode'])})],
               'header': [obj({'show': L(False)})],
               'items': [obj({'fontColor': COL(R.C_TEXT), 'textSize': L(10), 'fontFamily': RAW(FONT),
                              'background': COL('#FFFFFF')})],
               'general': [obj({'selfFilterEnabled': L(bool(v.get('search')))})]}
    if v['mode'] == 'Between':
        objects['date'] = [obj({'textSize': L(10), 'fontColor': COL(R.C_TEXT), 'fontFamily': RAW(FONT)})]
        objects['slider'] = [obj({'show': L(False)})]
    o = {'visualType': 'slicer',
         'query': {'queryState': {'Values': {'projections': [proj(v['field'], True)]}},
                   'sortDefinition': sort(v['field'], 'Ascending')},
         'objects': objects, 'visualContainerObjects': vco(), 'drillFilterOtherVisuals': True}
    if v.get('sync'):
        o['syncGroup'] = {'groupName': v['sync'], 'fieldChanges': True, 'filterChanges': True}
    return o

def v_button(link):
    o = vco()
    o['visualLink'] = [obj(link)]
    return {'visualType': 'actionButton',
            'objects': {'icon': [obj({'shapeType': L('blank')}, {'id': 'default'}), obj({'show': L(False)})],
                        'text': [obj({'show': L(False)})],
                        'outline': [obj({'show': L(False)})],
                        'fill': [obj({'show': L(False)})]},
            'visualContainerObjects': o, 'drillFilterOtherVisuals': True}

def v_nav(v):
    target = R.PAGE_BY_KEY[v['target']].name
    return v_button({'show': L(True), 'type': L('PageNavigation'), 'navigationSection': L(target),
                     'tooltip': L(v.get('tip', ''))})
def v_clear(v):
    return v_button({'show': L(True), 'type': L('ClearAllSlicers'), 'tooltip': L('Reset all slicers')})
def v_back(v):
    return v_button({'show': L(True), 'type': L('Back'), 'tooltip': L('Back to previous page')})

BUILD = {'card': v_card, 'spark': v_spark, 'line': v_line, 'bar': v_bar, 'donut': v_donut, 'table': v_table,
         'slicer': v_slicer, 'nav': v_nav, 'clear': v_clear, 'back': v_back}

# ------------------------------------------------------------- write
if RP.exists():
    shutil.rmtree(RP)
(DEF / 'pages').mkdir(parents=True)
reg = RP / 'StaticResources' / 'RegisteredResources'
shared = RP / 'StaticResources' / 'SharedResources' / 'BaseThemes'
reg.mkdir(parents=True); shared.mkdir(parents=True)
shutil.copy(BASE_THEME, shared / 'CY24SU10.json')
shutil.copy(THEME, reg / 'Nike_Business_Theme.json')

items = [{'name': 'Nike_Business_Theme.json', 'path': 'Nike_Business_Theme.json', 'type': 'CustomTheme'}]
bg_names = {}
for pg in R.PAGES:
    src = BG_DIR / f'bg_{pg.key}.png'
    suffix = int(hashlib.md5(src.read_bytes()).hexdigest()[:12], 16) % 10**14
    nm = f'bg_{pg.key}{suffix:014d}.png'
    shutil.copy(src, reg / nm)
    bg_names[pg.key] = nm
    items.append({'name': nm, 'path': nm, 'type': 'Image'})

report = {
    '$schema': f'{SCHEMA}/report/1.2.0/schema.json',
    'themeCollection': {
        'baseTheme': {'name': 'CY24SU10', 'reportVersionAtImport': '5.61', 'type': 'SharedResources'},
        'customTheme': {'name': 'Nike_Business_Theme.json', 'reportVersionAtImport': '5.61', 'type': 'RegisteredResources'}},
    'layoutOptimization': 'None',
    'objects': {'section': [obj({'verticalAlignment': L('Top')})],
                'outspacePane': [obj({'visible': L(True), 'expanded': L(False)})]},
    'resourcePackages': [
        {'name': 'RegisteredResources', 'type': 'RegisteredResources', 'items': items},
        {'name': 'SharedResources', 'type': 'SharedResources',
         'items': [{'name': 'CY24SU10', 'path': 'BaseThemes/CY24SU10.json', 'type': 'BaseTheme'}]}],
    'settings': {'useStylableVisualContainerHeader': True, 'defaultDrillFilterOtherVisuals': True,
                 'allowChangeFilterTypes': True, 'useEnhancedTooltips': True, 'useDefaultAggregateDisplayName': True},
    'slowDataSourceSettings': {'isCrossHighlightingDisabled': False, 'isSlicerSelectionsButtonEnabled': False,
                               'isFilterSelectionsButtonEnabled': False, 'isFieldWellButtonEnabled': False,
                               'isApplyAllButtonEnabled': False}}

def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

dump(DEF / 'report.json', report)
dump(DEF / 'version.json', {'$schema': f'{SCHEMA}/versionMetadata/1.0.0/schema.json', 'version': '2.0.0'})
dump(DEF / 'pages' / 'pages.json', {'$schema': f'{SCHEMA}/pagesMetadata/1.0.0/schema.json',
                                    'pageOrder': [pg.name for pg in R.PAGES], 'activePageName': R.PAGES[0].name})
manifest = []
for pg in R.PAGES:
    page = {'$schema': f'{SCHEMA}/page/1.3.0/schema.json', 'name': pg.name, 'displayName': pg.display,
            'displayOption': 'FitToPage', 'height': R.H, 'width': R.W,
            'objects': {'background': [obj({'image': {'image': {'name': L(f'bg_{pg.key}.png'),
                                                                'url': {'expr': {'ResourcePackageItem': {
                                                                    'PackageName': 'RegisteredResources', 'PackageType': 1,
                                                                    'ItemName': bg_names[pg.key]}}},
                                                                'scaling': L('Fit')}},
                                               'transparency': L(0)})],
                        'outspace': [obj({'color': COL(R.C_BG)})]}}
    if pg.hidden:
        page['visibility'] = 'HiddenInViewMode'
    if pg.drill_field:
        fname = f'Drill_{pg.key}'
        page['filterConfig'] = {'filters': [{'name': fname, 'field': fexpr(pg.drill_field), 'type': 'Categorical',
                                             'howCreated': 'User'}]}
        page['pageBinding'] = {'name': f'Binding_{pg.key}', 'type': 'Drillthrough',
                               'parameters': [{'name': f'Param_{pg.key}', 'boundFilter': fname,
                                               'fieldExpr': fexpr(pg.drill_field)}]}
    dump(DEF / 'pages' / pg.name / 'page.json', page)
    for i, v in enumerate(pg.vis):
        x, y, w, h = v['pos']
        vname = hashlib.md5(f'{pg.key}|{i}|{v["kind"]}'.encode()).hexdigest()[:20]
        z = (i + 1) * 1000
        body = BUILD[v['kind']](v)
        vc = {'$schema': VC_SCHEMA, 'name': vname,
              'position': {'x': round(x, 2), 'y': round(y, 2), 'z': z, 'height': round(h, 2), 'width': round(w, 2), 'tabOrder': z},
              'visual': body}
        dump(DEF / 'pages' / pg.name / 'visuals' / vname / 'visual.json', vc)
        manifest.append(dict(page=pg.display, kind=v['kind'], type=body['visualType'], x=x, y=y, w=w, h=h,
                             fields=[p['queryRef'] for st in body.get('query', {}).get('queryState', {}).values() for p in st['projections']]))

dump(RP / 'definition.pbir', {'version': '4.0', 'datasetReference': {'byPath': {'path': f'../{NAME}.SemanticModel'}}})
dump(RP / '.platform', {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json',
                        'metadata': {'type': 'Report', 'displayName': NAME},
                        'config': {'version': '2.0', 'logicalId': str(uuid.uuid5(uuid.NAMESPACE_URL, 'nike-report'))}})
dump(OUT / f'{NAME}.pbip', {'version': '1.0', 'artifacts': [{'report': {'path': f'{NAME}.Report'}}],
                            'settings': {'enableAutoRecovery': True}})
(OUT / '.gitignore').write_text('**/.pbi/localSettings.json\n**/.pbi/cache.abf\n', encoding='utf-8')
json.dump(manifest, open(Path(__file__).parent / 'visual_manifest.json', 'w'), indent=1)
print('pages', len(R.PAGES), 'visuals', len(manifest))
