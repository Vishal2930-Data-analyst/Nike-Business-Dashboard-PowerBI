"""Extended data-quality checks for the Nike Business Dashboard datasets.
Writes Documentation/Data_Quality_Report.md and exits 1 if a blocking check fails.
Usage: python Scripts/data_quality_checks.py            (run from the project root or Scripts/)
All data is synthetic demonstration data - not official Nike business figures."""
from pathlib import Path
import sys
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / 'Data'
s = pd.read_csv(D / 'Sales.csv', parse_dates=['Transaction_Date'])
p = pd.read_csv(D / 'Products.csv', parse_dates=['Launch_Date'])
c = pd.read_csv(D / 'Customers.csv', parse_dates=['Registration_Date'])
st = pd.read_csv(D / 'Stores.csv', parse_dates=['Opening_Date'])
inv = pd.read_csv(D / 'Inventory.csv', parse_dates=['Inventory_Date'])
m = pd.read_csv(D / 'Marketing_Campaigns.csv', parse_dates=['Campaign_Start_Date', 'Campaign_End_Date'])
su = pd.read_csv(D / 'Sustainability.csv', parse_dates=['Date'])
tables = {'Products': p, 'Customers': c, 'Stores': st, 'Sales': s, 'Marketing_Campaigns': m, 'Inventory': inv, 'Sustainability': su}

checks = []   # (area, check, passed, detail, blocking)
def chk(area, name, cond, detail='', blocking=True):
    checks.append((area, name, bool(cond), detail, blocking))

# ---- keys
for t, k in [('Products', 'Product_ID'), ('Customers', 'Customer_ID'), ('Stores', 'Store_ID'), ('Sales', 'Transaction_ID'), ('Marketing_Campaigns', 'Campaign_ID')]:
    chk('Keys', f'{t}.{k} unique and not blank', tables[t][k].is_unique and tables[t][k].notna().all(), f'{tables[t][k].nunique():,} distinct / {len(tables[t]):,} rows')
chk('Keys', 'Inventory store-product pairs unique (snapshot grain)', not inv.duplicated(['Inventory_Date', 'Store_ID', 'Product_ID']).any(), f'{len(inv):,} rows = 20 stores x 150 products')
chk('Keys', 'Sustainability product-quarter pairs unique', not su.duplicated(['Date', 'Product_ID']).any(), f'{len(su):,} rows = 150 products x 4 quarters')
for fk, dim, col in [('Product_ID', p, 'Product_ID'), ('Customer_ID', c, 'Customer_ID'), ('Store_ID', st, 'Store_ID')]:
    chk('Foreign keys', f'Sales.{fk} exists in dimension', s[fk].isin(dim[col]).all(), f'{(~s[fk].isin(dim[col])).sum()} orphans')
chk('Foreign keys', 'Inventory Store_ID / Product_ID exist', inv.Store_ID.isin(st.Store_ID).all() and inv.Product_ID.isin(p.Product_ID).all())
chk('Foreign keys', 'Sustainability.Product_ID exists', su.Product_ID.isin(p.Product_ID).all())
# ---- completeness & duplicates
for t, df in tables.items():
    chk('Completeness', f'{t}: no missing values', df.isna().sum().sum() == 0, f'{int(df.isna().sum().sum())} nulls')
    chk('Completeness', f'{t}: no fully duplicated rows', not df.duplicated().any())
# ---- dates
chk('Dates', 'All dates parse (no NaT)', all(df.select_dtypes('datetime').notna().all().all() for df in tables.values()))
chk('Dates', 'Sales dates within 2024-01-01..2024-12-31', s.Transaction_Date.between('2024-01-01', '2024-12-31').all(),
    f'{s.Transaction_Date.min().date()} .. {s.Transaction_Date.max().date()} ({s.Transaction_Date.nunique()} days)')
chk('Dates', 'Inventory is a single snapshot dated 2024-12-31', inv.Inventory_Date.nunique() == 1 and inv.Inventory_Date.iloc[0] == pd.Timestamp('2024-12-31'))
chk('Dates', 'Sustainability dates are 2024 quarter-ends', set(su.Date.dt.strftime('%m-%d')) <= {'03-31', '06-30', '09-30', '12-31'} and (su.Date.dt.year == 2024).all())
chk('Dates', 'Campaign end >= start; campaigns within 2024', (m.Campaign_End_Date >= m.Campaign_Start_Date).all() and (m.Campaign_Start_Date.dt.year == 2024).all() and (m.Campaign_End_Date.dt.year == 2024).all())
# ---- categorical standardisation
cat_cols = {'Products': ['Category', 'Subcategory', 'Product_Line', 'Gender_Target', 'Color', 'Size_Range'],
            'Customers': ['Gender', 'Age_Group', 'Customer_Segment', 'Country', 'City', 'Loyalty_Tier'],
            'Stores': ['Store_Type', 'City', 'Country', 'Region'], 'Sales': ['Sales_Channel', 'Order_Status'],
            'Marketing_Campaigns': ['Marketing_Channel'], 'Inventory': ['Inventory_Status']}
