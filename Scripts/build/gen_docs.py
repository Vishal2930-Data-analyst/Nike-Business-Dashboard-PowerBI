"""Generate PowerBI/Data_Model.md and PowerBI/Dashboard_Layout.md from the model/report definitions."""
import sys, json, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import model_def as MD
import report_def as R

PBI = Path(sys.argv[1])
GRAIN = {'DimDate': 'One row per calendar day (366 rows, 2024)', 'DimProduct': 'One row per product (150)',
         'DimCustomer': 'One row per registered customer (6,000)', 'DimStore': 'One row per store (20)',
         'FactSales': 'One row per transaction line (25,000)', 'FactMarketing': 'One row per campaign (10) - aggregates',
         'FactInventory': 'One row per store x product in the 31-Dec-2024 snapshot (3,000)',
         'FactSustainability': 'One row per product x quarter-end date (600)'}
KEYS = {'DimDate': 'Date', 'DimProduct': 'Product_ID', 'DimCustomer': 'Customer_ID', 'DimStore': 'Store_ID',
        'FactSales': 'Transaction_ID', 'FactMarketing': 'Campaign_ID', 'FactInventory': 'Store_ID + Product_ID',
        'FactSustainability': 'Date + Product_ID'}

L = ['# Data Model - Nike Business Dashboard', '',
     'Star schema implemented in `Nike_Business_Dashboard.SemanticModel/model.bim` (TMSL, compatibility level 1567, import mode).',
     'All data is **synthetic demonstration data** - not official Nike business figures.', '',
     '## Model diagram', '', '```mermaid', 'erDiagram']
for ft, fc, tt, tc, active in MD.RELATIONSHIPS:
    L.append(f'    {tt} ||--o{{ {ft} : "{tc} -> {fc}{"" if active else " (inactive)"}"')
L += ['    _Measures {', '        measures "154+ DAX measures"', '    }', '```', '', '```',
      '                      DimDate (marked Date table)',
      '                 /        |          :           :',
      '          active    active       inactive     inactive',
      '               /          |            :           :',
      '   FactSustainability  FactSales   FactInventory  FactMarketing (no other keys)',
      '        \\               / | \\            /   \\',
      '         DimProduct ----+  |  +--- DimStore --+',
      '                           |',
      '                       DimCustomer',
      '```', '', '## Tables', '', '| Table | Role | Grain | Key | Source |', '|---|---|---|---|---|']
for t in MD.TABLES:
    L.append(f'| {t["name"]} | {"Dimension" if t["name"].startswith("Dim") else "Fact"} | {GRAIN[t["name"]]} | {KEYS[t["name"]]} | '
             f'{t["file"] or "Generated in Power Query"} |')
L += ['| _Measures | Measure table | - | - | DAX calculated table `{0}` (hidden column) |', '',
      '## Relationships', '', '| From (many) | To (one) | Cardinality | Cross-filter | Active | Why |', '|---|---|---|---|---|---|']
WHY = {('FactInventory', 'Inventory_Date'): 'Snapshot must not disappear when the date slicer excludes 31 Dec; measures always read the latest snapshot.',
       ('FactMarketing', 'Campaign_Start_Date'): 'Campaigns span periods; DAX filters campaigns whose run overlaps the selected dates. Available for USERELATIONSHIP.'}
for ft, fc, tt, tc, active in MD.RELATIONSHIPS:
    L.append(f'| {ft}[{fc}] | {tt}[{tc}] | Many-to-one (*:1) | Single (dimension filters fact) | {"Yes" if active else "No"} | {WHY.get((ft, fc), "Standard star-schema join")} |')
