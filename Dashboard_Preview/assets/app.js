/* Nike Business Dashboard - HTML preview renderer.
 * Renders each report page from the same layout spec as the Power BI report (spec.js),
 * over the same page backgrounds, with live measures from engine.js. */
(function () {
  'use strict';
  const SPEC = window.NIKE_SPEC, E = window.createEngine(window.NIKE_DATA);
  const FMT = SPEC.fmt, PAGES = {}; SPEC.pages.forEach(p => PAGES[p.key] = p);
  const FONT = '"Segoe UI", Inter, system-ui, sans-serif';
  const DRILL_TARGET = { 'DimProduct.Product_Name': 'product_details', 'DimStore.Store_Name': 'store_details' };
  const state = { page: 'overview', product: null, date: [0, 365], region: null, pageSlicers: {}, selection: {}, drill: {}, history: [] };
  const charts = [];
  const stage = document.getElementById('stage');
  const key = f => f.t + '.' + f.n;
  const label = f => f.l || f.n.replace(/_/g, ' ');

  // ---------------------------------------------------------------- formatting (mirrors model format strings)
  function fmt(name, v, units, precision) {
    if (v === null || v === undefined) return '';
    if (typeof v === 'string') return v;
    const f = FMT[name] || '#,0';
    const dec = s => { const m = s.match(/\.(0+)/); return m ? m[1].length : 0; };
    if (f.includes('%')) return (v * 100).toFixed(dec(f.split(';')[0])) + '%';
    if (f.includes('"x"')) return v.toFixed(dec(f)) + 'x';
    const cur = f.startsWith('\\$');
    let suffix = '', val = v, d = dec(f.split(';')[0]);
    if (units && units >= 1000) { val = v / units; suffix = units === 1000 ? 'K' : 'M'; d = precision ?? 1; }
    else if (units === 0 && Math.abs(v) >= 1e5 && !f.includes('"')) { val = v / (Math.abs(v) >= 1e6 ? 1e6 : 1e3); suffix = Math.abs(v) >= 1e6 ? 'M' : 'K'; d = 2; }
    else if (precision !== undefined && units === 1) d = precision;
    const s = Math.abs(val).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
    const unitTxt = (f.match(/"(kg|L)"/) || [])[1];
    const out = (cur ? '$' : '') + s + suffix + (unitTxt ? ' ' + unitTxt : '');
    return v < 0 ? (cur ? '(' + out + ')' : '-' + out) : out;
  }
  const axisFmt = (name, units) => v => fmt(name, v, units || (FMT[name] && FMT[name].includes('%') ? undefined : 0), 0);

  // ---------------------------------------------------------------- filter context
  function pageCtx(pg, excludeSel) {
    const f = {};
    if (state.product) f['DimProduct.Product_Name'] = [state.product];
    if (state.region) f['DimStore.Region'] = [state.region];
    const ps = state.pageSlicers[pg.key] || {};
    for (const k in ps) if (ps[k] !== null) f[k] = [ps[k]];
    const d = state.drill[pg.key]; if (d) f[d.key] = [d.value];
    const sel = state.selection[pg.key];
    if (sel && sel.src !== excludeSel) f[sel.key] = f[sel.key] ? f[sel.key].filter(x => x === sel.value) : [sel.value];
    const ctx = { f, date: state.date.slice() }; ctx.base = ctx; return ctx;
  }
  function rowCtx(base, pairs) { let c = base; for (const [k, v] of pairs) c = E.withF(c, k, [v]); c.base = base; return c; }
  const mval = (f, ctx) => f.k === 'M' ? E.measure(f.n, ctx) : null;

  // ---------------------------------------------------------------- domains
  const MONTHS = E.MONTHS;
  function categories(cat, ctx) {
    const k = key(cat);
    if (k === 'DimDate.Month Short') { const b = E.dateBounds(ctx); return b ? MONTHS.filter((m, i) => E.DAYINFO.some((d, j) => d['Month Short'] === m && j >= b[0] && j <= b[1])) : []; }
    if (k === 'DimDate.Quarter') { const b = E.dateBounds(ctx); return b ? ['Q1', 'Q2', 'Q3', 'Q4'].filter(q => E.DAYINFO.some((d, j) => d.Quarter === q && j >= b[0] && j <= b[1])) : []; }
    const vals = E.values(k, ctx);
    return k === 'DimCustomer.Age_Group' ? vals.slice().sort() : vals;
  }
  const natural = k => ['DimDate.Month Short', 'DimDate.Quarter', 'DimCustomer.Age_Group', 'DimDate.Month-Year'].includes(k);

  // ---------------------------------------------------------------- selection (cross-filter)
  function select(pg, src, k, value) {
    const cur = state.selection[pg.key];
    state.selection[pg.key] = (cur && cur.src === src && cur.value === value) ? null : { src, key: k, value };
    render();
  }
  function drill(k, value) {
    const target = DRILL_TARGET[k]; if (!target) return;
    state.history.push(state.page); state.drill[target] = { key: k, value }; state.selection[target] = null;
    state.page = target; render();
  }
  function selFor(pg, src) { const s = state.selection[pg.key]; return s && s.src === src ? s : null; }

  // ---------------------------------------------------------------- renderers
  function box(v, cls) {
    const [x, y, w, h] = v.pos, el = document.createElement('div');
    el.className = 'vis ' + (cls || ''); Object.assign(el.style, { left: x + 'px', top: y + 'px', width: w + 'px', height: h + 'px' });
    stage.appendChild(el);            // attach first so charts can measure their container
    return el;
  }
  function chart(el, option, onClick, onContext) {
    const c = echarts.init(el, null, { renderer: 'svg' }); c.setOption(option); charts.push(c);
    if (onClick) c.on('click', onClick);
    if (onContext) c.on('contextmenu', p => { p.event.event.preventDefault(); onContext(p); });
    return c;
  }
  const TT = { trigger: 'axis', backgroundColor: '#fff', borderColor: '#E7E9ED', textStyle: { color: '#171717', fontFamily: FONT, fontSize: 11 }, extraCssText: 'box-shadow:0 6px 18px rgba(0,0,0,.08);border-radius:8px' };

  const R = {};
  R.card = (v, pg, ctx) => {
    const el = box(v, 'card');
    const val = mval(v.field, ctx);
    const color = v.color_measure ? E.measure(v.color_measure.n, ctx) : v.color;
    el.innerHTML = `<div class="cv" style="font-size:${v.size * 1.333}px;color:${color};font-weight:${v.bold ? 700 : 400}">${esc(fmt(v.field.n, val, v.units, v.precision)) || (v.bold ? '(Blank)' : '')}</div>` +
      (v.category ? `<div class="cl">${esc(label(v.field))}</div>` : '');
    return el;
  };
  R.spark = (v, pg, ctx) => {
    const el = box(v); const cats = categories({ t: 'DimDate', n: 'Month Short' }, ctx);
    const data = cats.map(m => mval(v.field, rowCtx(ctx, [['DimDate.Month Short', m]])));
    chart(el, { animation: false, grid: { left: 2, right: 2, top: 4, bottom: 4 }, xAxis: { type: 'category', show: false, data: cats },
      yAxis: { type: 'value', show: false, scale: true }, tooltip: Object.assign({}, TT, { valueFormatter: x => fmt(v.field.n, x) }),
      series: [{ type: 'line', data, symbol: 'none', smooth: false, lineStyle: { width: 2, color: '#9CA3AF' } }] });
    return el;
  };
  R.line = (v, pg, ctx) => {
    const el = box(v); const cats = categories(v.cat, ctx), k = key(v.cat);
    const rows = cats.map(c => rowCtx(ctx, [[k, c]]));
    const series = v.y.map(f => ({ name: label(f), type: 'line', data: rows.map(r => mval(f, r)), symbol: 'circle', symbolSize: 7,
      lineStyle: { width: 3, color: (v.colors && v.colors[f.n]) || '#171717' }, itemStyle: { color: (v.colors && v.colors[f.n]) || '#171717', borderColor: '#fff', borderWidth: 1.5 },
      areaStyle: v.y.length === 1 ? { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(23,23,23,.10)' }, { offset: 1, color: 'rgba(23,23,23,0)' }]) } : undefined }));
    const tips = v.tooltips || [];
    chart(el, { animation: false, grid: { left: 52, right: 16, top: v.legend ? 30 : 12, bottom: 26 },
      legend: v.legend ? { top: 0, right: 8, textStyle: { color: '#6B7280', fontSize: 11, fontFamily: FONT }, icon: 'circle', itemWidth: 8 } : undefined,
      xAxis: { type: 'category', data: cats, axisLine: { lineStyle: { color: '#E7E9ED' } }, axisTick: { show: false }, axisLabel: { color: '#6B7280', fontSize: 11, fontFamily: FONT } },
      yAxis: { type: 'value', scale: true, splitNumber: 4, splitLine: { lineStyle: { color: '#E7E9ED', type: 'dashed' } }, axisLabel: { color: '#6B7280', fontSize: 11, fontFamily: FONT, formatter: axisFmt(v.y[0].n, v.units) } },
      tooltip: Object.assign({}, TT, { formatter: ps => { const i = ps[0].dataIndex; return `<b>${cats[i]} 2024</b><br>` + v.y.map(f => `${label(f)}: <b>${fmt(f.n, mval(f, rows[i]))}</b>`).concat(tips.map(f => `${label(f)}: <b>${fmt(f.n, mval(f, rows[i])) || 'N/A'}</b>`)).join('<br>'); } }),
      series });
    return el;
  };
  R.bar = (v, pg, ctx) => {
    const el = box(v); const k = key(v.cat), horizontal = v.chart !== 'columnChart';
    let cats = categories(v.cat, ctx);
    let rows = cats.map(c => [c, rowCtx(ctx, [[k, c]])]).filter(([c, r]) => v.y.some(f => mval(f, r) !== null));
    if (!natural(k)) rows.sort((a, b) => (mval(v.y[0], b[1]) || 0) - (mval(v.y[0], a[1]) || 0));
    if (k === 'DimDate.Month Short') rows = MONTHS.filter(m => rows.some(r => r[0] === m)).map(m => rows.find(r => r[0] === m));
    const names = rows.map(r => r[0]), sel = selFor(pg, v);
    const colorOf = (c, r, i, f) => {
      if (v.series_colors) return v.series_colors[f.n];
      if (v.colors && v.colors[c]) return v.colors[c];
      if (v.color_measure) return E.measure(v.color_measure.n, r);
      return v.single_color || '#171717';
    };
    const series = v.y.map(f => ({ name: label(f), type: 'bar', barMaxWidth: horizontal ? 18 : 34, barCategoryGap: '38%',
      data: rows.map(([c, r], i) => ({ value: mval(f, r), itemStyle: { color: colorOf(c, r, i, f), borderRadius: horizontal ? [0, 3, 3, 0] : [3, 3, 0, 0], opacity: sel && sel.value !== c ? 0.3 : 1 } })),
      itemStyle: v.series_colors ? { color: v.series_colors[f.n] } : undefined,
      label: { show: v.labels !== false, position: horizontal ? 'right' : 'top', fontSize: v.cat_font ? 10 : 11, color: '#171717', fontFamily: FONT, formatter: p => fmt(f.n, p.value, v.units ? v.units : undefined, 1) } }));
    const catAxis = { type: 'category', data: names, inverse: horizontal, axisLine: { show: !horizontal, lineStyle: { color: '#E7E9ED' } }, axisTick: { show: false },
      axisLabel: { color: '#171717', fontSize: v.cat_font ? 10 : 11, fontFamily: FONT, width: horizontal ? Math.max(70, v.pos[2] * 0.36) : (rows.length > 10 ? 90 : undefined), overflow: 'truncate', interval: 0, rotate: !horizontal && rows.length > 10 ? 35 : 0 } };
    const valAxis = { type: 'value', show: false, max: x => x.max * (horizontal ? (v.pos[2] < 260 ? 1.6 : 1.3) : 1.12), min: x => Math.min(0, x.min * 1.12) };
    const tips = v.tooltips || [];
    chart(el, { animation: false, grid: horizontal ? { left: 8, right: 8, top: v.legend ? 28 : 10, bottom: 4, containLabel: true } : { left: rows.length > 10 ? 44 : 8, right: 8, top: 22, bottom: rows.length > 10 ? 70 : 22, containLabel: false },
      legend: v.legend ? { top: 0, right: 8, textStyle: { color: '#6B7280', fontSize: 11, fontFamily: FONT }, icon: 'circle', itemWidth: 8 } : undefined,
      xAxis: horizontal ? valAxis : catAxis, yAxis: horizontal ? catAxis : valAxis,
      tooltip: Object.assign({}, TT, { axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(0,0,0,.03)' } },
        formatter: ps => { const r = rows[ps[0].dataIndex][1]; return `<b>${esc(names[ps[0].dataIndex])}</b><br>` + v.y.concat(tips).map(f => `${label(f)}: <b>${fmt(f.n, mval(f, r)) || 'N/A'}</b>`).join('<br>'); } }),
      series },
      p => select(pg, v, k, names[p.dataIndex]), p => drill(k, names[p.dataIndex]));
    return el;
  };
  R.donut = (v, pg, ctx) => {
    const el = box(v); const k = key(v.cat), sel = selFor(pg, v);
    const rows = categories(v.cat, ctx).map(c => [c, rowCtx(ctx, [[k, c]])]).map(([c, r]) => [c, r, mval(v.y, r)]).filter(r => r[2] !== null)
      .sort((a, b) => b[2] - a[2]);
    const tips = v.tooltips || [];
    chart(el, { animation: false,
      legend: v.legend ? { bottom: 0, left: 'center', icon: 'circle', itemWidth: 8, itemGap: 10, textStyle: { color: '#6B7280', fontSize: 11, fontFamily: FONT } } : undefined,
      tooltip: { trigger: 'item', backgroundColor: '#fff', borderColor: '#E7E9ED', textStyle: { color: '#171717', fontSize: 11, fontFamily: FONT },
        formatter: p => { const r = rows[p.dataIndex][1]; return `<b>${esc(p.name)}</b><br>${label(v.y)}: <b>${fmt(v.y.n, p.value)}</b> (${p.percent.toFixed(1)}%)<br>` + tips.map(f => `${label(f)}: <b>${fmt(f.n, mval(f, r))}</b>`).join('<br>'); } },
      series: [{ type: 'pie', radius: v.legend ? ['50%', '72%'] : ['58%', '84%'], center: ['50%', v.legend ? '45%' : '50%'], avoidLabelOverlap: true, padAngle: 1,
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: v.legend ? { show: true, formatter: p => Math.round(p.percent) + '%', color: '#171717', fontSize: 11, fontFamily: FONT } : { show: false },
        labelLine: { length: 6, length2: 6 },
        data: rows.map(([c, r, val]) => ({ name: c, value: val, itemStyle: { color: v.colors[c] || '#A3A3A3', opacity: sel && sel.value !== c ? 0.3 : 1 } })) }] },
      p => select(pg, v, k, p.name), p => drill(k, p.name));
    return el;
  };
  R.table = (v, pg, ctx) => {
    const el = box(v, 'tbl');
    const groups = v.columns.filter(f => f.k === 'C'), meas = v.columns.filter(f => f.k === 'M');
    const gkeys = groups.map(key), sel = selFor(pg, v);
    let rows, note = '';
    if (gkeys.includes('FactSales.Transaction_ID')) {          // fast path: one row per transaction line
      const S = E.S, acc = E.accessor.FactSales, idx = E.rows('FactSales', ctx);
      const direct = { 'Total Units Sold': i => S.u[i], 'Total Net Sales': i => S.n[i] / 100, 'Gross Profit': i => S.g[i] / 100 };
      rows = idx.slice(0, 250).map(i => ({ vals: gkeys.map(k => acc(k, i)), m: meas.map(f => direct[f.n](i)), ctx: null }));
      note = `Showing first ${rows.length.toLocaleString()} of ${idx.length.toLocaleString()} transaction lines (Power BI shows all with scrolling).`;
    } else {
      let tuples;
      if (gkeys.length === 1 && gkeys[0].startsWith('DimDate.')) tuples = categories(groups[0], ctx).map(x => [x]);
      else tuples = E.tuples(gkeys, ctx);
      rows = tuples.map(t => { const r = rowCtx(ctx, gkeys.map((k, i) => [k, t[i]])); return { vals: t, m: meas.map(f => mval(f, r)), ctx: r }; })
        .filter(r => r.m.some(x => x !== null));
    }
    const sk = v.sort, dir = v.sort_dir === 'Ascending' ? 1 : -1;
    const sval = r => sk.k === 'M' ? r.m[meas.findIndex(f => f.n === sk.n)] : r.vals[gkeys.indexOf(key(sk))];
    if (sk.k === 'C' && key(sk) === 'DimDate.Month-Year') rows.sort((a, b) => dir * (MONTHS.indexOf(a.vals[0].slice(0, 3)) - MONTHS.indexOf(b.vals[0].slice(0, 3))));
    else if (sk.k === 'C' && key(sk) === 'FactInventory.Inventory_Status') { const o = ['In Stock', 'Low Stock', 'Out of Stock']; rows.sort((a, b) => dir * (o.indexOf(sval(a)) - o.indexOf(sval(b)))); }
    else rows.sort((a, b) => { const x = sval(a), y = sval(b); if (x === y) return 0; if (x === null) return 1; if (y === null) return -1; return (x > y ? 1 : -1) * dir; });
    const rules = v.color_rules || {};
    const colorFor = (f, r) => { const m = rules[f.n] || rules[key(f)]; return m && r.ctx ? E.measure(m, r.ctx) : null; };
    const tw = v.widths.reduce((a, b) => a + b, 0);
    let h = `<table style="width:${tw <= v.pos[2] - 14 ? '100%' : tw + 'px'}"><colgroup>` + v.widths.map(w => `<col style="width:${w}px">`).join('') + '</colgroup><thead><tr>' +
      v.columns.map(f => `<th class="${f.k === 'M' ? 'num' : ''}">${esc(label(f))}</th>`).join('') + '</tr></thead><tbody>';
    for (const r of rows) {
      const dim = sel && r.vals[0] !== sel.value ? ' dim' : '';
      h += `<tr class="${dim}" data-v="${esc(String(r.vals[0]))}">` + v.columns.map(f => {
        const isM = f.k === 'M', val = isM ? r.m[meas.indexOf(f)] : r.vals[gkeys.indexOf(key(f))];
        const col = colorFor(f, r), txt = isM ? ((v.formats || {})[f.n] === 'K' && val !== null ? '$' + Math.round(val / 1000).toLocaleString('en-US') + 'K' : fmt(f.n, val)) : String(val);
        return `<td class="${isM ? 'num' : ''}"${col ? ` style="color:${col};font-weight:600"` : ''} title="${esc(txt)}">${esc(txt)}</td>`;
      }).join('') + '</tr>';
    }
    if (v.totals && rows.length) h += '<tr class="tot">' + v.columns.map((f, i) => `<td class="${f.k === 'M' ? 'num' : ''}">${f.k === 'M' ? esc(fmt(f.n, mval(f, ctx))) : (i === 0 ? 'Total' : '')}</td>`).join('') + '</tr>';
    h += '</tbody></table>' + (note ? `<div class="note">${esc(note)}</div>` : '') + (rows.length ? '' : '<div class="empty">No data for the current selection</div>');
    el.innerHTML = h;
    if (gkeys.length && !gkeys.includes('FactSales.Transaction_ID')) {
      el.querySelectorAll('tbody tr:not(.tot)').forEach(tr => {
        tr.addEventListener('click', () => select(pg, v, gkeys[0], tr.dataset.v));
        tr.addEventListener('contextmenu', e => { const dk = gkeys.find(k => DRILL_TARGET[k]); if (dk) { e.preventDefault(); const i = gkeys.indexOf(dk); drill(dk, rows[[...tr.parentNode.children].indexOf(tr)].vals[i]); } });
      });
    }
    return el;
  };
  R.slicer = (v, pg) => {
    const el = box(v, 'slicer'), k = key(v.field);
    if (v.mode === 'Between') {
      const iso = d => E.DAYINFO[d].Date;
      el.innerHTML = `<input type="date" min="2024-01-01" max="2024-12-31" value="${iso(state.date[0])}" aria-label="Start date"><span>–</span><input type="date" min="2024-01-01" max="2024-12-31" value="${iso(state.date[1])}" aria-label="End date">`;
      const [a, b] = el.querySelectorAll('input');
      const upd = () => { const toDay = s => Math.round((Date.parse(s + 'T00:00:00Z') - Date.UTC(2024, 0, 1)) / 864e5); let d0 = toDay(a.value), d1 = toDay(b.value);
        if (Number.isNaN(d0)) d0 = 0; if (Number.isNaN(d1)) d1 = 365; d0 = Math.max(0, Math.min(365, d0)); d1 = Math.max(d0, Math.min(365, d1)); state.date = [d0, d1]; render(); };
      a.addEventListener('change', upd); b.addEventListener('change', upd);
      return el;
    }
    const isGlobal = v.sync === 'syncProduct' || v.sync === 'syncRegion';
    const cur = v.sync === 'syncProduct' ? state.product : v.sync === 'syncRegion' ? state.region : (state.pageSlicers[pg.key] || {})[k] || null;
    const vals = E.values(k, {}).slice().sort();
    const set = val => { if (v.sync === 'syncProduct') state.product = val; else if (v.sync === 'syncRegion') state.region = val;
      else { state.pageSlicers[pg.key] = state.pageSlicers[pg.key] || {}; state.pageSlicers[pg.key][k] = val; } state.selection[pg.key] = null; render(); };
    if (v.search) {
      const id = 'dl' + Math.random().toString(36).slice(2);
      el.innerHTML = `<input type="search" list="${id}" placeholder="Search for product…" value="${esc(cur || '')}" aria-label="Search product"><datalist id="${id}">${vals.map(x => `<option value="${esc(x)}">`).join('')}</datalist>`;
      const inp = el.querySelector('input');
      inp.addEventListener('change', () => set(vals.includes(inp.value) ? inp.value : null));
      inp.addEventListener('search', () => { if (!inp.value) set(null); });
    } else {
      el.innerHTML = `<select aria-label="${esc(v.tip || label(v.field))}"><option value="">${isGlobal ? 'Global' : 'All'}</option>${vals.map(x => `<option${x === cur ? ' selected' : ''}>${esc(x)}</option>`).join('')}</select>`;
      const s = el.querySelector('select'); s.addEventListener('change', () => set(s.value || null));
    }
    return el;
  };
  function button(v, title, fn) { const el = box(v, 'btn'); el.title = title; el.setAttribute('role', 'button'); el.tabIndex = 0;
    el.addEventListener('click', fn); el.addEventListener('keydown', e => { if (e.key === 'Enter') fn(); }); return el; }
  R.nav = v => button(v, v.tip, () => { if (state.page !== v.target) { state.history.push(state.page); state.page = v.target; render(); } });
  R.clear = v => button(v, 'Reset all slicers', () => { state.product = null; state.region = null; state.date = [0, 365]; state.pageSlicers = {}; state.selection = {}; render(); });
  R.back = v => button(v, 'Back', () => { state.page = state.history.pop() || 'overview'; render(); });

  function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

  // ---------------------------------------------------------------- page render
  function render() {
    charts.splice(0).forEach(c => c.dispose());
    E.clearMemo();
    const pg = PAGES[state.page];
    stage.innerHTML = '';
    stage.style.backgroundImage = `url(${window.NIKE_BG ? window.NIKE_BG[pg.key] : 'assets/bg_' + pg.key + '.webp'})`;
    document.title = pg.display + ' · Nike Business Dashboard (preview)';
    for (const v of pg.vis) {
      const ctx = pageCtx(pg, v);
      try { R[v.kind](v, pg, ctx); }
      catch (e) { console.error(v, e); const el = box(v, 'err'); el.textContent = 'Render error: ' + e.message; }
    }
    const sel = state.selection[pg.key];
    document.getElementById('status').innerHTML = [
      `<b>${esc(pg.display)}</b>`,
      `Period: ${E.DAYINFO[state.date[0]].Date} → ${E.DAYINFO[state.date[1]].Date}`,
      `Region: ${esc(state.region || 'Global')}`, state.product ? `Product: ${esc(state.product)}` : '',
      sel ? `Cross-filter: ${esc(sel.value)} <a href="#" id="clrsel">clear</a>` : 'Click a bar, slice or row to cross-filter · right-click a product/store to drill through'
    ].filter(Boolean).join('<span class="sep">·</span>');
    const c = document.getElementById('clrsel'); if (c) c.addEventListener('click', e => { e.preventDefault(); state.selection[pg.key] = null; render(); });
    fit();
  }
  function fit() {
    const wrap = document.getElementById('wrap'), s = Math.min(1, wrap.clientWidth / SPEC.W);
    stage.style.transform = `scale(${s})`; wrap.style.height = (SPEC.H * s) + 'px';
  }
  window.addEventListener('resize', fit);
  window.NIKE_APP = { state, render, E };
  render();
})();