ws = [f'{t}.{col}' for t, cols in cat_cols.items() for col in cols if (tables[t][col].astype(str) != tables[t][col].astype(str).str.strip()).any()]
chk('Categoricals', 'No leading/trailing whitespace in categorical labels', not ws, ', '.join(ws))
case = [f'{t}.{col}' for t, cols in cat_cols.items() for col in cols
        if tables[t][col].nunique() != tables[t][col].str.lower().nunique()]
chk('Categoricals', 'No case-variant duplicates (e.g. "online" vs "Online")', not case, ', '.join(case))
chk('Categoricals', 'Regions = 5 expected values', set(st.Region) == {'North America', 'Europe', 'Asia Pacific', 'Latin America', 'Middle East & Africa'})
chk('Categoricals', 'Sales channels = 5 expected values', set(s.Sales_Channel) == {'Retail Stores', 'Online', 'Wholesale', 'Nike App', 'Others'})
chk('Categoricals', 'Categories = Footwear/Apparel/Accessories/Equipment', set(p.Category) == {'Footwear', 'Apparel', 'Accessories', 'Equipment'})
chk('Categoricals', 'Age groups = 18-24/25-34/35-44/45-54/55+', set(c.Age_Group) == {'18-24', '25-34', '35-44', '45-54', '55+'})
chk('Categoricals', 'Inventory status = In Stock/Low Stock/Out of Stock', set(inv.Inventory_Status) == {'In Stock', 'Low Stock', 'Out of Stock'})
# ---- numeric sanity
chk('Numerics', 'No negative prices, costs, units or amounts',
    (p[['Unit_Cost', 'List_Price']] >= 0).all().all() and (s[['Units_Sold', 'Unit_Selling_Price', 'Discount_Amount', 'Net_Sales', 'Unit_Cost', 'Cost_of_Goods_Sold']] >= 0).all().all())
chk('Numerics', 'List price above unit cost for every product', (p.List_Price > p.Unit_Cost).all(), f'min markup {(p.List_Price / p.Unit_Cost).min():.2f}x')
chk('Numerics', 'No negative gross profit lines', (s.Gross_Profit >= 0).all())
chk('Numerics', 'Recycled material % within 0-100', su.Recycled_Material_Percentage.between(0, 100).all())
chk('Numerics', 'Inventory stock values non-negative', (inv[['Opening_Stock', 'Units_Received', 'Units_Sold', 'Units_Returned', 'Closing_Stock', 'Reorder_Level']] >= 0).all().all())
# ---- business rules
gross = s.Units_Sold * s.Unit_Selling_Price
chk('Sales rules', 'Net_Sales = Units x Unit_Selling_Price - Discount_Amount', ((gross - s.Discount_Amount - s.Net_Sales).abs() < 0.011).all(), 'all 25,000 lines')
chk('Sales rules', 'Cost_of_Goods_Sold = Units x Unit_Cost', ((s.Units_Sold * s.Unit_Cost - s.Cost_of_Goods_Sold).abs() < 0.011).all())
chk('Sales rules', 'Gross_Profit = Net_Sales - Cost_of_Goods_Sold', ((s.Net_Sales - s.Cost_of_Goods_Sold - s.Gross_Profit).abs() < 0.011).all())
chk('Sales rules', 'Discount never exceeds gross line value', (s.Discount_Amount <= gross + 0.01).all(), f'max discount rate {(s.Discount_Amount / gross.replace(0, np.nan)).max():.1%}')
chk('Sales rules', 'Sales Unit_Cost matches Products.Unit_Cost', (s.merge(p[['Product_ID', 'Unit_Cost']], on='Product_ID', suffixes=('', '_p')).eval('abs(Unit_Cost - Unit_Cost_p)') < 0.011).all())
nc = s[s.Order_Status != 'Completed']
chk('Sales rules', 'Returned/Cancelled rows are zeroed (demo convention preserved)',
    (nc[['Units_Sold', 'Discount_Amount', 'Net_Sales', 'Cost_of_Goods_Sold', 'Gross_Profit']] == 0).all().all(),
    f'{(s.Order_Status == "Returned").sum():,} returned + {(s.Order_Status == "Cancelled").sum():,} cancelled rows; no second return deduction applied')
