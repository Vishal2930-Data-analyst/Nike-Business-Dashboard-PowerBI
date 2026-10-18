"""Compute reference KPI values from the source CSVs (truth for DAX/preview QA)."""
import pandas as pd, json, sys
from pathlib import Path
D = Path(sys.argv[1])
s = pd.read_csv(D/'Sales.csv', parse_dates=['Transaction_Date'])
p = pd.read_csv(D/'Products.csv'); c = pd.read_csv(D/'Customers.csv'); st = pd.read_csv(D/'Stores.csv')
inv = pd.read_csv(D/'Inventory.csv'); m = pd.read_csv(D/'Marketing_Campaigns.csv'); su = pd.read_csv(D/'Sustainability.csv')
comp = s[s.Order_Status == 'Completed']
E = {}
E['Total Net Sales'] = round(s.Net_Sales.sum(), 2)
E['Total Units Sold'] = int(s.Units_Sold.sum())
E['Total Orders'] = int(comp.Transaction_ID.nunique())
E['All Transactions'] = len(s)
E['Average Order Value'] = round(E['Total Net Sales']/E['Total Orders'], 4)
E['Average Selling Price'] = round(E['Total Net Sales']/E['Total Units Sold'], 4)
E['Total Cost of Goods Sold'] = round(s.Cost_of_Goods_Sold.sum(), 2)
E['Gross Profit'] = round(s.Gross_Profit.sum(), 2)
E['Gross Profit Margin %'] = round(E['Gross Profit']/E['Total Net Sales'], 6)
E['Total Discount Amount'] = round(s.Discount_Amount.sum(), 2)
E['Discount Rate %'] = round(E['Total Discount Amount']/(E['Total Net Sales']+E['Total Discount Amount']), 6)
E['Active Customers'] = int(comp.Customer_ID.nunique())
E['Registered Customers'] = len(c)
E['Sales per Store'] = round(E['Total Net Sales']/comp.Store_ID.nunique(), 2)
E['Return Rate %'] = round((s.Order_Status=='Returned').mean(), 6)
mon = s.groupby(s.Transaction_Date.dt.month).agg(net=('Net_Sales','sum'), units=('Units_Sold','sum'), gp=('Gross_Profit','sum'))
mon['orders'] = comp.groupby(comp.Transaction_Date.dt.month).Transaction_ID.nunique()
mon['cust'] = comp.groupby(comp.Transaction_Date.dt.month).Customer_ID.nunique()
mon['aov'] = mon.net/mon.orders
E['Monthly'] = {int(k): {kk: round(float(vv), 4) for kk, vv in r.items()} for k, r in mon.iterrows()}
E['Sales MoM Growth % (Dec vs Nov)'] = round(mon.net[12]/mon.net[11]-1, 6)
E['Units MoM Growth % (Dec vs Nov)'] = round(mon.units[12]/mon.units[11]-1, 6)
E['Active Customers MoM Growth % (Dec vs Nov)'] = round(mon.cust[12]/mon.cust[11]-1, 6)
E['AOV MoM Growth % (Dec vs Nov)'] = round(mon.aov[12]/mon.aov[11]-1, 6)
E['Gross Profit MoM Growth % (Dec vs Nov)'] = round(mon.gp[12]/mon.gp[11]-1, 6)
sp = s.merge(p, on='Product_ID', suffixes=('', '_p')).merge(st, on='Store_ID').merge(c, on='Customer_ID', suffixes=('', '_c'))
def share(col):
    g = sp.groupby(col).Net_Sales.sum().sort_values(ascending=False)
    return {k: [round(v, 2), round(v/g.sum(), 6)] for k, v in g.items()}
E['By Category'] = share('Category'); E['By Region'] = share('Region'); E['By Channel'] = share('Sales_Channel')
tp = sp.groupby(['Product_Name','Category']).agg(net=('Net_Sales','sum'), units=('Units_Sold','sum'), gp=('Gross_Profit','sum')).sort_values('net', ascending=False).head(5)
E['Top 5 Products'] = [[a, b, round(r.net, 2), int(r.units), round(r.gp, 2)] for (a, b), r in tp.iterrows()]
ts = sp.groupby(['Store_Name','City','Country']).agg(net=('Net_Sales','sum'), units=('Units_Sold','sum')).sort_values('net', ascending=False).head(5)
E['Top 5 Stores'] = [[a, b, cc, round(r.net, 2), int(r.units)] for (a, b, cc), r in ts.iterrows()]
cp = sp[sp.Order_Status=='Completed']
gen = cp.groupby('Gender').Customer_ID.nunique(); E['Active Customers by Gender %'] = {k: round(v/E['Active Customers'], 6) for k, v in gen.items()}
age = cp.groupby('Age_Group').Customer_ID.nunique(); E['Active Customers by Age %'] = {k: round(v/E['Active Customers'], 6) for k, v in age.items()}
seg = sp.groupby('Customer_Segment').Net_Sales.sum(); E['Revenue by Segment'] = {k: round(v, 2) for k, v in seg.items()}
m2 = m.sort_values('Attributed_Revenue', ascending=False)
E['Campaign Spend'] = round(m.Campaign_Budget.sum(), 2); E['Attributed Revenue'] = round(m.Attributed_Revenue.sum(), 2)
E['ROAS (portfolio)'] = round(E['Attributed Revenue']/E['Campaign Spend'], 6)
E['CTR'] = round(m.Clicks.sum()/m.Impressions.sum(), 6); E['Conversion Rate'] = round(m.Conversions.sum()/m.Clicks.sum(), 6)
E['CPA'] = round(m.Campaign_Budget.sum()/m.Conversions.sum(), 4); E['Attributed Orders'] = int(m.Attributed_Orders.sum())
E['Top 5 Campaigns by Attributed Revenue'] = m2.head(5)[['Campaign_Name','Marketing_Channel','Campaign_Budget','Attributed_Revenue','ROAS']].values.tolist()
inv2 = inv.merge(p[['Product_ID','Unit_Cost']], on='Product_ID')
E['Current Stock'] = int(inv.Closing_Stock.sum()); E['Inventory Value'] = round((inv2.Closing_Stock*inv2.Unit_Cost).sum(), 2)
vc = inv.Inventory_Status.value_counts(); E['Inventory Status Records'] = {k: int(v) for k, v in vc.items()}
E['Inventory Status %'] = {k: round(v/len(inv), 6) for k, v in vc.items()}
E['Avg Recycled Material %'] = round(su.Recycled_Material_Percentage.mean()/100, 6)
E['Total Carbon Emissions'] = round(su.Carbon_Emissions_Kg.sum(), 2); E['Total Water Usage'] = round(su.Water_Usage_Liters.sum(), 2)
E['Sustainable Units Sold'] = int(su.Sustainable_Units_Sold.sum())
json.dump(E, open(sys.argv[2], 'w'), indent=1, default=str)
print(json.dumps({k: v for k, v in E.items() if not isinstance(v, (dict, list))}, indent=1))
for k in ['By Category','By Region','By Channel','Top 5 Products','Top 5 Stores','Active Customers by Gender %','Active Customers by Age %','Inventory Status %','Top 5 Campaigns by Attributed Revenue']: print(k, E[k])