L += ['', 'No bi-directional or many-to-many relationships are used, so there are no ambiguous filter paths. Facts never filter each other.', '',
      '## Modelling decisions', '',
      '- **DimDate** covers 1 Jan - 31 Dec 2024 (the reporting period; every fact date falls inside it), is marked as the Date table (`dataCategory = Time`, `Date` is the key) and auto date/time is disabled.',
      '- Sort-by columns: Month Name / Month Short by Month Number; Year-Month and Month-Year by Month-Year Sort Key; Quarter by Quarter Number; Day Name by Day of Week Number; Age_Group by Age_Group_Sort; Loyalty_Tier by Loyalty_Tier_Sort; Inventory_Status by Status_Sort.',
      '- Hierarchy `DimDate[Calendar]`: Year > Quarter > Month Short > Date (drill down from quarterly to monthly).',
      '- **FactSales** keeps the source demo convention: returned and cancelled lines have zero units and amounts. Measures simply sum - returns are never subtracted a second time and cancelled lines never count as revenue. Order/customer counts use completed lines only.',
      '- **FactMarketing** has no product/store/customer keys and is never joined to FactSales. Attributed revenue is reported separately and never added to sales.',
      '- **FactInventory** is a single snapshot (31 Dec 2024). Measures select the latest `Inventory_Date` explicitly and never sum Closing_Stock across dates. Grain for status counts = store x product position.',
      '- **FactSustainability** is product x quarter. Totals (carbon, water, units) are sums; recycled % is an average of records (and a units-weighted variant).',
      '- `DataFolder` Power Query parameter points at the folder holding the CSVs; all queries load through the reusable `fnLoadCsv`, `fnCleanText`, `fnRequireColumns` functions.', '',
      '## Columns', '']
for t in MD.TABLES:
    L += [f'### {t["name"]}', '', t['desc'], '', '| Column | Type | Format | Notes |', '|---|---|---|---|']
    for c in t['columns'] + t['extra_cols']:
        if not c.get('model', True):
            continue
        notes = []
        if c.get('hidden'): notes.append('hidden')
        if c.get('sortBy'): notes.append(f'sorted by {c["sortBy"]}')
        if c.get('dataCategory'): notes.append(f'data category {c["dataCategory"]}')
        if c['mtype'] is None and t['file']: notes.append('added in Power Query')
        L.append(f'| {c["name"]} | {c["dtype"]} | `{c.get("fmt") or ""}` | {", ".join(notes)} |')
    for cc in t['calc_cols']:
        L.append(f'| {cc["name"]} | {cc["dtype"]} | `{cc["fmt"]}` | DAX calculated column: `{cc["expr"]}` |')
    L.append('')
L += ['## Measures (by display folder)', '', 'Full DAX for every measure is in `DAX_Measures.txt`.', '']
fold = collections.OrderedDict()
for mm in MD.MEASURES:
    fold.setdefault(mm['folder'], []).append(mm)
for f, ms in fold.items():
    L += [f'### {f}', '', '| Measure | Format | Description |', '|---|---|---|']
    L += [f'| {mm["name"]} | `{mm["fmt"] or "text"}` | {mm["desc"]} |' for mm in ms]
    L.append('')
L += ['## Transaction count vs distinct customers', '',
      '- `[Total Orders]` counts distinct **completed transaction lines** (there is no separate order header in the data).',
      '- `[Total Transactions]` counts every line including returned and cancelled ones.',
      '- `[Active Customers]` counts distinct **customers with at least one completed line** in the filter context.',
      '- `[Registered Customers]` counts rows in DimCustomer regardless of purchasing (6,000).', '']
(PBI / 'Data_Model.md').write_text('\n'.join(L), encoding='utf-8')

# ---------------------------------------------------------------- layout spec
K = {'card': 'Card', 'spark': 'Line chart (sparkline)', 'line': 'Line chart', 'donut': 'Donut chart', 'table': 'Table',
     'slicer': 'Slicer', 'nav': 'Button (page navigation)', 'clear': 'Button (clear all slicers)', 'back': 'Button (back)'}
def fname(f):
    return f'[{f[1]}]' if f[2] == 'M' else f'{f[0]}[{f[1]}]'