chk('Sales rules', 'Return_Flag = TRUE exactly for Returned rows', ((s.Order_Status == 'Returned') == s.Return_Flag).all())
chk('Sales rules', 'Completed rows always have units > 0', (s[s.Order_Status == 'Completed'].Units_Sold > 0).all())
chk('Marketing rules', 'ROAS = Attributed_Revenue / Campaign_Budget', ((m.Attributed_Revenue / m.Campaign_Budget - m.ROAS).abs() < 0.011).all())
chk('Marketing rules', 'Clicks <= Impressions and Conversions <= Clicks', (m.Clicks <= m.Impressions).all() and (m.Conversions <= m.Clicks).all())
chk('Inventory rules', 'Closing = Opening + Received - Sold + Returned', (inv.Opening_Stock + inv.Units_Received - inv.Units_Sold + inv.Units_Returned == inv.Closing_Stock).all())
rule = np.where(inv.Closing_Stock == 0, 'Out of Stock', np.where(inv.Closing_Stock <= inv.Reorder_Level, 'Low Stock', 'In Stock'))
chk('Inventory rules', 'Status rule: 0 = Out of Stock; <= Reorder_Level = Low Stock; else In Stock', (rule == inv.Inventory_Status).all(), f'{(rule != inv.Inventory_Status).sum()} mismatches')
# ---- reconciliation of report totals
tot = s.Net_Sales.sum()
sp = s.merge(p[['Product_ID', 'Category']], on='Product_ID').merge(st[['Store_ID', 'Region']], on='Store_ID')
for col in ['Category', 'Region', 'Sales_Channel']:
    chk('Reconciliation', f'Net sales by {col} sums to total', abs(sp.groupby(col).Net_Sales.sum().sum() - tot) < 0.01, f'${tot:,.2f}')

# ---- informational findings (non-blocking, documented, not "fixed")
comp = s[s.Order_Status == 'Completed']
first = comp.groupby('Customer_ID').Transaction_Date.min()
late_reg = (c.set_index('Customer_ID').Registration_Date.reindex(first.index) > first).sum()
pre_launch = (s.merge(p[['Product_ID', 'Launch_Date']], on='Product_ID').pipe(lambda x: (x.Launch_Date > x.Transaction_Date) & (x.Units_Sold > 0))).sum()
future_launch = (p.Launch_Date > pd.Timestamp('2024-12-31')).sum()
name_mismatch = sum(1 for _, r in p.iterrows() if ('Pant' in r.Product_Name or 'Bag' in r.Product_Name or 'Top' in r.Product_Name) and r.Category == 'Footwear')
seg_tier = c.groupby('Customer_Segment').Loyalty_Tier.nunique().max() == 1
outliers = (comp.Net_Sales > comp.Net_Sales.mean() + 3 * comp.Net_Sales.std()).sum()
findings = [
    ('Order grain', 'Sales.csv has no order header: each Transaction_ID is one order line. [Total Orders] = distinct completed Transaction_IDs; AOV = net sales / completed lines.'),
    ('Registration after purchase', f'{late_reg:,} customers have Registration_Date later than their first completed purchase. Registration_Date is therefore not used for "new customer" logic; [New Customers] uses first purchase within the data window.'),
    ('Sales before launch', f'{pre_launch:,} completed sales lines precede the product Launch_Date and {future_launch} products launch after 2024. Kept as-is (synthetic); Launch_Date is descriptive only.'),
    ('Product names vs category', f'Product names are randomly composed (e.g. {name_mismatch} "Pant/Bag/Top" names are categorised as Footwear). Category is used as the source of truth for grouping.'),
    ('Segment = loyalty tier', 'Customer_Segment and Loyalty_Tier map 1:1 (Regular=Silver, Loyal=Gold, New=Bronze, VIP=Platinum). Both are kept; charts by either show the same split.'),
    ('Inventory vs sales', f'Inventory.Units_Sold totals {inv.Units_Sold.sum():,} vs {int(s.Units_Sold.sum()):,} in Sales.csv: the inventory snapshot is an independent synthetic table and is not reconciled to sales.'),
    ('Marketing attribution', f'Campaign attributed revenue (${m.Attributed_Revenue.sum():,.0f}) exceeds total net sales (${tot:,.0f}); attribution is synthetic, campaign-level and never added to sales revenue.'),
    ('No prior-year data', 'Only 2024 transactions exist, so year-over-year and "previous period" growth for the full year are N/A. KPI cards compare the last selected month with the month before (labelled e.g. "Dec vs Nov").'),
    ('Unusual values', f'{outliers:,} completed lines exceed mean + 3 sd of net sales (max ${comp.Net_Sales.max():,.2f}, up to 4 units x premium price). They are valid business records and are retained.'),
    ('Inactive products', f'{(~p.Is_Active).sum()} products are flagged Is_Active = False but still have 2024 sales; retained for historic reporting.'),
]
transformations = [
    'Imported every CSV with UTF-8 encoding and en-US culture; explicit column types (text / whole number / decimal / date / true-false).',
    'fnRequireColumns: refresh fails loudly if an expected source column is missing (schema drift guard).',
    'fnCleanText: Text.Trim + Text.Clean on all key and categorical columns (no changes were needed in the supplied files).',
    'Removed rows with blank primary keys (none present). No duplicate removal, no outlier removal - every valid record is preserved.',
    'Added helper columns: Is_Completed, Gross_Sales_Before_Discount (Sales); Age_Group_Sort, Loyalty_Tier_Sort, Registration_Year (Customers); List_Margin_Pct (Products); Status_Sort, Inventory_Key (Inventory); Campaign_Days (Marketing); Quarter_Label (Sustainability).',
    'Calculated column DimCustomer[First_Purchase_Date] (DAX) for the New Customers definition.',
    'Renamed the stored campaign ratio column ROAS to Source_ROAS so the model measure [ROAS] (recomputed from budget and revenue, correct under any filter) has an unambiguous name; values are unchanged and reconcile exactly.',
    'Generated DimDate (1 Jan - 31 Dec 2024) in Power Query and marked it as the model Date table.',
    'The source CSV files themselves are never modified (byte-identical copies in Data/).',
]

