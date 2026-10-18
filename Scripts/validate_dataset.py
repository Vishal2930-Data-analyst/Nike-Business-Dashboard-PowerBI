from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent
# Packaging change (only edit to the supplied script): CSVs now live in ../Data
if not (ROOT/'Sales.csv').exists(): ROOT=ROOT.parent/'Data'
s=pd.read_csv(ROOT/'Sales.csv'); p=pd.read_csv(ROOT/'Products.csv'); c=pd.read_csv(ROOT/'Customers.csv'); st=pd.read_csv(ROOT/'Stores.csv'); inv=pd.read_csv(ROOT/'Inventory.csv'); m=pd.read_csv(ROOT/'Marketing_Campaigns.csv')
checks={'Unique transaction IDs':s.Transaction_ID.is_unique,'Valid product keys':s.Product_ID.isin(p.Product_ID).all(),'Valid customer keys':s.Customer_ID.isin(c.Customer_ID).all(),'Valid store keys':s.Store_ID.isin(st.Store_ID).all(),'Gross profit reconciles':((s.Net_Sales-s.Cost_of_Goods_Sold-s.Gross_Profit).abs()<0.011).all(),'Inventory balances reconcile':(inv.Opening_Stock+inv.Units_Received-inv.Units_Sold+inv.Units_Returned==inv.Closing_Stock).all(),'ROAS reconciles':((m.Attributed_Revenue/m.Campaign_Budget-m.ROAS).abs()<0.011).all()}
for k,v in checks.items(): print(('PASS' if v else 'FAIL')+': '+k)
if not all(checks.values()): raise SystemExit(1)
