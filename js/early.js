(() => {
  const LX = window.LX;
  const { css, fmt, pct } = LX;
  const YEARS = [2026, 2024, 2022];
  const FIRST = { 2022: '2022-10-24', 2024: '2024-10-21', 2026: '2026-10-19' };
  const COL = { 2026: '#2e8a6f', 2024: 'var(--cds-chart-reference)', 2022: 'var(--cds-chart-muted)' };
  const DASH = { 2026: null, 2024: '5 3', 2022: '2 3' };
  const short = (n) => LX.short(n);
  const signed = (r) => r == null || !isFinite(r) ? '—' : (r >= 1 ? '+' : '−') + Math.abs((r - 1) * 100).toFixed(0) + '%';
  const dayDate = (y, d) => { const t = new Date(FIRST[y] + 'T12:00:00Z'); t.setUTCDate(t.getUTCDate() + d - 1); return t; };
  const dayLabel = (y, d) => dayDate(y, d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
  const wk = (y, d) => dayDate(y, d).toLocaleDateString('en-US', { weekday: 'short', timeZone: 'UTC' });

  // ---------- data ----------
  // index: year -> ev_day -> unit -> {registered, in_person, mail, total, in_person_day}
  let idxKey = null, IDX = null, LATEST = null, COMPLETE = 0, PARTIAL = null;
  function build(hist, cur) {
    if (idxKey && idxKey[0] === hist && idxKey[1] === cur) return;
    idxKey = [hist, cur]; IDX = new Map();
    for (const r of hist.concat(cur)) {
      const y = Number(r.year), d = Number(r.ev_day);
      if (!IDX.has(y)) IDX.set(y, new Map());
      const Y = IDX.get(y);
      if (!Y.has(d)) Y.set(d, new Map());
      const ip = Number(r.in_person) || 0, ml = Number(r.mail) || 0;
      Y.get(d).set(String(r.unit), { registered: Number(r.registered) || 0, in_person: ip, mail: ml, total: ip + ml, in_person_day: Number(r.in_person_day) || 0, date: r.date });
    }
    const days = IDX.has(2026) ? [...IDX.get(2026).keys()] : [];
    LATEST = days.length ? Math.max(...days) : null;
    // a day of in-person voting counts as complete once counties holding 90% of registered voters have reported
    // in-person votes for it; the state posts most big counties the next morning, so the newest day is often partial
    COMPLETE = 0; PARTIAL = null;
    // measure against the most registered voters seen on any day, in case a day's file leaves counties out
    const regAll = Math.max(0, ...days.map((d) => (IDX.get(2026).get(d).get('TX') || {}).registered || 0));
    for (const d of days.filter((d) => d >= 1).sort((a, b) => a - b)) {
      const M = IDX.get(2026).get(d); let reg = regAll, regRep = 0, n = 0;
      for (const [u, o] of M) { if (u === 'TX') continue; if (o.in_person_day > 0) { regRep += o.registered; n++; } }  // reported votes for this day itself
      const share = reg ? regRep / reg : 0;
      // report the earliest unfinished day; a later complete day clears it
      if (share >= 0.9) { COMPLETE = d; PARTIAL = null; }
      else if (!PARTIAL) PARTIAL = { day: d, counties: n, share, votes: (M.get('TX') || {}).in_person_day || 0, in_person: (M.get('TX') || {}).in_person || 0 };
    }
    if (PARTIAL && PARTIAL.day <= COMPLETE) PARTIAL = null;
  }
  const at = (y, d, u) => { const Y = IDX.get(y); if (!Y) return null; const D = Y.get(Math.max(0, Math.min(12, d))); return D ? D.get(u) || null : null; };
  // the comparison day: 2026's latest reported day, clamped to the 12 days of in-person voting (day 0 = mail only, before day 1)
  const cmpDay = () => LATEST == null ? null : Math.max(0, Math.min(12, LATEST >= 1 ? COMPLETE : LATEST));

  // ---------- page ----------
  let ready = false, sortKey = 'total', sortDir = -1, query = '';
  function setup() {
    if (ready) return;
    LX.mount('tab-early'); ready = true;
    document.querySelectorAll('[data-evview]').forEach((b) => b.addEventListener('click', () => dash.setParams({ ev_view: b.dataset.evview })));
    document.querySelectorAll('[data-evunit]').forEach((b) => b.addEventListener('click', () => dash.setParams({ ev_unit: b.dataset.evunit })));
    document.getElementById('ev-clear').addEventListener('click', () => dash.setParams({ ev_county: null }));
    document.getElementById('ev-search').addEventListener('input', (e) => { query = e.target.value.trim().toLowerCase(); draw(); });
    document.querySelectorAll('#ev-table th button').forEach((b) => b.addEventListener('click', () => {
      const k = b.dataset.sort; if (sortKey === k) sortDir = -sortDir; else { sortKey = k; sortDir = k === 'county' ? 1 : -1; } draw();
    }));
    document.querySelector('#ev-table tbody').addEventListener('click', (e) => {
      const tr = e.target.closest('tr[data-unit]'); if (tr) dash.setParams({ ev_county: dash.params().ev_county === tr.dataset.unit ? null : tr.dataset.unit });
    });
  }
  const params = () => {
    const p = dash.params();
    return { view: ['pct', 'vs2024', 'vs2022'].includes(p.ev_view) ? p.ev_view : 'pct', unit: p.ev_unit === 'pct' ? 'pct' : 'votes',
      county: p.ev_county ? String(p.ev_county).padStart(5, '0') : null };
  };

  function draw() {
    if (LX.tab() !== 'early') return;
    setup();
    const hist = dash.data('ev_history'), cur = dash.data('ev_2026'), st = dash.data('ev_status'), shp = dash.data('county_shapes');
    const deps = [hist, cur, shp];
    if (!deps.every((d) => d.status === 'ok')) {
      if (deps.some((d) => d.status === 'error' || d.status === 'missing')) ['ev-map', 'ev-trend'].forEach((id) => LX.failLine(document.getElementById(id)));
      return;
    }
    build(hist.data, cur.data);
    const p = params(), D = cmpDay();
    const names = new Map(shp.data.map((s) => [s.county_fips, s.county]));
    document.querySelectorAll('[data-evview]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.evview === p.view)));
    document.querySelectorAll('[data-evunit]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.evunit === p.unit)));

    // status line
    const s = st.status === 'ok' ? (Array.isArray(st.data) ? st.data[0] : st.data) || {} : {};
    const live = document.getElementById('ev-live'); live.replaceChildren();
    const dot = document.createElement('span'); dot.className = 'lx-live-dot' + (LATEST != null && LATEST >= 1 && LATEST <= 12 ? ' on' : '');
    const t = document.createElement('span');
    const thru = LATEST == null ? null : at(2026, D, 'TX');
    t.textContent = LATEST == null ? 'In-person early voting runs Monday, Oct. 19 through Friday, Oct. 30. Counts will appear here as the state posts them.'
      : `Unofficial counts through ${thru && thru.date ? new Date(thru.date + 'T12:00:00Z').toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', timeZone: 'UTC' }) : '—'}${s.state_updated ? ', posted by the state ' + new Date(s.state_updated + 'T12:00:00Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' }) : ''}. In-person early voting runs Oct. 19–30; the state posts each day's numbers the next morning.`;
    if (PARTIAL) t.textContent += ` Day ${PARTIAL.day} (${wk(2026, PARTIAL.day)}, ${dayLabel(2026, PARTIAL.day)}) is still coming in: ${PARTIAL.counties} of 254 counties, with ${d3.format('.0%')(PARTIAL.share)} of registered voters, have reported ${fmt(PARTIAL.votes)} in-person votes so far. Comparisons use the last complete day until it fills in.`;
    live.append(dot, t);

    const T26 = D == null ? null : at(2026, D, 'TX'), T24 = D == null ? null : at(2024, D, 'TX'), T22 = D == null ? null : at(2022, D, 'TX');
    const final24 = at(2024, 12, 'TX'), final22 = at(2022, 12, 'TX');
    const before = D === 0;
    const reporting = (yr) => { const Y = IDX.get(yr), M = Y && Y.get(D); if (!M) return 0; let n = 0; for (const [u, o] of M) if (u !== 'TX' && o.total > 0) n++; return n; };
    const rep26 = D == null ? 0 : reporting(2026);
    const dayTxt = before ? 'before in-person voting began' : `through day ${D} of early voting`;

    // takeaway
    const tk = document.getElementById('ev-take'); tk.classList.remove('dash-skeleton'); tk.replaceChildren();
    const add = (x, b) => { const n = document.createElement(b ? 'b' : 'span'); n.textContent = x; tk.append(n); };
    if (!T26) add('2026 early-voting counts will appear here once the state posts them. The chart and map show 2022 and 2024 for comparison.');
    else if (before) {
      if (PARTIAL) {
        add('In-person early voting began '); add('Monday, Oct. 19', true); add('. The state posts most large counties\' counts the next morning; so far ');
        add(`${PARTIAL.counties} of 254 counties`, true); add(` have reported ${fmt(PARTIAL.votes)} in-person votes for day ${PARTIAL.day}. Comparisons with 2024 and 2022 start once most counties have reported. Before in-person voting, ${fmt(T26.total)} mail ballots had been reported from ${rep26} counties.`);
      } else {
        add(fmt(T26.total), true); add(` mail ballots have been reported so far, from ${rep26} of 254 counties. In-person early voting starts `); add('Monday, Oct. 19', true);
        add(`. Comparisons with 2024 and 2022 begin then: before in-person voting, counties report mail ballots on different schedules (at this point in 2024, ${reporting(2024)} counties had reported ${fmt(T24.total)} mail ballots), so early mail totals aren't comparable yet.`);
      }
    } else {
      add(fmt(T26.total), true); add(` Texans have voted early ${dayTxt} (${pct(T26.total / T26.registered)} of registered voters). That is `);
      const r24 = T26.total / T24.total, r22 = T26.total / T22.total;
      add(`${Math.abs((r24 - 1) * 100).toFixed(0)}% ${r24 >= 1 ? 'ahead of' : 'behind'}`, true); add(' 2024 and ');
      add(`${Math.abs((r22 - 1) * 100).toFixed(0)}% ${r22 >= 1 ? 'ahead of' : 'behind'}`, true); add(' 2022 on the same day.');
      if (D === 12) add(` Early voting is over; 2024 ended with ${short(final24.total)} early votes and 2022 with ${short(final22.total)}.`);
    }

    // KPIs
    const setK = (id, v, color) => { const el = document.getElementById(id); el.textContent = v; el.classList.remove('dash-skeleton'); el.style.color = color || ''; };
    const cmpCol = (r) => r == null ? '' : r >= 1 ? css('--color-ok') : css('--color-bad');
    document.getElementById('ev-k-total-label').textContent = before ? 'Mail ballots counted so far' : D === 12 ? 'Early votes, final' : 'Early votes so far';
    setK('ev-k-total', T26 ? fmt(T26.total) : '—');
    document.getElementById('ev-k-total-sub').textContent = T26 ? `${pct(T26.total / T26.registered)} of ${short(T26.registered)} registered voters${rep26 < 254 ? ` · ${rep26} of 254 counties reporting` : ''}` : '';
    const r24 = T26 && T24 && !before ? T26.total / T24.total : null, r22 = T26 && T22 && !before ? T26.total / T22.total : null;
    setK('ev-k-24', signed(r24), cmpCol(r24)); setK('ev-k-22', signed(r22), cmpCol(r22));
    document.getElementById('ev-k-24-sub').textContent = before ? 'Starts after the first day of in-person voting' : T24 ? `2024: ${fmt(T24.total)} early votes by then (${pct(T24.total / T24.registered)})` : '';
    document.getElementById('ev-k-22-sub').textContent = before ? 'Starts after the first day of in-person voting' : T22 ? `2022: ${fmt(T22.total)} early votes by then (${pct(T22.total / T22.registered)})` : '';
    document.getElementById('ev-k-24-label').textContent = before ? 'Compared with 2024' : `Compared with 2024, day ${D}`;
    document.getElementById('ev-k-22-label').textContent = before ? 'Compared with 2022' : `Compared with 2022, day ${D}`;
    setK('ev-k-mail', T26 && T26.total ? pct(T26.mail / T26.total) : '—');
    document.getElementById('ev-k-mail-sub').textContent = T26 ? (before ? 'Only mail ballots are counted before in-person voting starts' : `${fmt(T26.mail)} mail ballots; 2024 at this point: ${pct(T24.mail / (T24.total || 1))}`) : '';

    drawTrend(p, D, names);
    drawMap(p, D, shp.data);
    drawTable(p, D, names);
  }

  // ---------- cumulative chart ----------
  function drawTrend(p, D, names) {
    const el = document.getElementById('ev-trend'); el.classList.remove('dash-skeleton'); el.replaceChildren();
    const W = Math.max(280, el.clientWidth), H = 270;
    const unit = p.county || 'TX', cname = p.county ? names.get(p.county) : null;
    const val = (o) => !o ? null : p.unit === 'pct' ? o.total / (o.registered || 1) : o.total;
    const series = YEARS.map((y) => ({ y, pts: [...Array(13).keys()].map((d) => ({ d, o: at(y, d, unit) })).filter((x) => x.o && (y !== 2026 || x.d <= D)).map((x) => ({ d: x.d, v: val(x.o), o: x.o })) }));
    const maxV = d3.max(series.flatMap((s) => s.pts.map((x) => x.v))) || 1;
    const y = d3.scaleLinear([0, maxV], [H - 30, 10]).nice(5);
    const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', '100%').attr('role', 'img').attr('aria-label', 'Cumulative early votes by day');
    const fmtY = p.unit === 'pct' ? d3.format('.0%') : (v) => v >= 1e6 ? (v / 1e6).toFixed(v % 1e6 ? 1 : 0) + 'M' : v >= 1e3 ? Math.round(v / 1e3) + 'K' : String(v);
    const ticks = y.ticks(5), tg = svg.append('g');
    const tl = tg.selectAll('text').data(ticks).join('text').attr('x', 0).attr('y', (d) => y(d)).attr('dy', '0.32em').attr('fill', 'var(--color-fg-muted)').attr('font-size', 'var(--cds-font-size-caption)').text(fmtY);
    let ml = 0; tl.each(function () { ml = Math.max(ml, this.getComputedTextLength()); });
    const left = ml + 8, right = 12, x = d3.scaleLinear([0, 12], [left, W - right]);
    tg.selectAll('line').data(ticks).join('line').attr('x1', left).attr('x2', W - right).attr('y1', (d) => y(d)).attr('y2', (d) => y(d)).attr('stroke', 'var(--cds-chart-grid)');
    const xt = W < 480 ? [0, 3, 6, 9, 12] : [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
    svg.append('g').selectAll('text').data(xt).join('text').attr('x', (d) => x(d)).attr('y', H - 14).attr('text-anchor', 'middle').attr('fill', 'var(--color-fg-muted)').attr('font-size', 'var(--cds-font-size-caption)').text((d) => d === 0 ? 'Before' : String(d));
    svg.append('g').selectAll('text').data(xt.filter((d) => d > 0)).join('text').attr('x', (d) => x(d)).attr('y', H - 2).attr('text-anchor', 'middle').attr('fill', 'var(--color-fg-muted)').attr('font-size', '0.68rem').text((d) => wk(2026, d));
    const line = d3.line().x((d) => x(d.d)).y((d) => y(d.v));
    for (const s of series.slice().reverse()) {
      svg.append('path').datum(s.pts).attr('d', line).attr('fill', 'none').attr('stroke', COL[s.y]).attr('stroke-width', s.y === 2026 ? 2.6 : 1.6).attr('stroke-dasharray', DASH[s.y]).attr('stroke-linejoin', 'round');
      if (s.y === 2026) svg.append('g').selectAll('circle').data(s.pts).join('circle').attr('cx', (d) => x(d.d)).attr('cy', (d) => y(d.v)).attr('r', 3.2).attr('fill', COL[2026]);
    }
    if (D != null) svg.append('line').attr('x1', x(D)).attr('x2', x(D)).attr('y1', 10).attr('y2', H - 30).attr('stroke', 'var(--cds-chart-axis)').attr('stroke-dasharray', '2 3');
    const card = document.getElementById('ev-trend-card'), tip = document.getElementById('ev-trend-tip');
    const rule = svg.append('line').attr('y1', 10).attr('y2', H - 30).attr('stroke', 'var(--cds-chart-axis)').attr('opacity', 0);
    svg.append('rect').attr('x', left).attr('y', 0).attr('width', W - left - right).attr('height', H).attr('fill', 'transparent')
      .on('mousemove', (event) => {
        const d = Math.max(0, Math.min(12, Math.round(x.invert(d3.pointer(event)[0]))));
        rule.attr('x1', x(d)).attr('x2', x(d)).attr('opacity', 1);
        tip.replaceChildren(); const t = document.createElement('div'); t.className = 't'; t.textContent = d === 0 ? 'Before in-person voting (mail ballots)' : `Day ${d} (${wk(2026, d)})`; tip.append(t);
        for (const yr of YEARS) {
          const o = at(yr, d, unit); if (!o || (yr === 2026 && d > D)) continue;
          LX.tipLine(tip, COL[yr] === COL[2026] ? COL[2026] : css(COL[yr].slice(4, -1)), `${yr}${d > 0 ? ' · ' + dayLabel(yr, d) : ''}`, `${fmt(o.total)} · ${pct(o.total / (o.registered || 1))}`);
        }
        LX.placeTip(tip, card, event);
      })
      .on('mouseleave', () => { tip.style.display = 'none'; rule.attr('opacity', 0); });
    document.getElementById('ev-trend-title').textContent = cname ? `${cname} County: early votes by day` : 'Statewide early votes by day';
    document.getElementById('ev-trend-note').textContent = `Running total of in-person early votes plus mail ballots${p.unit === 'pct' ? ', as a share of registered voters' : ''}, by day of early voting. Day 1 is the first Monday of in-person voting in each year.${cname ? '' : ' Click a county on the map or in the table to see it here.'}`;
    const clr = document.getElementById('ev-clear'); clr.hidden = !cname; clr.textContent = cname ? `${cname} ×` : '';
    const lg = document.getElementById('ev-trend-legend'); lg.replaceChildren();
    for (const yr of YEARS) {
      const g = document.createElement('span'); g.className = 'grp';
      const sv = d3.create('svg').attr('width', 22).attr('height', 8).style('vertical-align', 'middle').style('margin-right', '4px');
      sv.append('line').attr('x1', 1).attr('x2', 21).attr('y1', 4).attr('y2', 4).attr('stroke', COL[yr]).attr('stroke-width', yr === 2026 ? 2.6 : 1.8).attr('stroke-dasharray', DASH[yr]);
      g.append(sv.node(), document.createTextNode(String(yr))); lg.append(g);
    }
  }

  // ---------- county map ----------
  const RATIO_BINS = [0.7, 0.9, 1.1, 1.3];
  function drawMap(p, D, shapes) {
    const el = document.getElementById('ev-map'); el.classList.remove('dash-skeleton');
    const muted = css('--cds-chart-muted');
    const cmpYear = p.view === 'vs2024' ? 2024 : p.view === 'vs2022' ? 2022 : null;
    const cur = (f) => D == null ? null : at(2026, D, f);
    const metric = (f) => {
      const o = cur(f); if (!o || !o.registered) return null;
      if (!cmpYear) return o.total / o.registered;
      const q = at(cmpYear, D, f); return q && q.total ? o.total / q.total : null;
    };
    // share-of-registered bins scale with the statewide figure, so the map reads the same on day 1 and day 12
    const sw = cur('TX'), base = sw && sw.registered ? sw.total / sw.registered : 0.1;
    const pctBins = [0.6, 0.85, 1.15, 1.4].map((k) => k * base);
    const DIV = ['#b65a2a', '#e3a982', '#ece9e2', '#8fc5b3', '#2e8a6f'];
    const color = (v) => v == null ? muted : cmpYear ? DIV[d3.bisect(RATIO_BINS, v)] : LX.RAMP.T[d3.bisect(pctBins, v)];
    let svg = d3.select(el).select('svg');
    if (svg.empty()) { el.replaceChildren(); svg = d3.select(el).append('svg').attr('viewBox', '0 0 678 645').attr('width', '100%').attr('role', 'img').attr('aria-label', 'Map of early votes by Texas county'); svg.append('g').attr('class', 'c'); svg.append('g').attr('class', 's'); }
    const card = document.getElementById('ev-map-card'), tip = document.getElementById('ev-map-tip');
    svg.select('g.c').selectAll('path').data(shapes, (d) => d.county_fips).join('path')
      .attr('d', (d) => d.path).attr('fill', (d) => color(metric(d.county_fips))).attr('stroke', 'var(--color-panel)').attr('stroke-width', 0.4).style('cursor', 'pointer')
      .on('mousemove', (event, d) => {
        tip.replaceChildren(); const t = document.createElement('div'); t.className = 't'; t.textContent = `${d.county} County`; tip.append(t);
        const o = cur(d.county_fips);
        if (!o) LX.tipLine(tip, null, 'No 2026 counts yet', '');
        else {
          LX.tipLine(tip, COL[2026], '2026 early votes', `${fmt(o.total)} · ${pct(o.total / (o.registered || 1))}`);
          LX.tipLine(tip, null, 'In person · by mail', `${fmt(o.in_person)} · ${fmt(o.mail)}`);
          for (const yr of [2024, 2022]) { const q = at(yr, D, d.county_fips); if (q) LX.tipLine(tip, null, `${yr}, same day`, `${fmt(q.total)} (${signed(q.total ? o.total / q.total : null)})`); }
        }
        LX.placeTip(tip, card, event);
      })
      .on('mouseleave', () => { tip.style.display = 'none'; })
      .on('click', (event, d) => dash.setParams({ ev_county: params().county === d.county_fips ? null : d.county_fips }));
    svg.select('g.s').selectAll('path').data(shapes.filter((d) => d.county_fips === p.county), (d) => d.county_fips).join('path')
      .attr('d', (d) => d.path).attr('fill', 'none').attr('stroke', css('--color-fg')).attr('stroke-width', 2.2).attr('pointer-events', 'none');
    const when = D == null ? '' : D === 0 ? 'before in-person voting' : `through day ${D}`;
    document.getElementById('ev-map-title').textContent = cmpYear ? `2026 early votes compared with ${cmpYear}, ${when}` : `2026 early votes as a share of registered voters, ${when}`;
    document.getElementById('ev-map-note').textContent = cmpYear && D === 0 ? `Before in-person voting starts, counties report mail ballots on different schedules, so this comparison isn't meaningful yet; most gaps are counties that haven't reported.` : cmpYear ? `Green: more early votes than at the same point in ${cmpYear}. Orange: fewer.` : 'Darker green: a bigger share of the county\'s registered voters has voted early. Shades are relative to the statewide figure.';
    const lg = document.getElementById('ev-legend'); lg.replaceChildren();
    const g = document.createElement('span'); g.className = 'grp';
    (cmpYear ? DIV : LX.RAMP.T).forEach((c) => { const s = document.createElement('i'); s.className = 'sw'; s.style.background = c; s.style.marginRight = '1px'; g.append(s); });
    lg.append(g);
    const n = document.createElement('span');
    n.textContent = cmpYear ? 'light → dark: 30%+ behind · 10–30% behind · within 10% · 10–30% ahead · 30%+ ahead' : 'share of registered voters: ' + [0, ...pctBins].map((b, i, a) => i === a.length - 1 ? d3.format('.0%')(b) + '+' : d3.format('.0%')(b) + '–' + d3.format('.0%')(a[i + 1])).slice(1).join(' · ');
    if (!cmpYear) n.textContent = `share of registered voters, light → dark: under ${d3.format('.1%')(pctBins[0])} · up to ${d3.format('.1%')(pctBins[1])} · ${d3.format('.1%')(pctBins[2])} · ${d3.format('.1%')(pctBins[3])} · more`;
    lg.append(n);
  }

  // ---------- table ----------
  function drawTable(p, D, names) {
    const rows = [];
    for (const [f, nm] of names) {
      const o = D == null ? null : at(2026, D, f), a = D == null ? null : at(2024, D, f), b = D == null ? null : at(2022, D, f);
      rows.push({ unit: f, county: nm, registered: o ? o.registered : null, in_person: o ? o.in_person : null, mail: o ? o.mail : null, total: o ? o.total : null,
        pct: o && o.registered ? o.total / o.registered : null, vs2024: o && a && a.total ? o.total / a.total : null, vs2022: o && b && b.total ? o.total / b.total : null });
    }
    let list = rows.filter((r) => !query || r.county.toLowerCase().includes(query));
    list.sort((a, b) => { const va = a[sortKey], vb = b[sortKey]; if (va == null && vb == null) return 0; if (va == null) return 1; if (vb == null) return -1; return (typeof va === 'string' ? va.localeCompare(vb) : va - vb) * sortDir; });
    document.getElementById('ev-table-title').textContent = D == null ? 'All 254 counties' : `All 254 counties, ${D === 0 ? 'before in-person voting' : 'through day ' + D}`;
    document.getElementById('ev-count').textContent = query ? `${list.length} of ${rows.length}` : '';
    document.querySelectorAll('#ev-table th').forEach((th) => {
      const b = th.querySelector('button'), k = b.dataset.sort;
      th.setAttribute('aria-sort', k === sortKey ? (sortDir > 0 ? 'ascending' : 'descending') : 'none');
      b.textContent = b.dataset.label + (k === sortKey ? (sortDir > 0 ? ' ▲' : ' ▼') : '');
    });
    const ok = css('--color-ok'), bad = css('--color-bad');
    const tb = document.querySelector('#ev-table tbody');
    tb.replaceChildren(...list.map((r) => {
      const tr = document.createElement('tr'); tr.dataset.unit = r.unit; tr.dataset.key = r.unit; if (r.unit === p.county) tr.className = 'sel';
      const td = (t, cls, col) => { const c = document.createElement('td'); c.textContent = t; if (cls) c.className = cls; if (col) c.style.color = col; tr.append(c); };
      const num = (v) => v == null ? '—' : fmt(v);
      td(r.county); td(num(r.registered), 'lx-hide-narrow'); td(num(r.in_person), 'lx-hide-narrow'); td(num(r.mail), 'lx-hide-narrow'); td(num(r.total));
      td(r.pct == null ? '—' : pct(r.pct));
      td(signed(r.vs2024), '', r.vs2024 == null ? '' : r.vs2024 >= 1 ? ok : bad);
      td(signed(r.vs2022), 'lx-hide-narrow', r.vs2022 == null ? '' : r.vs2022 >= 1 ? ok : bad);
      return tr;
    }));
  }

  dash.onData(draw);
})();