L = ['# Dashboard Layout Specification', '',
     'Generated from `Scripts/build/report_def.py` - the same definition that produced the PBIR report and the HTML preview.', '',
     '## Canvas and grid', '',
     '- Page size **1600 x 900 px** (16:9), display option *Fit to page*. 11 pages (9 navigable + 2 hidden drill-through pages).',
     '- Sidebar: x 0-200 (#111111). Main area: x 216-1584 (1,368 px wide), 16 px gutters, 12 px top/bottom margins.',
     '- Header row y 12-52: product search (x 216-600), Reset (x 1000-1092), date range (x 1104-1354), region (x 1366-1516), notification bell and profile (decorative).',
     '- Overview: banner y 62-138; KPI row y 148-236 (5 tiles x 260.8 px); rows y 248-464, 476-682, 694-888 with columns 540 / 420 / 376 px.',
     '- Other pages: title band y 62-108 (page slicers right-aligned); KPI row y 118-200; content rows y 212-542 and 554-888.',
     '- Card shells: white, 1 px #E7E9ED border, 12 px radius; title 14 px bold at (16, 13); subtitle 11 px #6B7280 at (16, 32); visuals start 48-50 px below the shell top with 10 px side padding.',
     '', '## Palette and typography', '',
     '| Token | Hex | Use |', '|---|---|---|',
     '| Background | #F5F6F8 | Page / wallpaper |', '| Card | #FFFFFF | Card shells, tables |', '| Sidebar | #111111 | Navigation rail |',
     '| Primary text | #171717 | Values, titles, main series |', '| Secondary text | #6B7280 | Labels, axes, captions |', '| Border | #E7E9ED | Card borders, gridlines |',
     '| Positive | #22C55E | Positive growth, In Stock, ROAS >= 4.5x |', '| Warning | #F59E0B | Low Stock, ROAS < 3.5x |', '| Negative | #E11D48 | Negative growth, Out of Stock |',
     '| Neutral ramp | #171717 #404040 #525252 #737373 #A3A3A3 #D4D4D4 | Categories, regions, channels |', '',
     'Typography: Segoe UI family in Power BI (Inter in the rendered backgrounds/preview). KPI values 18-19 pt bold, KPI labels 10 px uppercase semibold, card titles 14 px bold, axis/table text 9-10 pt.',
     '', '## How the page is built', '',
     'Each page has a **background image** (`StaticResources/RegisteredResources/bg_<page>*.png`, 3200x1800 = 2x canvas) containing only static design: sidebar with active-page highlight, header boxes and icons, banner, card shells, card titles/subtitles, KPI icons and labels. '
     'Every number, chart, table and slicer on top of it is a **native Power BI visual bound to the model**. Navigation, View All, Reset and Back are transparent native buttons placed over the drawn controls. '
     'HTML sources for the backgrounds are in `PowerBI/Design/` so the design can be edited and re-rendered.', '']
