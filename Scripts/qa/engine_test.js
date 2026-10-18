// Cross-check: JS engine (independent re-implementation of the DAX) vs pandas reference values.
const fs = require('fs'); const path = require('path');
const dir = process.argv[2]; const expected = JSON.parse(fs.readFileSync(process.argv[3]));
global.window = {}; eval(fs.readFileSync(path.join(dir, 'data.js'), 'utf8'));
const { createEngine } = require(path.join(dir, 'engine.js'));
const E = createEngine(window.NIKE_DATA);
const all = { f: {}, date: [0, 365] }; all.base = all;
const res = []; const close = (a, b, tol) => a !== null && Math.abs(a - b) <= (tol ?? Math.max(0.011, Math.abs(b) * 1e-6));
function t(name, got, exp, tol) { res.push([name, close(got, exp, tol), got, exp]); }
const m = n => E.measure(n, all);
for (const k of ['Total Net Sales', 'Total Units Sold', 'Total Orders', 'Average Order Value', 'Average Selling Price', 'Gross Profit',
  'Gross Profit Margin %', 'Total Discount Amount', 'Discount Rate %', 'Active Customers', 'Registered Customers', 'Sales per Store',
  'Return Rate %', 'Campaign Spend', 'Attributed Revenue', 'Attributed Orders', 'Current Stock', 'Inventory Value',
  'Total Carbon Emissions', 'Total Water Usage', 'Sustainable Units Sold'])
  t(k, m(k), expected[k], 0.02);
t('ROAS', m('ROAS'), expected['ROAS (portfolio)'], 1e-5); t('CTR', m('Click-Through Rate'), expected['CTR'], 1e-5);
t('Conversion Rate', m('Conversion Rate'), expected['Conversion Rate'], 1e-5); t('CPA', m('Cost per Acquisition'), expected['CPA'], 1e-3);
t('Avg Recycled %', m('Average Recycled Material %'), expected['Avg Recycled Material %'], 1e-5);
t('Sales MoM (Dec vs Nov)', m('Sales MoM Growth %'), expected['Sales MoM Growth % (Dec vs Nov)'], 1e-5);
t('Units MoM', m('Units MoM Growth %'), expected['Units MoM Growth % (Dec vs Nov)'], 1e-5);
t('Customers MoM', m('Customers MoM Growth %'), expected['Active Customers MoM Growth % (Dec vs Nov)'], 1e-5);
t('AOV MoM', m('AOV MoM Growth %'), expected['AOV MoM Growth % (Dec vs Nov)'], 1e-5);
t('GP MoM', m('Gross Profit MoM Growth %'), expected['Gross Profit MoM Growth % (Dec vs Nov)'], 1e-5);
res.push(['Sales Growth % (prev period) blank for full year', m('Sales Growth %') === null, m('Sales Growth %'), null]);
for (const [grp, key, meas] of [['By Category', 'DimProduct.Category', 'Net Sales % of Total'], ['By Region', 'DimStore.Region', 'Net Sales % of Total'], ['By Channel', 'FactSales.Sales_Channel', 'Net Sales % of Total']]) {
  let tot = 0;
  for (const [v, [net, sh]] of Object.entries(expected[grp])) {
    const c = E.withF(all, key, [v]); c.base = all;
    t(`${grp} ${v} net`, E.measure('Total Net Sales', c), net, 0.02); t(`${grp} ${v} share`, E.measure(meas, c), sh, 1e-5);
    tot += E.measure('Total Net Sales', c);
  }
  t(`${grp} reconciles to total`, tot, expected['Total Net Sales'], 0.05);
}
for (const [v, sh] of Object.entries(expected['Active Customers by Gender %'])) { const c = E.withF(all, 'DimCustomer.Gender', [v]); c.base = all; t('Gender ' + v, E.measure('Active Customer Share %', c), sh, 1e-5); }
for (const [v, sh] of Object.entries(expected['Active Customers by Age %'])) { const c = E.withF(all, 'DimCustomer.Age_Group', [v]); c.base = all; t('Age ' + v, E.measure('Active Customer Share %', c), sh, 1e-5); }
for (const [v, sh] of Object.entries(expected['Inventory Status %'])) { const c = E.withF(all, 'FactInventory.Inventory_Status', [v]); c.base = all; t('Inventory ' + v, E.measure('Inventory Status %', c), sh, 1e-5); }
// top 5 products via Top5 measures over (Product_Name, Category) tuples
const tup = E.tuples(['DimProduct.Product_Name', 'DimProduct.Category'], all).map(([n, c]) => { const x = E.withF(E.withF(all, 'DimProduct.Product_Name', [n]), 'DimProduct.Category', [c]); x.base = all; return [n, E.measure('Top5 Product Net Sales', x), E.measure('Top5 Product Rank', x)]; })
  .filter(r => r[1] !== null).sort((a, b) => b[1] - a[1]);
res.push(['Top-5 products = pandas top 5 (names, order)', JSON.stringify(tup.map(r => r[0])) === JSON.stringify(expected['Top 5 Products'].map(r => r[0])), tup.map(r => r[0] + ':' + r[2]).join(', '), '']);
expected['Top 5 Products'].forEach((r, i) => t('Top product ' + (i + 1) + ' net', tup[i] && tup[i][1], r[2], 0.02));
const st = E.tuples(['DimStore.Store_Name', 'DimStore.City', 'DimStore.Country'], all).map(([n, ci, co]) => { let x = E.withF(all, 'DimStore.Store_Name', [n]); x.base = all; return [n, E.measure('Top5 Store Net Sales', x)]; }).filter(r => r[1] !== null).sort((a, b) => b[1] - a[1]);
res.push(['Top-5 stores = pandas top 5', JSON.stringify(st.map(r => r[0])) === JSON.stringify(expected['Top 5 Stores'].map(r => r[0])), st.map(r => r[0]).join(', '), '']);
const mk = E.tuples(['FactMarketing.Campaign_Name', 'FactMarketing.Marketing_Channel'], all).map(([n, ch]) => { let x = E.withF(E.withF(all, 'FactMarketing.Campaign_Name', [n]), 'FactMarketing.Marketing_Channel', [ch]); x.base = all; return [n, E.measure('Top5 Campaign Attributed Revenue', x)]; }).filter(r => r[1] !== null).sort((a, b) => b[1] - a[1]);
res.push(['Top-5 campaigns = pandas top 5 by attributed revenue', JSON.stringify(mk.map(r => r[0])) === JSON.stringify(expected['Top 5 Campaigns by Attributed Revenue'].map(r => r[0])), mk.map(r => r[0]).join(', '), '']);
// monthly
for (let mo = 1; mo <= 12; mo++) { const c = E.withF(all, 'DimDate.Month Short', [E.MONTHS[mo - 1]]); c.base = all; t('Month ' + mo + ' net', E.measure('Total Net Sales', c), expected.Monthly[mo].net, 0.02); }
const jan = E.withF(all, 'DimDate.Month Short', ['Jan']); jan.base = all;
res.push(['January MoM is N/A (no Dec 2023)', E.measure('Sales MoM Growth %', jan) === null, E.measure('Sales MoM KPI Text', jan), 'N/A']);
let fails = 0;
for (const [n, ok, got, exp] of res) { if (!ok) fails++; console.log((ok ? 'PASS' : 'FAIL') + ': ' + n + (ok ? '' : `  got=${got} expected=${exp}`)); }
console.log(`${res.length - fails}/${res.length} engine checks passed`);
process.exit(fails ? 1 : 0);
