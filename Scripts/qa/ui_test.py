"""Drive the HTML preview like a user and compare displayed KPIs with pandas."""
import sys, os, json
import pandas as pd
from playwright.sync_api import sync_playwright
url, data = sys.argv[1], sys.argv[2]
s = pd.read_csv(f'{data}/Sales.csv', parse_dates=['Transaction_Date']); st = pd.read_csv(f'{data}/Stores.csv'); p = pd.read_csv(f'{data}/Products.csv')
sm = s.merge(st, on='Store_ID').merge(p[['Product_ID', 'Product_Name', 'Category']], on='Product_ID')
res = []
def ok(name, cond, detail=''): res.append((name, bool(cond), detail))
def cards(pg):
    return pg.evaluate("() => [...document.querySelectorAll('.card .cv')].map(e => e.textContent)")
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={'width': 1632, 'height': 1000})
    errors = []; pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.goto(url); pg.wait_for_timeout(1200)
    c = cards(pg); ok('Overview KPI cards render measures', c[:1] == ['$3.20M'] and '32,160' in c and '5,835' in c and '$150.88' in c and '$1.66M' in c, c[:8])
    # region slicer (real <select> interaction)
    pg.select_option('.slicer select', 'Europe'); pg.wait_for_timeout(500)
    eu = sm[sm.Region == 'Europe']; exp = f"${eu.Net_Sales.sum()/1e6:.2f}M"
    c = cards(pg); ok('Region slicer filters KPIs (Europe)', c[0] == exp, f'{c[0]} vs {exp}')
    exp_c = eu[eu.Order_Status == 'Completed'].Customer_ID.nunique()
    ok('Region slicer: active customers', f'{exp_c:,}' in c, f'{exp_c:,} in {c[:6]}')
    # date slicer: Q2 only via the date inputs
    d = pg.query_selector_all('.slicer input[type=date]'); d[0].fill('2024-04-01'); d[0].dispatch_event('change'); pg.wait_for_timeout(300)
    d = pg.query_selector_all('.slicer input[type=date]'); d[1].fill('2024-06-30'); d[1].dispatch_event('change'); pg.wait_for_timeout(500)
    q2 = eu[(eu.Transaction_Date >= '2024-04-01') & (eu.Transaction_Date <= '2024-06-30')]
    c = cards(pg); exp = f"${q2.Net_Sales.sum()/1e6:.2f}M"; ok('Date range + region combine (Europe, Q2)', c[0] == exp, f'{c[0]} vs {exp}')
    mj = pg.evaluate("() => [...document.querySelectorAll('.card .cv')].map(e=>e.textContent).find(t=>t.includes('Jun vs May'))")
    ok('MoM caption follows the last selected month (Jun vs May)', mj is not None, str(mj))
    # reset button
    pg.evaluate("() => { const b=[...document.querySelectorAll('.btn')].find(e=>e.title==='Reset all slicers'); b.click(); }"); pg.wait_for_timeout(500)
    ok('Reset clears all slicers', cards(pg)[0] == '$3.20M', cards(pg)[0])
    # cross-filter: click 'Footwear' slice is in echarts; use bar click via app API equivalent -> click table row in Top Products
    pg.evaluate("NIKE_APP.state.selection['overview'] = null"); 
    rows = pg.query_selector_all('.tbl tbody tr'); rows[0].click(); pg.wait_for_timeout(500)
    first = sm[sm.Product_Name == 'Tech Fleece Runner 2']; exp = f"${first.Net_Sales.sum()/1e3:.1f}" 
    c = cards(pg); ok('Cross-filter: clicking a product row filters the KPI cards', c[0].startswith('$0.09M'), c[0] + ' (expected ~$0.09M = Tech Fleece Runner 2)')
    rows = pg.query_selector_all('.tbl tbody tr'); rows[0].click(); pg.wait_for_timeout(400)
    ok('Clicking again clears the cross-filter', cards(pg)[0] == '$3.20M', cards(pg)[0])
    # drill-through: right-click a store row (Store Performance table)
    tbls = pg.query_selector_all('.tbl'); store_rows = tbls[1].query_selector_all('tbody tr'); store_rows[0].click(button='right'); pg.wait_for_timeout(600)
    st_name = pg.evaluate("NIKE_APP.state.page + '|' + JSON.stringify(NIKE_APP.state.drill)")
    tok = sm[sm.Store_Name == 'Tokyo Shibuya']
    c = cards(pg); exp = f"${tok.Net_Sales.sum()/1e3:,.1f}K"
    ok('Drill-through (right-click store) opens Store Details filtered', 'store_details' in st_name and exp in c, f'{st_name} {c[:3]} expected {exp}')
    ok('Drill label shows selected store', any('Tokyo Shibuya' in x for x in c), str(c[:2]))
    pg.evaluate("() => [...document.querySelectorAll('.btn')].find(e=>e.title==='Back').click()"); pg.wait_for_timeout(400)
    ok('Back button returns to Overview', pg.evaluate('NIKE_APP.state.page') == 'overview')
    # navigation: every sidebar item
    navs = pg.evaluate("() => [...document.querySelectorAll('.btn')].map(e=>e.title).filter(t=>t.startsWith('Go to'))")
    visited = []
    for t in navs:
        pg.evaluate(f"() => [...document.querySelectorAll('.btn')].find(e=>e.title==={json.dumps(t)}).click()"); pg.wait_for_timeout(350)
        visited.append(pg.evaluate('NIKE_APP.state.page'))
    ok('All 9 sidebar buttons navigate', len(set(visited)) == 9, ','.join(visited))
    # View All buttons on overview
    pg.evaluate("NIKE_APP.state.page='overview'; NIKE_APP.render()"); pg.wait_for_timeout(300)
    va = pg.evaluate("() => [...document.querySelectorAll('.btn')].filter(e=>e.title.startsWith('Open View')).length")
    ok('View All buttons present (Products, Stores, Marketing)', va == 3, va)
    # page slicer: Category on Products page
    pg.evaluate("NIKE_APP.state.page='products'; NIKE_APP.render()"); pg.wait_for_timeout(400)
    sels = pg.query_selector_all('.slicer select'); sels[-1].select_option('Apparel'); pg.wait_for_timeout(500)
    ap = sm[sm.Category == 'Apparel']; c = cards(pg)
    ok('Page slicer (Category=Apparel) filters product KPIs', f"${ap.Net_Sales.sum()/1e6:.2f}M" in c, f'{c[:4]}')
    first_rank = pg.evaluate("() => document.querySelectorAll('.tbl tbody tr')[0].children[1].textContent")
    exp_top = ap.groupby('Product_Name').Net_Sales.sum().idxmax()
    ok('Product ranking re-ranks within the slicer selection', first_rank == exp_top, f'{first_rank} vs {exp_top}')
    # inventory ignores date slicer
    pg.evaluate("NIKE_APP.state.page='inventory'; NIKE_APP.state.date=[0,30]; NIKE_APP.render()"); pg.wait_for_timeout(400)
    ok('Inventory snapshot not affected by date slicer', '152,430' in cards(pg), cards(pg)[:3])
    pg.evaluate("NIKE_APP.state.date=[0,365]; NIKE_APP.state.page='marketing'; NIKE_APP.state.date=[300,365]; NIKE_APP.render()"); pg.wait_for_timeout(400)
    ok('Marketing uses campaign/period overlap (Oct 27-Dec 31: 0 campaigns)', any('0 campaigns' in x for x in cards(pg)), cards(pg)[:3])
    ok('No JavaScript errors', not errors, errors[:3])
    b.close()
fails = 0
for n, passed, det in res:
    fails += not passed; print(('PASS' if passed else 'FAIL') + ': ' + n + ('' if passed else f'  -- {det}'))
print(f'{len(res)-fails}/{len(res)} UI checks passed'); sys.exit(1 if fails else 0)
