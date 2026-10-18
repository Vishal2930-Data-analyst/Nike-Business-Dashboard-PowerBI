"""Export compact columnar data + page spec for the HTML preview (data.js / spec.js)."""
import json, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import report_def as R
import model_def as MD

D, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
s = pd.read_csv(D / 'Sales.csv'); p = pd.read_csv(D / 'Products.csv'); c = pd.read_csv(D / 'Customers.csv')
st = pd.read_csv(D / 'Stores.csv'); inv = pd.read_csv(D / 'Inventory.csv'); mk = pd.read_csv(D / 'Marketing_Campaigns.csv')
su = pd.read_csv(D / 'Sustainability.csv')
day0 = pd.Timestamp('2024-01-01')
def day(series):
    return ((pd.to_datetime(series) - day0).dt.days).astype(int).tolist()
def codes(series, cats=None):
    cats = cats or sorted(series.unique().tolist())
    idx = {v: i for i, v in enumerate(cats)}
    return cats, [idx[v] for v in series]

pidx = {v: i for i, v in enumerate(p.Product_ID)}; cidx = {v: i for i, v in enumerate(c.Customer_ID)}
sidx = {v: i for i, v in enumerate(st.Store_ID)}
chan, chan_codes = codes(s.Sales_Channel); stat, stat_codes = codes(s.Order_Status)
data = {
    'products': {k: p[k].tolist() for k in ['Product_ID', 'Product_Name', 'Category', 'Subcategory', 'Product_Line', 'Unit_Cost']},
    'customers': {'Gender': c.Gender.tolist(), 'Age_Group': c.Age_Group.tolist(), 'Customer_Segment': c.Customer_Segment.tolist(),
                  'Loyalty_Tier': c.Loyalty_Tier.tolist(), 'Country': c.Country.tolist()},
    'stores': {k: st[k].tolist() for k in ['Store_ID', 'Store_Name', 'Store_Type', 'City', 'Country', 'Region', 'Store_Size_SqFt']},
    'sales': {'id': [int(x[1:]) for x in s.Transaction_ID], 'd': day(s.Transaction_Date), 'p': [pidx[x] for x in s.Product_ID],
              'c': [cidx[x] for x in s.Customer_ID], 's': [sidx[x] for x in s.Store_ID], 'ch': chan_codes, 'st': stat_codes,
              'u': s.Units_Sold.tolist(), 'n': [round(x * 100) for x in s.Net_Sales], 'g': [round(x * 100) for x in s.Gross_Profit],
              'k': [round(x * 100) for x in s.Discount_Amount]},
    'dicts': {'channel': chan, 'status': stat},
    'inventory': {'s': [sidx[x] for x in inv.Store_ID], 'p': [pidx[x] for x in inv.Product_ID], 'd': day(inv.Inventory_Date),
                  'close': inv.Closing_Stock.tolist(), 'reorder': inv.Reorder_Level.tolist(), 'status': inv.Inventory_Status.tolist()},
    'marketing': {k: mk[k].tolist() for k in ['Campaign_ID', 'Campaign_Name', 'Marketing_Channel', 'Campaign_Budget', 'Attributed_Revenue',
                                               'Attributed_Orders', 'Impressions', 'Clicks', 'Conversions']},
    'sustain': {'d': day(su.Date), 'p': [pidx[x] for x in su.Product_ID], 'rec': su.Recycled_Material_Percentage.tolist(),
                'co2': su.Carbon_Emissions_Kg.tolist(), 'h2o': su.Water_Usage_Liters.tolist(), 'units': su.Sustainable_Units_Sold.tolist()},
}
data['marketing']['start'] = day(mk.Campaign_Start_Date); data['marketing']['end'] = day(mk.Campaign_End_Date)
data['marketing']['Campaign_Start_Date'] = mk.Campaign_Start_Date.tolist(); data['marketing']['Campaign_End_Date'] = mk.Campaign_End_Date.tolist()
(OUT / 'data.js').write_text('window.NIKE_DATA=' + json.dumps(data, separators=(',', ':')) + ';', encoding='utf-8')

# page spec (positions + bindings) shared with the PBIR generator
def f(x):
    return None if x is None else {'t': x[0], 'n': x[1], 'k': x[2], 'l': x[3]}
def conv(v):
    o = {}
    for k, val in v.items():
        if isinstance(val, tuple) and len(val) == 4 and val[2] in ('M', 'C'):
            o[k] = f(val)
        elif isinstance(val, list) and val and isinstance(val[0], tuple) and len(val[0]) == 4:
            o[k] = [f(x) for x in val]
        else:
            o[k] = val
    return o
spec = {'W': R.W, 'H': R.H, 'pages': [{'key': pg.key, 'display': pg.display, 'hidden': pg.hidden, 'nav': pg.active_nav,
                                       'drill': f(pg.drill_field), 'vis': [conv(v) for v in pg.vis]} for pg in R.PAGES],
        'nav': [k for _, _, k in R.NAV],
        'fmt': {mm['name']: mm['fmt'] for mm in MD.MEASURES}}
(OUT / 'spec.js').write_text('window.NIKE_SPEC=' + json.dumps(spec, separators=(',', ':')) + ';', encoding='utf-8')
print('data.js', round((OUT / 'data.js').stat().st_size / 1e6, 2), 'MB; spec.js', round((OUT / 'spec.js').stat().st_size / 1e3), 'KB')
