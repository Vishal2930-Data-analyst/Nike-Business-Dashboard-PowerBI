/* Nike Business Dashboard - preview evaluation engine.
 * Re-implements the report's DAX measures over the raw CSV rows with Power BI-style filter context:
 *   ctx = { f: { 'Table.Column': [values] }, date: [firstDay, lastDay] }   (days since 2024-01-01)
 * Relationship semantics mirror the semantic model (single-direction, inventory date inactive,
 * marketing filtered by campaign/period overlap). Synthetic demonstration data only. */
(function (root) {
  'use strict';
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const NDAYS = 366, START = Date.UTC(2024, 0, 1);

  function createEngine(D) {
    const S = D.sales, P = D.products, C = D.customers, ST = D.stores, I = D.inventory, MK = D.marketing, SU = D.sustain;
    const nS = S.d.length, nI = I.s.length, nSU = SU.d.length, nMK = MK.Campaign_ID.length, nC = C.Gender.length;
    const COMPLETED = D.dicts.status.indexOf('Completed'), RETURNED = D.dicts.status.indexOf('Returned');
    const dayDate = d => new Date(START + d * 86400000);
    const dayMonth = d => dayDate(d).getUTCMonth();
    const DAYINFO = Array.from({ length: NDAYS }, (_, d) => {
      const dt = dayDate(d), m = dt.getUTCMonth();
      return { 'Month Short': MONTHS[m], 'Quarter': 'Q' + (Math.floor(m / 3) + 1), 'Month-Year': MONTHS[m] + ' 2024',
               'Date': dt.toISOString().slice(0, 10), 'Month Number': m + 1 };
    });
    // first completed purchase per customer (DimCustomer[First_Purchase_Date])
    const firstPurchase = new Array(nC).fill(null);
    for (let i = 0; i < nS; i++) if (S.st[i] === COMPLETED) {
      const c = S.c[i]; if (firstPurchase[c] === null || S.d[i] < firstPurchase[c]) firstPurchase[c] = S.d[i];
    }
    const mkCols = Object.keys(MK);

    // ---------------- column accessors per table
    const dimVal = {
      DimProduct: (col, i) => P[col][i], DimCustomer: (col, i) => C[col][i], DimStore: (col, i) => ST[col][i],
    };
    const ACC = {
      FactSales: (key, i) => {
        const [t, col] = split(key);
        if (t === 'DimProduct') return P[col][S.p[i]];
        if (t === 'DimCustomer') return C[col][S.c[i]];
        if (t === 'DimStore') return ST[col][S.s[i]];
        if (t === 'DimDate') return DAYINFO[S.d[i]][col];
        if (key === 'FactSales.Sales_Channel') return D.dicts.channel[S.ch[i]];
        if (key === 'FactSales.Order_Status') return D.dicts.status[S.st[i]];
        if (key === 'FactSales.Transaction_ID') return 'T' + String(S.id[i]).padStart(7, '0');
        if (key === 'FactSales.Transaction_Date') return DAYINFO[S.d[i]].Date;
        return undefined;
      },
      FactInventory: (key, i) => {
        const [t, col] = split(key);
        if (t === 'DimProduct') return P[col][I.p[i]];
        if (t === 'DimStore') return ST[col][I.s[i]];
        if (key === 'FactInventory.Inventory_Status') return I.status[i];
        return undefined;
      },
      FactSustainability: (key, i) => {
        const [t, col] = split(key);
        if (t === 'DimProduct') return P[col][SU.p[i]];
        if (t === 'DimDate') return DAYINFO[SU.d[i]][col];
        return undefined;
      },
      FactMarketing: (key, i) => { const [t, col] = split(key); return t === 'FactMarketing' ? MK[col][i] : undefined; },
      DimCustomer: (key, i) => { const [t, col] = split(key); return t === 'DimCustomer' ? C[col][i] : undefined; },
      DimStore: (key, i) => { const [t, col] = split(key); return t === 'DimStore' ? ST[col][i] : undefined; },
      DimProduct: (key, i) => { const [t, col] = split(key); return t === 'DimProduct' ? P[col][i] : undefined; },
    };
    const REACH = {   // which filter tables propagate to which table (active relationships)
      FactSales: ['FactSales', 'DimDate', 'DimProduct', 'DimCustomer', 'DimStore'],
      FactInventory: ['FactInventory', 'DimProduct', 'DimStore'],
      FactSustainability: ['FactSustainability', 'DimDate', 'DimProduct'],
      FactMarketing: ['FactMarketing'], DimCustomer: ['DimCustomer'], DimStore: ['DimStore'], DimProduct: ['DimProduct'],
    };
    const SIZE = { FactSales: nS, FactInventory: nI, FactSustainability: nSU, FactMarketing: nMK, DimCustomer: nC,
                   DimStore: ST.Store_ID.length, DimProduct: P.Product_ID.length };
    function split(key) { const i = key.indexOf('.'); return [key.slice(0, i), key.slice(i + 1)]; }

    // ---------------- context helpers
    function ctxKey(ctx) {
      const ks = Object.keys(ctx.f).sort();
      return ks.map(k => k + '=' + ctx.f[k].join('\u0001')).join('|') + '#' + (ctx.date ? ctx.date.join('-') : '');
    }
    function withF(ctx, key, values) { const f = Object.assign({}, ctx.f); f[key] = values; return { f, date: ctx.date, base: ctx.base }; }
    function without(ctx, pred) {
      const f = {}; for (const k in ctx.f) if (!pred(k)) f[k] = ctx.f[k];
      return { f, date: ctx.date, base: ctx.base };
    }
    function dayPasses(ctx, d) {
      if (ctx.date && (d < ctx.date[0] || d > ctx.date[1])) return false;
      for (const k in ctx.f) if (k.startsWith('DimDate.')) {
        const v = DAYINFO[d][k.slice(8)]; if (ctx.f[k].indexOf(v) < 0) return false;
      }
      return true;
    }
    function dateBounds(ctx) {
      let lo = null, hi = null;
      for (let d = 0; d < NDAYS; d++) if (dayPasses(ctx, d)) { if (lo === null) lo = d; hi = d; }
      return lo === null ? null : [lo, hi];
    }
    function setDates(ctx, d0, d1) {     // DATESBETWEEN on a marked date table: replaces all DimDate filters
      const c = without(ctx, k => k.startsWith('DimDate.')); c.date = [d0, d1]; return c;
    }

    // ---------------- scanning with memoisation
    const memo = new Map();
    function rows(table, ctx) {
      const key = table + '§' + ctxKey(ctx);
      if (memo.has(key)) return memo.get(key);
      const reach = REACH[table], acc = ACC[table], n = SIZE[table];
      const filters = Object.keys(ctx.f).filter(k => reach.indexOf(split(k)[0]) >= 0 && !k.startsWith('DimDate.'))
        .map(k => [k, new Set(ctx.f[k])]);
      const dateAware = reach.indexOf('DimDate') >= 0;
      const dayOk = dateAware ? Array.from({ length: NDAYS }, (_, d) => dayPasses(ctx, d)) : null;
      const dayArr = table === 'FactSales' ? S.d : table === 'FactSustainability' ? SU.d : null;
      const out = [];
      outer: for (let i = 0; i < n; i++) {
        if (dayOk && !dayOk[dayArr[i]]) continue;
        for (const [k, set] of filters) if (!set.has(acc(k, i))) continue outer;
        out.push(i);
      }
      memo.set(key, out);
      return out;
    }
    const sum = (arr, idx, scale) => { let s = 0; for (const i of idx) s += arr[i]; return idx.length ? s / (scale || 1) : null; };
    const div = (a, b) => (a === null || b === null || b === 0 || a === undefined) ? null : a / b;
    const nz = v => (v === null || v === undefined || Number.isNaN(v)) ? null : v;

    // ---------------- base measures
    const M = {};
    const sales = ctx => rows('FactSales', ctx);
    const completed = ctx => sales(ctx).filter(i => S.st[i] === COMPLETED);
    M['Total Net Sales'] = ctx => sum(S.n, sales(ctx), 100);
    M['Total Units Sold'] = ctx => sum(S.u, sales(ctx));
    M['Gross Profit'] = ctx => sum(S.g, sales(ctx), 100);
    M['Total Discount Amount'] = ctx => sum(S.k, sales(ctx), 100);
    M['Total Orders'] = ctx => { const n = completed(ctx).length; return n || null; };
    M['Total Transactions'] = ctx => sales(ctx).length || null;
    M['Return Rate %'] = ctx => div(sales(ctx).filter(i => S.st[i] === RETURNED).length || null, M['Total Transactions'](ctx));
    M['Active Customers'] = ctx => new Set(completed(ctx).map(i => S.c[i])).size || null;
    M['Active Stores'] = ctx => new Set(completed(ctx).map(i => S.s[i])).size || null;
    M['Products Sold'] = ctx => new Set(completed(ctx).map(i => S.p[i])).size || null;
    M['Average Order Value'] = ctx => div(M['Total Net Sales'](ctx), M['Total Orders'](ctx));
    M['Average Selling Price'] = ctx => div(M['Total Net Sales'](ctx), M['Total Units Sold'](ctx));
    M['Gross Profit Margin %'] = ctx => div(M['Gross Profit'](ctx), M['Total Net Sales'](ctx));
    M['Product Gross Margin %'] = M['Gross Profit Margin %'];
    M['Discount Rate %'] = ctx => { const d = M['Total Discount Amount'](ctx), n = M['Total Net Sales'](ctx); return div(d, n === null ? null : n + d); };
    M['Sales per Store'] = ctx => div(M['Total Net Sales'](ctx), M['Active Stores'](ctx));
    M['Sales per Sq Ft'] = ctx => div(M['Total Net Sales'](ctx), sum(ST.Store_Size_SqFt, rows('DimStore', ctx)));
    M['Revenue per Active Customer'] = ctx => div(M['Total Net Sales'](ctx), M['Active Customers'](ctx));
    M['Avg Orders per Customer'] = ctx => div(M['Total Orders'](ctx), M['Active Customers'](ctx));
    M['Registered Customers'] = ctx => rows('DimCustomer', ctx).length || null;
    M['New Customers'] = ctx => {
      const b = dateBounds(ctx); if (!b) return null;
      const n = rows('DimCustomer', ctx).filter(c => firstPurchase[c] !== null && firstPurchase[c] >= b[0] && firstPurchase[c] <= b[1]).length;
      return n || null;
    };
    // shares (ALLSELECTED -> ctx.base = filter context outside the visual)
    const share = name => ctx => div(M[name](ctx), M[name](ctx.base || ctx));
    M['Net Sales % of Total'] = share('Total Net Sales');
    M['Product Revenue Contribution %'] = share('Total Net Sales');
    M['Store Revenue Contribution %'] = share('Total Net Sales');
    M['Revenue by Gender %'] = share('Total Net Sales');
    M['Revenue by Age Group %'] = share('Total Net Sales');
    M['Revenue by Customer Segment %'] = share('Total Net Sales');
    M['Active Customer Share %'] = share('Active Customers');
    M['Loyalty Tier Distribution %'] = share('Active Customers');
    M['Share of All Products %'] = ctx => div(M['Total Net Sales'](ctx), M['Total Net Sales'](without(ctx, k => k.startsWith('DimProduct.'))));
    M['Share of All Stores %'] = ctx => div(M['Total Net Sales'](ctx), M['Total Net Sales'](without(ctx, k => k.startsWith('DimStore.'))));

    // ---------------- time intelligence
    const monthStart = d => { const dt = dayDate(d); return Math.round((Date.UTC(2024, dt.getUTCMonth(), 1) - START) / 86400000); };
    const monthEnd = d => { const dt = dayDate(d); return Math.round((Date.UTC(2024, dt.getUTCMonth() + 1, 0) - START) / 86400000); };
    function lastMonth(name) { return ctx => { const b = dateBounds(ctx); if (!b) return null; return nz(M[name](setDates(ctx, monthStart(b[1]), monthEnd(b[1])))); }; }
    function priorMonth(name) {
      return ctx => {
        const b = dateBounds(ctx); if (!b) return null;
        const end = monthStart(b[1]) - 1; if (end < 0) return null;
        return nz(M[name](setDates(ctx, monthStart(end), end)));
      };
    }
    const MOM = { Sales: 'Total Net Sales', Units: 'Total Units Sold', Customers: 'Active Customers', AOV: 'Average Order Value', 'Gross Profit': 'Gross Profit' };
    for (const label in MOM) {
      M[label + ' Last Month'] = lastMonth(MOM[label]);
      M[label + ' Prior Month'] = priorMonth(MOM[label]);
      M[label + ' MoM Growth %'] = ctx => {
        const c = M[label + ' Last Month'](ctx), p = M[label + ' Prior Month'](ctx);
        return (c === null || p === null) ? null : div(c - p, p);
      };
      M[label + ' MoM KPI Text'] = ctx => {
        const g = M[label + ' MoM Growth %'](ctx);
        return g === null ? 'N/A (no prior month)' : (g >= 0 ? '▲ ' : '▼ ') + pct(Math.abs(g), 1) + '  ' + M['MoM Comparison Label'](ctx);
      };
      M[label + ' MoM KPI Color'] = ctx => { const g = M[label + ' MoM Growth %'](ctx); return g === null ? '#6B7280' : g >= 0 ? '#22C55E' : '#E11D48'; };
    }
    M['Store MoM Growth %'] = M['Sales MoM Growth %'];
    M['MoM Comparison Label'] = ctx => { const b = dateBounds(ctx); if (!b) return ''; const m = dayMonth(b[1]); return MONTHS[m] + ' vs ' + (m === 0 ? 'Dec' : MONTHS[m - 1]); };
    M['Previous Month Sales'] = ctx => {     // DATEADD(-1 MONTH) on the current date set
      const b = dateBounds(ctx); if (!b) return null;
      const days = []; for (let d = b[0]; d <= b[1]; d++) if (dayPasses(ctx, d)) days.push(d);
      const shifted = days.map(d => { const dt = dayDate(d); const t = Date.UTC(2024, dt.getUTCMonth() - 1, Math.min(dt.getUTCDate(), new Date(Date.UTC(2024, dt.getUTCMonth(), 0)).getUTCDate())); return Math.round((t - START) / 86400000); })
        .filter(d => d >= 0);
      if (!shifted.length) return null;
      return nz(M['Total Net Sales'](setDates(ctx, Math.min(...shifted), Math.max(...shifted))));
    };
    M['Sales Growth %'] = ctx => {
      const b = dateBounds(ctx); if (!b) return null;
      const len = b[1] - b[0] + 1, ps = b[0] - len; if (ps < 0) return null;
      const prev = M['Total Net Sales'](setDates(ctx, ps, b[0] - 1)), cur = M['Total Net Sales'](ctx);
      return (prev === null || cur === null) ? null : div(cur - prev, prev);
    };
    M['Period Growth KPI Text'] = ctx => { const g = M['Sales Growth %'](ctx); return g === null ? 'N/A vs prev. period (no 2023)' : (g >= 0 ? '▲ ' : '▼ ') + pct(Math.abs(g), 1) + ' vs previous period'; };
    M['Period Growth KPI Color'] = ctx => { const g = M['Sales Growth %'](ctx); return g === null ? '#6B7280' : g >= 0 ? '#22C55E' : '#E11D48'; };
    M['Growth Bar Color'] = ctx => { const g = M['Sales MoM Growth %'](ctx); return g === null ? '#D4D4D4' : g >= 0 ? '#22C55E' : '#E11D48'; };

    // ---------------- ranking (RANKX over ALLSELECTED(dim))
    function rankBy(dimKeyCol, entity, valueFn, getId) {
      return ctx => {
        const own = valueFn(ctx); if (own === null) return null;
        const base = ctx.base || ctx;
        const ids = rows(entity, base);
        let better = 0;
        for (const id of ids) { const v = valueFn(withF(base, dimKeyCol, [getId(id)])); if (v !== null && v > own + 1e-9) better++; }
        return better + 1;
      };
    }
    const rankCache = new Map();
    function cachedRank(name, dimKeyCol, entity, valueFn, getId) {
      const r = rankBy(dimKeyCol, entity, valueFn, getId);
      return ctx => { const k = name + ctxKey(ctx) + '$' + ctxKey(ctx.base || ctx); if (!rankCache.has(k)) rankCache.set(k, r(ctx)); return rankCache.get(k); };
    }
    M['Product Rank by Revenue'] = cachedRank('p', 'DimProduct.Product_ID', 'DimProduct', M['Total Net Sales'], i => P.Product_ID[i]);
    M['Store Rank by Sales'] = cachedRank('s', 'DimStore.Store_ID', 'DimStore', M['Total Net Sales'], i => ST.Store_ID[i]);
    const top5 = (rank, inner) => ctx => { const r = M[rank](ctx); return (r !== null && r <= 5) ? nz(M[inner](ctx)) : null; };
    M['Top5 Product Rank'] = top5('Product Rank by Revenue', 'Product Rank by Revenue');
    M['Top5 Product Net Sales'] = top5('Product Rank by Revenue', 'Total Net Sales');
    M['Top5 Product Units'] = top5('Product Rank by Revenue', 'Total Units Sold');
    M['Top5 Product Gross Profit'] = top5('Product Rank by Revenue', 'Gross Profit');
    M['Top5 Store Rank'] = top5('Store Rank by Sales', 'Store Rank by Sales');
    M['Top5 Store Net Sales'] = top5('Store Rank by Sales', 'Total Net Sales');
    M['Top5 Store Units'] = top5('Store Rank by Sales', 'Total Units Sold');

    // ---------------- marketing (period overlap)
    function campaigns(ctx) {
      const b = dateBounds(ctx); if (!b) return [];
      return rows('FactMarketing', ctx).filter(i => MK.start[i] <= b[1] && MK.end[i] >= b[0]);
    }
    const mkSum = col => ctx => sum(MK[col], campaigns(ctx));
    M['Campaign Spend'] = mkSum('Campaign_Budget');
    M['Attributed Revenue'] = mkSum('Attributed_Revenue');
    M['Attributed Orders'] = mkSum('Attributed_Orders');
    M['Campaign Clicks'] = mkSum('Clicks');
    M['Campaign Impressions'] = mkSum('Impressions');
    M['Campaign Conversions'] = mkSum('Conversions');
    M['Campaign Count'] = ctx => campaigns(ctx).length || null;
    M['ROAS'] = ctx => div(M['Attributed Revenue'](ctx), M['Campaign Spend'](ctx));
    M['Click-Through Rate'] = ctx => div(M['Campaign Clicks'](ctx), M['Campaign Impressions'](ctx));
    M['Conversion Rate'] = ctx => div(M['Campaign Conversions'](ctx), M['Campaign Clicks'](ctx));
    M['Cost per Acquisition'] = ctx => div(M['Campaign Spend'](ctx), M['Campaign Conversions'](ctx));
    M['Campaign Rank by Attributed Revenue'] = cachedRank('m', 'FactMarketing.Campaign_ID', 'FactMarketing', M['Attributed Revenue'], i => MK.Campaign_ID[i]);
    M['Top5 Campaign Budget'] = top5('Campaign Rank by Attributed Revenue', 'Campaign Spend');
    M['Top5 Campaign Attributed Revenue'] = top5('Campaign Rank by Attributed Revenue', 'Attributed Revenue');
    M['Top5 Campaign ROAS'] = top5('Campaign Rank by Attributed Revenue', 'ROAS');
    M['ROAS Color'] = ctx => { const r = M['ROAS'](ctx); return r === null ? '#6B7280' : r >= 4.5 ? '#22C55E' : r >= 3.5 ? '#171717' : '#F59E0B'; };

    // ---------------- inventory (latest snapshot only; date slicer ignored - inactive relationship)
    const LATEST = Math.max(...I.d);
    const inv = ctx => rows('FactInventory', ctx).filter(i => I.d[i] === LATEST);
    const invStatus = (ctx, st) => { const f = ctx.f['FactInventory.Inventory_Status']; if (f && f.indexOf(st) < 0) return []; return inv(ctx).filter(i => I.status[i] === st); };
    M['Current Stock'] = ctx => sum(I.close, inv(ctx));
    M['Inventory Value'] = ctx => { const r = inv(ctx); if (!r.length) return null; let s = 0; for (const i of r) s += I.close[i] * P.Unit_Cost[I.p[i]]; return s; };
    M['Inventory Records'] = ctx => inv(ctx).length || null;
    M['In-Stock Product Count'] = ctx => invStatus(ctx, 'In Stock').length || null;
    M['Low-Stock Product Count'] = ctx => invStatus(ctx, 'Low Stock').length || null;
    M['Out-of-Stock Product Count'] = ctx => invStatus(ctx, 'Out of Stock').length || null;
    M['Low-Stock SKUs'] = ctx => new Set(inv(ctx).filter(i => I.status[i] !== 'In Stock').map(i => I.p[i])).size || null;
    M['Inventory Status %'] = share('Inventory Records');
    M['In Stock %'] = ctx => div(M['In-Stock Product Count'](ctx), M['Inventory Records'](ctx));
    M['Exception Stock Units'] = ctx => { const r = inv(ctx).filter(i => I.status[i] !== 'In Stock'); return r.length ? sum(I.close, r) : null; };
    M['Exception Reorder Level'] = ctx => M['Exception Stock Units'](ctx) === null ? null : sum(I.reorder, inv(ctx));
    M['Status Color'] = ctx => { const f = ctx.f['FactInventory.Inventory_Status']; const v = f && f.length === 1 ? f[0] : null;
      return v === 'In Stock' ? '#22C55E' : v === 'Low Stock' ? '#F59E0B' : v === 'Out of Stock' ? '#E11D48' : '#6B7280'; };

    // ---------------- sustainability
    const sus = ctx => rows('FactSustainability', ctx);
    M['Average Recycled Material %'] = ctx => { const r = sus(ctx); return r.length ? sum(SU.rec, r) / r.length / 100 : null; };
    M['Weighted Recycled Material %'] = ctx => { const r = sus(ctx); let a = 0, b = 0; for (const i of r) { a += SU.rec[i] * SU.units[i]; b += SU.units[i]; } return b ? a / b / 100 : null; };
    M['Total Carbon Emissions'] = ctx => sum(SU.co2, sus(ctx));
    M['Total Water Usage'] = ctx => sum(SU.h2o, sus(ctx));
    M['Sustainable Units Sold'] = ctx => sum(SU.units, sus(ctx));
    M['Avg Carbon per Product-Quarter'] = ctx => { const r = sus(ctx); return r.length ? sum(SU.co2, r) / r.length : null; };

    // ---------------- captions / colors
    const fmtInt = v => v === null ? '' : Math.round(v).toLocaleString('en-US');
    const pct = (v, dp) => (v * 100).toFixed(dp) + '%';
    M['Gross Margin KPI Text'] = ctx => { const g = M['Gross Profit Margin %'](ctx); return (g === null ? '' : pct(g, 1)) + ' gross margin'; };
    M['Return Rate KPI Text'] = ctx => { const r = M['Return Rate %'](ctx); return (r === null ? '0.0%' : pct(r, 1)) + ' of lines returned'; };
    M['Discount KPI Text'] = ctx => '$' + fmtInt(M['Total Discount Amount'](ctx) || 0) + ' in discounts';
    M['Orders KPI Text'] = ctx => fmtInt(M['Total Transactions'](ctx) || 0) + ' lines incl. returns/cancels';
    M['Products Sold KPI Text'] = () => 'of ' + P.Product_ID.length + ' catalogue products';
    M['Activation KPI Text'] = ctx => { const a = div(M['Active Customers'](ctx), M['Registered Customers'](ctx)); return (a === null ? '' : pct(a, 1)) + ' purchased in period'; };
    M['Stores KPI Text'] = () => 'of ' + ST.Store_ID.length + ' stores in network';
    M['Campaign Count KPI Text'] = ctx => (M['Campaign Count'](ctx) || 0) + ' campaigns overlap period';
    M['Attributed Orders KPI Text'] = ctx => fmtInt(M['Attributed Orders'](ctx) || 0) + ' attributed orders';
    M['Clicks KPI Text'] = ctx => fmtInt(M['Campaign Clicks'](ctx) || 0) + ' clicks';
    M['CPA KPI Text'] = ctx => { const v = M['Cost per Acquisition'](ctx); return 'CPA ' + (v === null ? '' : '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })); };
    M['Inventory Positions KPI Text'] = ctx => fmtInt(M['In-Stock Product Count'](ctx) || 0) + ' of ' + fmtInt(M['Inventory Records'](ctx) || 0) + ' positions';
    M['Low Stock SKUs KPI Text'] = ctx => fmtInt(M['Low-Stock SKUs'](ctx) || 0) + ' products affected';
    M['Snapshot KPI Text'] = () => 'Snapshot 31 Dec 2024';
    M['Weighted Recycled KPI Text'] = ctx => { const w = M['Weighted Recycled Material %'](ctx); return 'Weighted: ' + (w === null ? '' : pct(w, 1)); };
    M['Period KPI Text'] = ctx => { const b = dateBounds(ctx); if (!b) return ''; const f = d => { const dt = dayDate(d); return dt.getUTCDate() + ' ' + MONTHS[dt.getUTCMonth()] + ' ' + dt.getUTCFullYear(); }; return f(b[0]) + ' - ' + f(b[1]); };
    M['Profit Color'] = ctx => { const m = M['Gross Profit Margin %'](ctx), o = M['Gross Profit Margin %'](ctx.base || ctx); return (m !== null && o !== null && m >= o) ? '#16A34A' : '#171717'; };

    const selected = (ctx, key) => { const f = ctx.f[key]; return f && f.length === 1 ? f[0] : null; };
    M['Drill Product Label'] = ctx => 'Product: ' + (selected(ctx, 'DimProduct.Product_Name') || 'none - use right-click > Drill through');
    M['Drill Store Label'] = ctx => 'Store: ' + (selected(ctx, 'DimStore.Store_Name') || 'none - use right-click > Drill through');

    function measure(name, ctx) {
      if (!M[name]) throw new Error('No preview implementation for measure: ' + name);
      return nz(M[name](ctx));
    }
    function values(key, ctx) {    // distinct values of a column (domain) - for slicers/categories
      const [t, col] = split(key);
      if (t === 'DimDate') return [...new Set(DAYINFO.map(x => x[col]))];
      if (t === 'DimProduct') return [...new Set(P[col])];
      if (t === 'DimCustomer') return [...new Set(C[col])];
      if (t === 'DimStore') return [...new Set(ST[col])];
      if (t === 'FactSales') return key === 'FactSales.Sales_Channel' ? D.dicts.channel.slice() : D.dicts.status.slice();
      if (t === 'FactInventory') return ['In Stock', 'Low Stock', 'Out of Stock'];
      if (t === 'FactMarketing') return [...new Set(MK[col])];
      return [];
    }
    function tuples(keys, ctx) {    // distinct combinations for multi-column tables (driver table)
      const tables = keys.map(k => split(k)[0]);
      let driver = tables.find(t => t.startsWith('Fact'));
      if (!driver) driver = tables.every(t => t === tables[0]) ? tables[0] : 'FactSales';
      const acc = ACC[driver], idx = rows(driver, ctx), seen = new Map();
      for (const i of idx) { const tup = keys.map(k => acc(k, i)); const s = tup.join('\u0001'); if (!seen.has(s)) seen.set(s, tup); }
      return [...seen.values()];
    }
    function clearMemo() { memo.clear(); rankCache.clear(); }
    return { measure, values, tuples, withF, without, dateBounds, rows, clearMemo, ctxKey, MONTHS, DAYINFO, S, firstPurchase,
             hasMeasure: n => !!M[n], accessor: ACC };
  }
  root.createEngine = createEngine;
  if (typeof module !== 'undefined') module.exports = { createEngine };
})(typeof window !== 'undefined' ? window : globalThis);