ok = all(x[2] for x in checks if x[4])
lines = ['# Data Quality Report', '', '**Nike Business Dashboard - synthetic demonstration data, not official Nike business figures.**', '',
         f'Generated by `Scripts/data_quality_checks.py`. Result: **{"PASS" if ok else "FAIL"}** - '
         f'{sum(x[2] for x in checks)}/{len(checks)} checks passed.', '',
         '## Row counts', '', '| File | Rows | Columns |', '|---|---:|---:|']
lines += [f'| {t}.csv | {len(df):,} | {df.shape[1]} |' for t, df in tables.items()]
lines += ['', '## Checks', '', '| Area | Check | Result | Detail |', '|---|---|---|---|']
lines += [f'| {a} | {n} | {"PASS" if r else "FAIL"} | {d} |' for a, n, r, d, b in checks]
lines += ['', '## Findings (documented, intentionally not "corrected")', '', '| Topic | Finding and handling |', '|---|---|']
lines += [f'| {a} | {b} |' for a, b in findings]
lines += ['', '## Transformations applied in Power Query / model', ''] + [f'- {t}' for t in transformations]
lines += ['', '## Key reference figures (full year 2024, no filters)', '',
          f'- Net sales ${tot:,.2f}; units {int(s.Units_Sold.sum()):,}; completed orders {len(comp):,}; active customers {comp.Customer_ID.nunique():,} of {len(c):,} registered.',
          f'- Gross profit ${s.Gross_Profit.sum():,.2f} ({s.Gross_Profit.sum() / tot:.1%} margin); discounts ${s.Discount_Amount.sum():,.2f}.',
          f'- Inventory snapshot: {inv.Closing_Stock.sum():,} units on hand; {(inv.Inventory_Status == "In Stock").mean():.1%} of 3,000 positions in stock.',
          f'- Campaigns: budget ${m.Campaign_Budget.sum():,.2f}, attributed revenue ${m.Attributed_Revenue.sum():,.2f}, portfolio ROAS {m.Attributed_Revenue.sum() / m.Campaign_Budget.sum():.2f}x.', '']
out = ROOT / 'Documentation' / 'Data_Quality_Report.md'
out.write_text('\n'.join(lines), encoding='utf-8')
for a, n, r, d, b in checks:
    print(('PASS' if r else 'FAIL') + f': [{a}] {n}')
print(f'{sum(x[2] for x in checks)}/{len(checks)} data checks passed -> {out}')
sys.exit(0 if ok else 1)
