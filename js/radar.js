(() => {
  // County Groups tab: how statewide candidates did across groups of counties.
  // Groups come from county_groups (ACS 2020–2024 race/ethnicity and median income, NCHS 2023 urban–rural codes,
  // and a k-means clustering of all three); votes come from by_county, the same county results the Statewide tab uses.
  const LX = window.LX;
  const { css, fmt, pct } = LX;
  const OFFICES = [['Governor', 'Governor'], ['Senate', 'U.S. Senate'], ['Lt. Governor', 'Lt. Governor'], ['Attorney General', 'Attorney General'], ['Comptroller', 'Comptroller'],
    ['Land Commissioner', 'Land Commissioner'], ['Agriculture Commissioner', 'Agriculture Commissioner'], ['Railroad Commissioner', 'Railroad Commissioner'], ['Supreme Court', 'Texas Supreme Court']];
  const officeOf = (o) => o.startsWith('Railroad Commissioner') ? 'Railroad Commissioner' : o.startsWith('Supreme Court') ? 'Supreme Court' : o;
  const BY = {
    cluster: { label: 'Combined groups (machine learning)', field: 'cluster', order: 'cluster_order',
      note: 'Eight groups found by a k-means clustering of every county on race and ethnicity, median household income and how urban it is, each of the three weighted equally. Group names describe each group\'s typical county.' },
    race: { label: 'Race & ethnicity', field: 'race_group', order: 'race_order', note: 'Counties grouped by their largest population group (ACS 2020–2024). "No majority group" means no group is over 50%; it includes Harris, Dallas, Tarrant, Travis, Collin and Fort Bend.' },
    income: { label: 'Median income', field: 'income_group', order: 'income_order', note: 'Counties grouped by median household income (ACS 2020–2024, in 2024 dollars).' },
    urban: { label: 'Urban–suburban–rural', field: 'urban_group', order: 'urban_order', note: 'Counties grouped by the CDC\'s 2023 urban–rural classification: urban core = central counties of metros over 1 million; suburban = their outer counties; small town = micropolitan; rural = outside any metro or micro area.' },
  };
  const CAT = ['#6a4bb0', '#1f8a8a', '#d08a1c', '#c2507a', '#7a8a2a', '#5d6b7a', '#8c5a3c', '#4f9ad6'];
  const SEQ = ['#efe6fa', '#d4bff0', '#b394e3', '#9067cf', '#6d43b5', '#4f2894'];  // stays visible on the dark theme too
  const short = (n) => LX.short(n);
  const signedPts = (m) => m == null || isNaN(m) ? '—' : Math.abs(m) < 0.0005 ? 'Even' : (m > 0 ? 'R+' : 'D+') + (Math.abs(m) * 100).toFixed(1);

  let ready = false, hot = null;
  function setup() {
    if (ready) return;
    LX.mount('tab-groups'); ready = true;
    document.querySelectorAll('[data-grby]').forEach((b) => b.addEventListener('click', () => dash.setParams({ gr_by: b.dataset.grby })));
    document.getElementById('gr-cmp').addEventListener('click', () => dash.setParams({ gr_cmp: dash.params().gr_cmp === 'off' ? 'on' : 'off' }));
    document.querySelectorAll('[data-grm]').forEach((b) => b.addEventListener('click', () => dash.setParams({ gr_measure: b.dataset.grm })));
  }
  const params = () => { const p = dash.params(); return { race: p.gr_race || null, by: BY[p.gr_by] ? p.gr_by : 'cluster', cmp: p.gr_cmp !== 'off', measure: p.gr_measure === 'turnout' ? 'turnout' : 'share' }; };
  const TURN = '#2e8a6f';  // turnout color used elsewhere on the dashboard
  const pp = (d) => d == null || isNaN(d) ? '—' : (d > 0 ? '+' : d < 0 ? '−' : '') + Math.abs(d * 100).toFixed(1) + ' pts';

  function draw() {
    if (LX.tab() !== 'groups') return;
    setup();
    const grp = dash.data('county_groups'), bc = dash.data('by_county'), cs = dash.data('candidates_statewide'), shp = dash.data('county_shapes');
    const deps = [grp, bc, cs, shp];
    if (!deps.every((d) => d.status === 'ok')) {
      if (deps.some((d) => d.status === 'error' || d.status === 'missing')) ['gr-radar', 'gr-map'].forEach((id) => LX.failLine(document.getElementById(id)));
      return;
    }
    const p = params(), B = BY[p.by];
    document.querySelectorAll('[data-grby]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.grby === p.by)));
    document.querySelectorAll('[data-grm]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.grm === p.measure)));
    const T = LX.turnout();
    // races with both a Republican and a Democrat and some votes
    const byRace = d3.group(bc.data, (r) => r.race);
    const races = [...byRace.entries()].filter(([, rows]) => d3.sum(rows, (r) => r.rep_votes) > 0 && d3.sum(rows, (r) => r.dem_votes) > 0)
      .map(([race, rows]) => ({ race, year: rows[0].year, office: rows[0].office, prev: rows[0].prev_race }));
    races.sort((a, b) => a.year - b.year || a.race.localeCompare(b.race));
    const latestSenate = races.filter((r) => r.office === 'Senate').pop() || races[races.length - 1];
    const R = races.find((r) => r.race === p.race) || latestSenate;
    LX.racePicker(document.getElementById('gr-pick'), OFFICES, races.map((r) => ({ race: r.race, year: r.year, group: officeOf(r.office),
      yearLabel: String(r.year) + (r.office.startsWith('Supreme Court') ? ' · ' + r.office.replace('Supreme Court, ', '') : r.office.includes('unexpired') ? ' (unexpired term)' : '') })),
      R.race, (race) => dash.setParams({ gr_race: race }));

    // groups
    const G = grp.data.map((g) => ({ ...g, population: +g.population, median_income: +g.median_income, pct_hispanic: +g.pct_hispanic, pct_white: +g.pct_white, pct_black: +g.pct_black, pct_asian: +g.pct_asian }));
    const groupOf = new Map(G.map((g) => [g.county_fips, g[B.field]]));
    const order = [...new Map(G.map((g) => [g[B.field], +g[B.order]])).entries()].sort((a, b) => a[1] - b[1]).map((x) => x[0]);
    const color = new Map(order.map((g, i) => [g, p.by === 'cluster' ? CAT[i % CAT.length] : SEQ[Math.round(i * (SEQ.length - 1) / Math.max(1, order.length - 1))]]));
    // turnout per group = ballots cast in its counties / registered voters there, for the race's election year
    const sum = (race) => {
      const year = Number(String(race).slice(0, 4));
      const m = new Map(order.map((g) => [g, { group: g, year, counties: 0, population: 0, rep: 0, dem: 0, total: 0, reg: 0, ballots: 0, toCounties: 0, live: false }]));
      for (const r of byRace.get(race) || []) { const o = m.get(groupOf.get(r.county_fips)); if (!o) continue; o.rep += r.rep_votes; o.dem += r.dem_votes; o.total += r.total_votes; }
      for (const g of G) {
        const o = m.get(g[B.field]); o.counties++; o.population += g.population;
        const t = T ? T.county.get(year + '|' + g.county_fips) : null;
        if (t) { o.reg += t.registered; o.ballots += t.ballots; o.toCounties++; if (t.live) o.live = true; }
      }
      const all = d3.sum([...m.values()], (o) => o.total);
      for (const o of m.values()) { o.rs = o.total ? o.rep / o.total : null; o.ds = o.total ? o.dem / o.total : null; o.margin = o.total ? (o.rep - o.dem) / o.total : null; o.share = all ? o.total / all : null;
        o.turnout = o.reg ? o.ballots / o.reg : null; }  // a county missing from the turnout file (one in 2008) is left out; the tooltip says so
      return order.map((g) => m.get(g));
    };
    const cur = sum(R.race), prev = R.prev && byRace.has(R.prev) ? sum(R.prev) : null;
    const showPrev = p.cmp && prev;
    const cands = (race) => {
      const c = cs.data.filter((x) => x.race === race);
      return { R: c.filter((x) => x.party === 'R').sort((a, b) => a.rank - b.rank)[0], D: c.filter((x) => x.party === 'D').sort((a, b) => a.rank - b.rank)[0] };
    };
    const C = cands(R.race), PC = prev ? cands(R.prev) : null;
    const nameR = C.R ? C.R.candidate : 'Republican', nameD = C.D ? C.D.candidate : 'Democrat';
    const RED = css('--lx-rep'), BLUE = css('--lx-dem');
    const cmpBtn = document.getElementById('gr-cmp');
    cmpBtn.hidden = !prev; cmpBtn.setAttribute('aria-pressed', String(!!showPrev)); cmpBtn.textContent = prev ? (p.measure === 'turnout' ? `Compare with ${R.prev.slice(0, 4)}` : `Compare with ${R.prev}`) : '';

    // takeaway
    const tk = document.getElementById('gr-take'); tk.classList.remove('dash-skeleton'); tk.replaceChildren();
    const add = (t, b) => { const n = document.createElement(b ? 'b' : 'span'); n.textContent = t; tk.append(n); };
    const ok = cur.filter((o) => o.total > 0);
    if (!ok.length) add(`No county results for ${R.race} yet.`);
    else {
      const bestR = ok.reduce((a, b) => (b.rs > a.rs ? b : a)), bestD = ok.reduce((a, b) => (b.ds > a.ds ? b : a));
      add(`In the ${R.race} race, `); add(nameR, true); add(' (R) ran strongest in the ');
      add(bestR.group, true); add(` group (${pct(bestR.rs)}), and `); add(nameD, true); add(' (D) in the '); add(bestD.group, true); add(` group (${pct(bestD.ds)}).`);
      if (prev) {
        const sh = ok.map((o, i) => ({ g: o.group, s: prev[i].margin == null ? null : o.margin - prev[i].margin })).filter((x) => x.s != null);
        if (sh.length) {
          const big = sh.reduce((a, b) => (Math.abs(b.s) > Math.abs(a.s) ? b : a));
          add(` Compared with ${R.prev}, the biggest swing was in the `); add(big.g, true); add(` group: ${signedPts(big.s).replace('R+', '').replace('D+', '')} points toward ${big.s > 0 ? 'Republicans' : 'Democrats'}.`);
        }
      }
    }
    const tok = cur.filter((o) => o.turnout != null);
    if (tok.length > 1) {
      const hi = tok.reduce((a, b) => (b.turnout > a.turnout ? b : a)), lo = tok.reduce((a, b) => (b.turnout < a.turnout ? b : a));
      add(` ${cur[0].live ? 'Turnout counted so far' : `Turnout in ${cur[0].year}`} was highest in the `); add(hi.group, true); add(` group (${pct(hi.turnout)}) and lowest in the `); add(lo.group, true); add(` group (${pct(lo.turnout)}).`);
    }
    document.getElementById('gr-by-note').textContent = B.note;
    drawRadar(cur, showPrev ? prev : null, { nameR, nameD, RED, BLUE, race: R.race, prevRace: R.prev, PC, color, measure: p.measure });
    drawMap(G, shp.data, B, color, order);
    drawTable(cur, prev, R, color);
  }

  function drawRadar(cur, prev, o) {
    const el = document.getElementById('gr-radar'); el.classList.remove('dash-skeleton'); el.replaceChildren();
    const W = Math.max(300, Math.min(620, el.clientWidth || 560)), narrow = W < 460, H = W * (narrow ? 0.95 : 0.86);
    const cx = W / 2, cy = H / 2 + 4, rad = Math.max(80, Math.min(W / 2 - (narrow ? 78 : 122), H / 2 - 52));
    const n = cur.length, ang = (i) => -Math.PI / 2 + (2 * Math.PI * i) / n;
    const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', '100%').attr('role', 'img')
      .attr('aria-label', `Radar chart of ${o.measure === 'turnout' ? 'turnout' : o.race + ' vote share'} by county group`).style('overflow', 'visible');
    const r = d3.scaleLinear([0, 1], [0, rad]);
    const grid = svg.append('g');
    for (const t of [0.25, 0.5, 0.75, 1]) {
      grid.append('polygon').attr('points', d3.range(n).map((i) => [cx + Math.cos(ang(i)) * r(t), cy + Math.sin(ang(i)) * r(t)].join(',')).join(' '))
        .attr('fill', 'none').attr('stroke', css('--cds-chart-grid') || css('--cds-chart-axis')).attr('stroke-width', t === 0.5 ? 1.4 : 0.8).attr('stroke-dasharray', t === 0.5 ? null : '2 3');
      grid.append('text').attr('x', cx + 3).attr('y', cy - r(t) + 11).attr('font-size', 10).attr('fill', css('--color-fg-muted')).text(t * 100 + '%');
    }
    d3.range(n).forEach((i) => grid.append('line').attr('x1', cx).attr('y1', cy).attr('x2', cx + Math.cos(ang(i)) * rad).attr('y2', cy + Math.sin(ang(i)) * rad)
      .attr('stroke', css('--cds-chart-axis')).attr('stroke-width', 0.6).attr('opacity', 0.6));
    const pts = (rows, key) => rows.map((d, i) => d[key] == null ? null : [cx + Math.cos(ang(i)) * r(d[key]), cy + Math.sin(ang(i)) * r(d[key])]);
    const shape = (rows, key, col, dashed) => {
      const P = pts(rows, key); if (P.some((x) => !x)) return;
      svg.append('polygon').attr('points', P.map((x) => x.join(',')).join(' ')).attr('fill', dashed ? 'none' : col).attr('fill-opacity', 0.14)
        .attr('stroke', col).attr('stroke-width', dashed ? 1.4 : 2.2).attr('stroke-dasharray', dashed ? '5 4' : null).attr('stroke-linejoin', 'round').attr('opacity', dashed ? 0.75 : 1);
    };
    const keys = o.measure === 'turnout' ? [['turnout', TURN]] : [['rs', o.RED], ['ds', o.BLUE]];
    if (prev) for (const [key, col] of keys) shape(prev, key, col, true);
    for (const [key, col] of keys) shape(cur, key, col);
    for (const [key, col] of keys) pts(cur, key).forEach((x) => x && svg.append('circle').attr('cx', x[0]).attr('cy', x[1]).attr('r', 3.2).attr('fill', col));
    // axis labels: group name (wrapped) and county count, with a color key matching the map
    cur.forEach((d, i) => {
      const a = ang(i), lx = cx + Math.cos(a) * (rad + 14), ly = cy + Math.sin(a) * (rad + 14);
      const anchor = Math.abs(Math.cos(a)) < 0.25 ? 'middle' : Math.cos(a) > 0 ? 'start' : 'end';
      const words = d.group.split(' '), lines = []; let line = '';
      const maxCh = narrow ? 12 : 16;
      for (const w of words) { if ((line + ' ' + w).trim().length > maxCh && line) { lines.push(line); line = w; } else line = (line + ' ' + w).trim(); }
      lines.push(line);
      const t = svg.append('text').attr('x', lx).attr('y', ly).attr('text-anchor', anchor).attr('font-size', narrow ? 10.5 : 12).attr('fill', css('--color-fg'))
        .attr('dominant-baseline', Math.sin(a) < -0.5 ? 'auto' : Math.sin(a) > 0.5 ? 'hanging' : 'middle');
      const dy0 = Math.sin(a) < -0.5 ? -(lines.length) * 1.15 + 1 : Math.sin(a) > 0.5 ? 0 : -(lines.length - 1) * 0.575;
      lines.forEach((l, k) => t.append('tspan').attr('x', lx).attr('dy', k === 0 ? dy0 + 'em' : '1.15em').attr('font-weight', 600).text(l));
      t.append('tspan').attr('x', lx).attr('dy', '1.15em').attr('fill', css('--color-fg-muted')).attr('font-size', narrow ? 9.5 : 10.5).text(narrow ? `${d.share == null ? '—' : pct(d.share).replace('.0%', '%')} of votes` : `${d.counties} counties · ${d.share == null ? '—' : pct(d.share).replace('.0%', '%')} of votes`);
    });
    // hover targets: one wedge per group
    const tip = document.getElementById('gr-radar-tip'), card = document.getElementById('gr-radar-card');
    cur.forEach((d, i) => {
      const a0 = ang(i) - Math.PI / n, a1 = ang(i) + Math.PI / n;
      const path = d3.path(); path.moveTo(cx, cy); path.arc(cx, cy, rad + 10, a0, a1); path.closePath();
      svg.append('path').attr('d', path.toString()).attr('fill', 'transparent').style('cursor', 'default')
        .on('mousemove', (ev) => {
          tip.replaceChildren(); const t = document.createElement('div'); t.className = 't'; t.textContent = d.group; tip.append(t);
          LX.tipLine(tip, o.RED, o.nameR + ' (R)', d.rs == null ? '—' : pct(d.rs));
          LX.tipLine(tip, o.BLUE, o.nameD + ' (D)', d.ds == null ? '—' : pct(d.ds));
          LX.tipLine(tip, null, 'Margin', signedPts(d.margin));
          if (prev && prev[i].margin != null) LX.tipLine(tip, null, `${o.prevRace} margin`, signedPts(prev[i].margin));
          LX.tipLine(tip, o.measure === 'turnout' ? TURN : null, d.live ? 'Turnout so far' : `Turnout ${d.year}`, d.turnout == null ? '—' : `${pct(d.turnout)} (${short(d.ballots)} of ${short(d.reg)})` + (d.toCounties < d.counties ? ` · ${d.toCounties} of ${d.counties} counties` : ''));
          if (prev && prev[i].turnout != null) LX.tipLine(tip, null, `Turnout ${prev[i].year}`, `${pct(prev[i].turnout)} (${d.turnout == null ? '—' : pp(d.turnout - prev[i].turnout)})`);
          LX.tipLine(tip, null, 'Votes', `${fmt(d.total)} (${d.share == null ? '—' : pct(d.share)} of state)`);
          LX.tipLine(tip, null, 'Counties', `${d.counties} · ${short(d.population)} people`);
          LX.placeTip(tip, card, ev);
          if (hot !== d.group) { hot = d.group; highlight(); }
        })
        .on('mouseleave', () => { tip.style.display = 'none'; hot = null; highlight(); });
    });
    const lg = document.getElementById('gr-legend'); lg.replaceChildren();
    const item = (col, text, dashed) => { const g = document.createElement('span'); g.className = 'grp'; const s = document.createElement('i'); s.className = 'sw';
      if (dashed) { s.style.background = 'none'; s.style.border = `1.5px dashed ${col}`; } else s.style.background = col; g.append(s, document.createTextNode(text)); lg.append(g); };
    if (o.measure === 'turnout') {
      item(TURN, `Turnout, ${cur[0].year}`); if (prev) item(TURN, `Turnout, ${prev[0].year}`, true);
      const n2 = document.createElement('span'); n2.textContent = 'Ballots cast as a share of registered voters in each group\'s counties; the bold ring is 50%.'; lg.append(n2);
      return;
    }
    item(o.RED, `${o.nameR} (R)`); item(o.BLUE, `${o.nameD} (D)`);
    if (prev && o.PC) { item(o.RED, `${o.PC.R ? o.PC.R.candidate : 'R'}, ${o.prevRace}`, true); item(o.BLUE, `${o.PC.D ? o.PC.D.candidate : 'D'}, ${o.prevRace}`, true); }
    const n2 = document.createElement('span'); n2.textContent = 'Share of all votes cast in each group; the bold ring is 50%.'; lg.append(n2);
  }

  let mapSel = null;
  function highlight() {
    if (!mapSel) return;
    mapSel.attr('fill-opacity', (d) => hot == null || d._g === hot ? 1 : 0.18);
    document.querySelectorAll('#gr-table tbody tr').forEach((tr) => tr.classList.toggle('sel', tr.dataset.key === hot));
  }

  function drawMap(G, shapes, B, color, order) {
    const el = document.getElementById('gr-map'); el.classList.remove('dash-skeleton');
    const by = new Map(G.map((g) => [g.county_fips, g]));
    let svg = d3.select(el).select('svg');
    if (svg.empty()) { el.replaceChildren(); svg = d3.select(el).append('svg').attr('viewBox', '0 0 678 645').attr('width', '100%').attr('role', 'img').attr('aria-label', 'Map of Texas counties by group'); const zm = LX.zoomMap(el, svg, 678, 645); zm.layer.append('g').attr('class', 'cties'); }
    const tip = document.getElementById('gr-map-tip'), card = document.getElementById('gr-map-card');
    const NCHS = { 1: 'Urban core', 2: 'Suburban', 3: 'Medium metro', 4: 'Small metro', 5: 'Small town (micropolitan)', 6: 'Rural' };
    mapSel = svg.select('g.cties').selectAll('path.cty').data(shapes.map((s) => ({ ...s, _g: (by.get(s.county_fips) || {})[B.field] })), (d) => d.county_fips).join('path')
      .attr('class', 'cty').attr('d', (d) => d.path).attr('fill', (d) => color.get(d._g) || css('--cds-chart-muted'))
      .on('mousemove', (ev, d) => {
        const g = by.get(d.county_fips); tip.replaceChildren();
        const t = document.createElement('div'); t.className = 't'; t.textContent = `${d.county} County`; tip.append(t);
        if (g) {
          LX.tipLine(tip, color.get(d._g), 'Group', d._g);
          LX.tipLine(tip, null, 'Hispanic · White', `${pct(g.pct_hispanic).replace('.0%', '%')} · ${pct(g.pct_white).replace('.0%', '%')}`);
          LX.tipLine(tip, null, 'Black · Asian', `${pct(g.pct_black).replace('.0%', '%')} · ${pct(g.pct_asian).replace('.0%', '%')}`);
          LX.tipLine(tip, null, 'Median household income', '$' + fmt(g.median_income));
          LX.tipLine(tip, null, 'Type', NCHS[g.nchs_code] || '—');
          LX.tipLine(tip, null, 'Population', fmt(g.population));
        }
        LX.placeTip(tip, card, ev);
      })
      .on('mouseleave', () => { tip.style.display = 'none'; });
    highlight();
    document.getElementById('gr-map-title').textContent = 'Which counties are in each group';
    const lg = document.getElementById('gr-map-legend'); lg.replaceChildren();
    order.forEach((g) => { const s = document.createElement('span'); s.className = 'grp'; const i = document.createElement('i'); i.className = 'sw'; i.style.background = color.get(g); s.append(i, document.createTextNode(g)); lg.append(s); });
  }

  function drawTable(cur, prev, R, color) {
    const tb = document.querySelector('#gr-table tbody');
    document.getElementById('gr-th-shift').textContent = prev ? `Shift vs ${R.prev}` : 'Shift';
    document.getElementById('gr-th-to').textContent = cur[0].live ? 'Turnout so far' : `Turnout ${cur[0].year}`;
    document.getElementById('gr-th-toch').textContent = prev ? `Turnout change vs ${prev[0].year}` : 'Turnout change';
    tb.replaceChildren(...cur.map((d, i) => {
      const tr = document.createElement('tr'); tr.dataset.key = d.group;
      const td = (t, cls, col) => { const c = document.createElement('td'); c.textContent = t; if (cls) c.className = cls; if (col) c.style.color = col; tr.append(c); return c; };
      const c0 = td(''); const sw = document.createElement('i'); sw.className = 'sw'; sw.style.cssText = `display:inline-block;width:.6rem;height:.6rem;border-radius:2px;margin-right:.4rem;background:${color.get(d.group)}`; c0.append(sw, document.createTextNode(d.group));
      td(String(d.counties)); td(short(d.population), 'lx-hide-narrow'); td(d.share == null ? '—' : pct(d.share), 'lx-hide-narrow');
      td(d.rs == null ? '—' : pct(d.rs)); td(d.ds == null ? '—' : pct(d.ds));
      td(signedPts(d.margin), '', d.margin == null ? '' : d.margin > 0 ? css('--lx-rep') : css('--lx-dem'));
      const s = prev && prev[i].margin != null && d.margin != null ? d.margin - prev[i].margin : null;
      td(s == null ? '—' : signedPts(s), 'lx-hide-narrow', s == null ? '' : s > 0 ? css('--lx-rep') : css('--lx-dem'));
      td(d.turnout == null ? '—' : pct(d.turnout));
      const tch = prev && prev[i].turnout != null && d.turnout != null ? d.turnout - prev[i].turnout : null;
      td(tch == null ? '—' : pp(tch), 'lx-hide-narrow');
      tr.addEventListener('mouseenter', () => { hot = d.group; highlight(); }); tr.addEventListener('mouseleave', () => { hot = null; highlight(); });
      return tr;
    }));
  }

  dash.onData(draw);
  window.addEventListener('resize', () => { if (LX.tab() === 'groups') draw(); });
})();