for pg in R.PAGES:
    L += [f'## Page: {pg.display}' + (' (hidden drill-through)' if pg.hidden else ''), '']
    if pg.drill_field:
        L += [f'Drill-through field: `{fname(pg.drill_field)}` - right-click a {pg.drill_field[1].split("_")[0].lower()} in any visual > Drill through > {pg.display}. A Back button returns to the source page.', '']
    shells = [e for e in pg.bg if e['t'] == 'shell']
    kpis = [e for e in pg.bg if e['t'] == 'kpi']
    if kpis:
        L += ['**KPI tiles**', '', '| # | Label | Icon | Value measure | Caption measure | Sparkline |', '|---|---|---|---|---|---|']
        cards = [v for v in pg.vis if v['kind'] == 'card' and not v.get('category') and 'drill' not in v.get('name_hint', '')]
        for i, k in enumerate(kpis):
            val = next((v for v in cards if v.get('name_hint') == k['label']), None)
            sub = next((v for v in cards if v.get('name_hint') == k['label'] + ' sub'), None)
            spark = [v for v in pg.vis if v['kind'] == 'spark']
            L.append(f'| {i + 1} | {k["label"]} | {k["icon"]} | {fname(val["field"]) if val else ""} | '
                     f'{fname(sub["field"]) if sub else "-"}{" (colour: " + fname(sub["color_measure"]) + ")" if sub and sub.get("color_measure") else ""} | '
                     f'{"[" + spark[i]["field"][1] + "] by month" if k["spark"] and i < len(spark) else "-"} |')
        L.append('')
    L += ['**Panels and visuals**', '', '| Panel (title / subtitle) | Visual | Position x,y,w,h | Fields | Formatting / behaviour |', '|---|---|---|---|---|']
    for v in pg.vis:
        if v['kind'] in ('nav', 'card', 'spark') and not (v['kind'] == 'card' and v.get('category')):
            continue
        x, y, w, h = v['pos']
        shell = next((s for s in shells if s['x'] <= x + 1 and x + w <= s['x'] + s['w'] + 1 and s['y'] <= y + 1 and y + h <= s['y'] + s['h'] + 1), None)
        title = f'{shell["title"]} / {shell["subtitle"]}' if shell else ('Header' if y < 60 else 'Title band' if y < 110 else '')
        kind = v['kind']
        if kind == 'bar':
            vt = {'barChart': 'Bar chart', 'columnChart': 'Column chart', 'clusteredBarChart': 'Clustered bar chart'}[v['chart']]
            fields = f'Axis: {fname(v["cat"])}; Values: {", ".join(fname(f) for f in v["y"])}' + (f'; Tooltips: {", ".join(fname(f) for f in v["tooltips"])}' if v['tooltips'] else '')
            fmt = 'Data labels' + (' (K)' if v.get('units') == 1000 else '') + ('; colour per category' if v.get('colors') else '') + \
                  (f'; colour by {fname(v["color_measure"])}' if v.get('color_measure') else '') + ('; legend' if v.get('legend') else '') + \
                  ('; sorted by value desc' if v['cat'][1] not in ('Month Short', 'Quarter', 'Age_Group') else '; natural order')
        elif kind == 'line':
            vt = 'Line chart'; fields = f'Axis: {fname(v["cat"])}; Values: {", ".join(fname(f) for f in v["y"])}' + (f'; Tooltips: {", ".join(fname(f) for f in v["tooltips"])}' if v['tooltips'] else '')
            fmt = '3 px line, circular markers, dashed #E7E9ED gridlines' + ('; legend top' if v.get('legend') else '; no legend')
            if v.get('drill'):
                fmt += '; drillable axis ' + ' > '.join(fname(d) for d in v['drill']) + f' > {fname(v["cat"])} (drill up = quarterly, drill down = monthly)'
        elif kind == 'donut':
            vt = 'Donut chart'; fields = f'Legend: {fname(v["cat"])}; Values: {fname(v["y"])}' + (f'; Tooltips: {", ".join(fname(f) for f in v["tooltips"])}' if v['tooltips'] else '')
            fmt = 'Inner radius 66%; fixed colour per category' + ('; % labels, legend bottom' if v['legend'] else '; no legend (table/legend alongside)')
        elif kind == 'table':
            vt = 'Table'; fields = ', '.join(fname(f) + (f' as "{f[3]}"' if f[3] else '') for f in v['columns'])
            fmt = f'Sorted by {fname(v["sort"])} {v["sort_dir"].lower()}; column widths {v["widths"]}' + \
                  ('; totals row' if v['totals'] else '') + ''.join(f'; font colour of {k} from [{mm}]' for k, mm in v['color_rules'].items()) + \
                  ('; top-5 measures return BLANK beyond rank 5 so only five rows show' if any('Top5' in f[1] for f in v['columns']) else '')
        elif kind == 'card':
            vt = 'Card (overlay)'; fields = fname(v['field']); fmt = 'Centre label inside the donut ring'
        elif kind == 'slicer':
            vt = f'Slicer ({v["mode"]})'; fields = fname(v['field'])
            fmt = ('search enabled; ' if v.get('search') else '') + (f'sync group {v["sync"]} (same selection on every page)' if v.get('sync') else 'page-level')
        else:
            vt = K[kind]; fields = '-'; fmt = 'Transparent button over the drawn control' + (f' -> {v.get("target")}' if v.get('target') else '')
        L.append(f'| {title} | {vt} | {x:.0f}, {y:.0f}, {w:.0f}, {h:.0f} | {fields} | {fmt} |')
    navs = [v for v in pg.vis if v['kind'] == 'nav']
    L += ['', f'Navigation: {len(navs)} transparent page-navigation buttons (9 sidebar items' + (f' + {len(navs) - 9} "View All"' if len(navs) > 9 else '') + ').', '']
L += ['## Interactions', '',
      '- Date range (Between) slicer filters every date-based visual through DimDate; inventory ignores it by design (snapshot; inactive relationship).',
      '- Region slicer filters sales and inventory through DimStore. Product search filters sales, inventory and sustainability through DimProduct.',
      '- Header slicers are in sync groups, so a selection follows the user to every page. Page slicers (Channel, Category, Segment, Store type, Marketing channel, Status) are page-scoped.',
      '- Marketing visuals respond to the date range by campaign/period overlap and to the marketing-channel slicer only; they never multiply or add to sales.',
      '- Default cross-filtering is on: selecting a bar, slice or table row filters the other visuals on the page.',
      '- Drill-through: right-click a product (Product Details) or a store (Store Details) in any visual. Both detail pages are hidden from the page tabs and have a Back button.',
      '- Reset button uses the native "Clear all slicers" action.', '']
(PBI / 'Dashboard_Layout.md').write_text('\n'.join(L), encoding='utf-8')
print('docs written')
