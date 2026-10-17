(() => {
  const LX = window.LX;
  const { css, fmt, pct, enc, PARTY, partyCol } = LX;
  const lab = (m) => (m == null || isNaN(m)) ? '—' : Math.abs(m) < 0.0005 ? 'Even' : (m > 0 ? 'R+' : 'D+') + (Math.abs(m) * 100).toFixed(1);
  const OFFICES = ['County Judge', 'Commissioner Pct 1', 'Commissioner Pct 2', 'Commissioner Pct 3', 'Commissioner Pct 4'];

  dash.calc('fb_by_precinct', {
    title: 'Fort Bend results per precinct',
    description: 'Each Fort Bend County Judge and Commissioner race by voting precinct: vote shares of the top four candidates and Republican-minus-Democratic margin; 2026 comes from the election-night file.',
    inputs: ['fortbend_results', 'live_2026'],
    fn: (fortbend_results, live_2026) => {
      const lab = (m) => (m == null || isNaN(m)) ? '—' : Math.abs(m) < 0.0005 ? 'Even' : (m > 0 ? 'R+' : 'D+') + (Math.abs(m) * 100).toFixed(1);
      const all = fortbend_results.map((r) => ({ ...r, status: 'final' })).concat(live_2026.filter((r) => r.level === 'fortbend').map((r) => ({
        year: r.year, race: r.race, office: r.office, precinct_set: r.plan, precinct: String(r.unit), candidate: r.candidate, party: r.party, votes: r.votes, status: r.status })));
      const tot = new Map();
      for (const r of all) if (r.party !== 'W') { const k = r.race + '|' + r.candidate; tot.set(k, (tot.get(k) || 0) + (Number(r.votes) || 0)); }
      const rankOf = new Map();
      for (const race of new Set(all.map((r) => r.race))) [...tot.entries()].filter(([k]) => k.startsWith(race + '|')).sort((a, b) => b[1] - a[1]).forEach(([k], i) => rankOf.set(k, i + 1));
      const hasR = new Set(all.filter((r) => r.party === 'R' && Number(r.votes) > 0).map((r) => r.race)), hasD = new Set(all.filter((r) => r.party === 'D' && Number(r.votes) > 0).map((r) => r.race));
      const g = new Map();
      for (const r of all) {
        const k = r.race + '|' + r.precinct;
        let o = g.get(k);
        if (!o) { o = { race: r.race, year: Number(r.year), office: r.office, precinct_set: r.precinct_set, precinct: String(r.precinct), status: r.status, rep: 0, dem: 0, total: 0, c: {} }; g.set(k, o); }
        const v = Number(r.votes) || 0; o.total += v;
        if (r.party === 'R') o.rep += v; if (r.party === 'D') o.dem += v;
        const rk = rankOf.get(r.race + '|' + r.candidate);
        if (r.party !== 'W' && rk && rk <= 4) o.c[rk] = (o.c[rk] || 0) + v;
      }
      return [...g.values()].map((o) => {
        const row = { race: o.race, year: o.year, office: o.office, precinct_set: o.precinct_set, precinct: o.precinct, status: o.status, reported: o.total > 0, total_votes: o.total, both_parties: hasR.has(o.race) && hasD.has(o.race),
          margin: o.total ? (o.rep - o.dem) / o.total : null };
        row.margin_label = lab(row.margin);
        for (let i = 1; i <= 4; i++) if (o.c[i] != null) row['c' + i + '_pct'] = o.total ? o.c[i] / o.total : null;
        return row;
      });
    },
  });

  dash.calc('fb_races', {
    title: 'Fort Bend races',
    description: 'Each Fort Bend County Judge and Commissioner race countywide (or precinct-wide): margin, precincts carried, and shift from the previous race for the same office.',
    inputs: ['fb_by_precinct'],
    fn: (fb_by_precinct) => {
      const lab = (m) => (m == null || isNaN(m)) ? '—' : Math.abs(m) < 0.0005 ? 'Even' : (m > 0 ? 'R+' : 'D+') + (Math.abs(m) * 100).toFixed(1);
      const g = new Map();
      for (const p of fb_by_precinct) {
        let o = g.get(p.race);
        if (!o) { o = { race: p.race, year: p.year, office: p.office, precinct_set: p.precinct_set, status: p.status, both: p.both_parties, rep: 0, dem: 0, total: 0, precincts: 0, reporting: 0, prec_r: 0, prec_d: 0 }; g.set(p.race, o); }
        o.precincts++; o.total += p.total_votes;
        if (p.margin != null) o.rep += p.margin * p.total_votes; // R minus D votes in this precinct
        if (p.reported) { o.reporting++; if (p.margin > 0) o.prec_r++; else if (p.margin < 0) o.prec_d++; }
      }
      const rows = [...g.values()].map((o) => ({ race: o.race, year: o.year, office: o.office, precinct_set: o.precinct_set, status: o.status, both_parties: o.both, total_votes: o.total,
        margin: o.total ? o.rep / o.total : null, precincts: o.precincts, precincts_reporting: o.reporting, precincts_r: o.prec_r, precincts_d: o.prec_d }));
      for (const r of rows) r.margin_label = lab(r.margin);
      const byOff = new Map();
      for (const r of rows) { if (!byOff.has(r.office)) byOff.set(r.office, []); byOff.get(r.office).push(r); }
      for (const list of byOff.values()) {
        list.sort((a, b) => a.year - b.year);
        // compare only races where both a Republican and a Democrat ran
        let prev = null;
        for (const r of list) {
          r.prev_race = r.both_parties && prev ? prev.race : null;
          r.shift = r.prev_race && r.status === 'final' && r.margin != null && prev.margin != null ? r.margin - prev.margin : null;
          r.shift_label = r.shift == null ? '—' : lab(r.shift);
          if (r.both_parties && r.margin != null) prev = r;
        }
      }
      return rows.sort((a, b) => a.year - b.year || a.office.localeCompare(b.office));
    },
  });

  dash.calc('fb_candidates', {
    title: 'Fort Bend candidates',
    description: 'Top four candidates in each Fort Bend race with their share of all votes cast; "winner" is set only once a count is final.',
    inputs: ['fortbend_results', 'live_2026'],
    fn: (fortbend_results, live_2026) => {
      const all = fortbend_results.map((r) => ({ race: r.race, candidate: r.candidate, party: r.party, votes: r.votes, status: 'final' }))
        .concat(live_2026.filter((r) => r.level === 'fortbend').map((r) => ({ race: r.race, candidate: r.candidate, party: r.party, votes: r.votes, status: r.status })));
      const races = new Map();
      for (const r of all) {
        let o = races.get(r.race); if (!o) { o = { total: 0, status: r.status, cand: new Map() }; races.set(r.race, o); }
        const v = Number(r.votes) || 0; o.total += v;
        if (r.party !== 'W') { const c = o.cand.get(r.candidate) || { party: r.party, votes: 0 }; c.votes += v; o.cand.set(r.candidate, c); }
      }
      const rows = [];
      for (const [race, o] of races) {
        const list = [...o.cand.entries()].sort((a, b) => b[1].votes - a[1].votes || a[0].localeCompare(b[0])).slice(0, 4);
        list.forEach(([candidate, c], i) => rows.push({ race, rank: i + 1, candidate, party: c.party, votes: c.votes, pct: o.total ? c.votes / o.total : (list.length === 1 ? 1 : null),
          unopposed: list.length === 1, status: o.status, winner: o.status === 'final' && i === 0 && (o.total > 0 || list.length === 1) }));
      }
      return rows;
    },
  });

  // ---------- page ----------
  let sortKey = 'precinct', sortDir = 1, query = '', ready = false;
  function setup() {
    if (ready) return;
    LX.mount('tab-fortbend'); ready = true;
    document.getElementById('fb-search').addEventListener('input', (e) => { query = e.target.value.trim().toLowerCase(); draw(); });
    document.querySelectorAll('#fb-table th button').forEach((b) => b.addEventListener('click', () => {
      const k = b.dataset.sort; if (sortKey === k) sortDir = -sortDir; else { sortKey = k; sortDir = k === 'precinct' ? 1 : -1; } draw();
    }));
  }

  function draw() {
    if (LX.tab() !== 'fortbend') return;
    setup();
    if (LX.localArea() !== 'fortbend') return;
    const res = dash.data('fortbend_results'), shp = dash.data('fortbend_shapes'), bp = dash.data('fb_by_precinct'), rc = dash.data('fb_races'), cd = dash.data('fb_candidates'), lv = dash.data('live_2026');
    const deps = [res, shp, bp, rc, cd, lv];
    if (!deps.every((d) => d.status === 'ok')) {
      if (deps.some((d) => d.status === 'error' || d.status === 'missing')) ['fb-map', 'fb-trend', 'fb-cands'].forEach((id) => LX.failLine(document.getElementById(id)));
      return;
    }
    const races = new Map(rc.data.map((r) => [r.race, r]));
    for (const o of LX.SCHEDULE_2026.fortbend) if (!races.has('2026 ' + o)) races.set('2026 ' + o, { race: '2026 ' + o, year: 2026, office: o, pending: true });
    const raceId = races.has(dash.params().fb_race) ? dash.params().fb_race : '2022 County Judge';
    LX.racePicker(document.getElementById('fb-race-rows'), OFFICES.map((o) => [o, o.replace('Commissioner Pct', 'Commissioner, Precinct')]),
      [...races.values()].map((r) => ({ race: r.race, year: r.year, group: r.office, yearLabel: r.year === 2026 ? '2026 (Nov. 3)' : String(r.year) })),
      raceId, (race) => dash.setParams({ fb_race: race }));
    const R = races.get(raceId), year = R.year, office = R.office;
    const pending = R.pending || !R.total_votes && !(cd.data.find((c) => c.race === raceId && c.unopposed));
    const C = cd.data.filter((c) => c.race === raceId).sort((a, b) => a.rank - b.rank);
    const precincts = bp.data.filter((p) => p.race === raceId);
    LX.liveBanner(document.getElementById('fb-live'), year, 'Fort Bend County Elections (unofficial)');
    document.querySelectorAll('#tab-fortbend [data-source="fb_races"][data-field]').forEach((el) => el.setAttribute('data-where', 'race=' + enc(raceId)));

    // takeaway
    const tk = document.getElementById('fb-take'); tk.classList.remove('dash-skeleton'); tk.replaceChildren();
    const add = (t, b, field) => { const n = document.createElement(b ? 'b' : 'span'); n.textContent = t; if (field) { n.setAttribute('data-source', 'fb_races'); n.setAttribute('data-field', field); n.setAttribute('data-where', 'race=' + enc(raceId)); } tk.append(n); };
    const oname = office === 'County Judge' ? 'county judge' : office.replace('Commissioner Pct ', 'Precinct ') + ' commissioner';
    if (pending) add(`The ${year} ${oname} race is on the ballot ${LX.ELECTION_2026}. Candidates and results will appear here on election night.`);
    else if (C.length === 1) { add(C[0].candidate, true); add(` (${C[0].party}) ran unopposed for ${oname} in ${year}.`); }
    else {
      add(C[0].candidate, true); add(R.status === 'counting' ? ` leads the ${year} ${oname} race by ` : ` won the ${year} ${oname} race by `);
      add(Math.abs((C[0].pct - C[1].pct) * 100).toFixed(1) + ' points', true); add(` (${R.margin_label}).`);
      if (R.prev_race && R.shift != null) { add(` Compared with ${R.prev_race}, the margin moved `); add(R.shift_label, true, 'shift_label'); add(R.shift > 0 ? ' toward Republicans.' : R.shift < 0 ? ' toward Democrats.' : '.'); }
    }

    // candidate cards
    const box = document.getElementById('fb-cands'); box.classList.remove('dash-skeleton');
    if (!C.length) { const m = document.createElement('div'); m.className = 'lx-card lx-empty'; m.textContent = 'Candidates will appear here once Fort Bend County posts election-night results.'; box.replaceChildren(m); }
    else box.replaceChildren(...C.map((c) => {
      const card = document.createElement('div'); card.className = 'lx-card lx-cand' + (c.rank === 1 && !pending ? ' win' : '');
      const col = partyCol(c.party), where = 'race=' + enc(c.race) + '&rank=' + c.rank;
      const ini = document.createElement('div'); ini.className = 'lx-initials'; ini.style.background = col; ini.textContent = LX.initials(c.candidate); ini.setAttribute('aria-hidden', 'true');
      const body = document.createElement('div'); body.className = 'lx-cand-body';
      const nm = document.createElement('div'); nm.className = 'lx-cand-name'; nm.textContent = c.candidate; nm.setAttribute('data-source', 'fb_candidates'); nm.setAttribute('data-field', 'candidate'); nm.setAttribute('data-where', where);
      const pt = document.createElement('div'); pt.className = 'lx-cand-party';
      const pn = document.createElement('span'); pn.style.color = col; pn.textContent = (PARTY[c.party] || c.party) + ' (' + c.party + ')'; pt.append(pn);
      const word = c.unopposed ? 'Unopposed' : pending ? '' : LX.stateWord(c.status, c.rank === 1);
      if (word) { const b = document.createElement('span'); b.className = 'lx-badge'; b.textContent = word; pt.append(b); }
      const pc = document.createElement('div'); pc.className = 'lx-cand-pct'; pc.textContent = c.pct == null ? '—' : pct(c.pct); pc.setAttribute('data-source', 'fb_candidates'); pc.setAttribute('data-field', 'pct'); pc.setAttribute('data-where', where);
      const vt = document.createElement('div'); vt.className = 'lx-cand-votes'; const vs = document.createElement('span'); vs.textContent = fmt(c.votes); vs.setAttribute('data-source', 'fb_candidates'); vs.setAttribute('data-field', 'votes'); vs.setAttribute('data-where', where); vt.append(vs, document.createTextNode(' votes'));
      const bar = document.createElement('div'); bar.className = 'lx-cand-bar'; const bi = document.createElement('i'); bi.style.width = ((c.pct || 0) * 100).toFixed(1) + '%'; bi.style.background = col; bar.append(bi);
      body.append(nm, pt, pc, vt, bar); card.append(ini, body); return card;
    }));

    // KPIs
    const setK = (id, v) => { const el = document.getElementById(id); el.textContent = v; el.classList.remove('dash-skeleton'); };
    setK('fb-k-margin', pending ? '—' : C.length === 1 ? 'Unopposed' : R.margin_label);
    document.getElementById('fb-k-margin').style.color = pending || C.length === 1 ? '' : R.margin > 0 ? css('--lx-rep') : css('--lx-dem');
    document.getElementById('fb-k-shift').textContent = R.shift != null ? `Shift: ${R.shift_label}${R.prev_race ? ' vs ' + R.prev_race : ''}` : '';
    setK('fb-k-prec', pending ? '—' : `${R.precincts_r} R · ${R.precincts_d} D`);
    document.getElementById('fb-k-prec-sub').textContent = pending ? '' : R.status === 'counting' ? `${R.precincts_reporting} of ${R.precincts} precincts reporting` : `of ${R.precincts} precincts${office === 'County Judge' ? ' countywide' : ' in ' + office.replace('Commissioner ', '')}`;
    setK('fb-k-votes', pending ? '—' : fmt(R.total_votes));

    drawMap(R, precincts, shp.data, pending);
    drawTrend(rc.data, raceId, office);
    drawTable(precincts, C, pending);
  }

  function drawMap(R, precincts, shapes, pending) {
    const el = document.getElementById('fb-map'); el.classList.remove('dash-skeleton');
    const set = R.precinct_set || 'p26';
        const list = shapes.filter((s) => s.set === set);
    const byP = new Map(precincts.map((p) => [p.precinct, p]));
    const muted = css('--cds-chart-muted'), blank = css('--color-bg');
    let svg = d3.select(el).select('svg');
    if (svg.empty()) { el.replaceChildren(); svg = d3.select(el).append('svg').attr('viewBox', '0 0 700 637').attr('width', '100%').attr('role', 'img').attr('aria-label', 'Fort Bend County precinct map'); svg.append('g').attr('class', 'p'); }
    const card = document.getElementById('fb-map-card'), tip = document.getElementById('fb-map-tip');
    const fill = (p) => !p ? blank : !p.reported ? muted : p.margin == null ? muted : LX.rampColor(p.margin >= 0 ? 'R' : 'D', p.margin);
    svg.select('g.p').selectAll('path').data(list, (d) => d.set + d.precinct).join('path')
      .attr('d', (d) => d.path).attr('fill', (d) => fill(byP.get(d.precinct))).attr('fill-rule', 'evenodd').attr('stroke', 'var(--color-border-line)').attr('stroke-width', 0.5)
      .on('mousemove', (event, d) => {
        const p = byP.get(d.precinct); tip.replaceChildren();
        const t = document.createElement('div'); t.className = 't'; t.textContent = `Precinct ${d.precinct} · ${R.race}`; tip.append(t);
        if (!p) LX.tipLine(tip, null, R.office === 'County Judge' ? 'No results' : 'Outside this commissioner precinct', '');
        else if (!p.reported) LX.tipLine(tip, null, 'No results yet', '');
        else { LX.tipLine(tip, null, 'Margin', p.margin_label); LX.tipLine(tip, null, 'Votes', fmt(p.total_votes)); }
        LX.placeTip(tip, card, event);
      })
      .on('mouseleave', () => { tip.style.display = 'none'; });
    const lg = document.getElementById('fb-legend'); lg.replaceChildren();
    for (const [pt, nm] of [['R', 'Republican'], ['D', 'Democrat']]) {
      const g = document.createElement('span'); g.className = 'grp'; g.append(document.createTextNode(nm + ' '));
      LX.RAMP[pt].forEach((col) => { const s = document.createElement('i'); s.className = 'sw'; s.style.background = col; s.style.marginRight = '1px'; g.append(s); });
      lg.append(g);
    }
    const n = document.createElement('span'); n.textContent = 'margin, light → dark: <10 · 10–20 · 20–40 · 40–60 · 60+ pts'; lg.append(n);
    if (R.office !== 'County Judge') { const g = document.createElement('span'); g.className = 'grp'; const s = document.createElement('i'); s.className = 'sw'; s.style.background = blank; s.style.border = '1px solid var(--color-border-line)'; g.append(s, document.createTextNode('Outside this precinct')); lg.append(g); }
    document.getElementById('fb-map-note').textContent = pending ? 'Precincts fill in as Fort Bend reports on election night.' : `Voting precincts as drawn for ${R.year}${R.precinct_set === 'p20' && R.year < 2020 ? ' (2020 boundaries, which match every precinct number used that year)' : ''}. Darker means a bigger margin.`;
  }

  function drawTrend(races, raceId, office) {
    const el = document.getElementById('fb-trend'); el.classList.remove('dash-skeleton'); el.replaceChildren();
    const W = Math.max(280, el.clientWidth), H = 240;
    const ser = OFFICES.map((o, i) => ({ o, col: dash.colors[i], focus: o === office, pts: races.filter((r) => r.office === o && r.margin != null && Math.abs(r.margin) < 0.999).sort((a, b) => a.year - b.year) }));
    const all = ser.flatMap((s) => s.pts.map((p) => p.margin));
    let lo = Math.min(0, d3.min(all) ?? 0), hi = Math.max(0, d3.max(all) ?? 0); const pad = (hi - lo) * 0.1 || 0.05; lo -= pad; hi += pad;
    const y = d3.scaleLinear([lo, hi], [H - 26, 10]).nice(5);
    const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', '100%').attr('role', 'img').attr('aria-label', 'Margin over time');
    const ticks = y.ticks(5);
    const tl = svg.append('g').selectAll('text').data(ticks).join('text').attr('x', 0).attr('y', (d) => y(d)).attr('dy', '0.32em').attr('fill', 'var(--color-fg-muted)').attr('font-size', 'var(--cds-font-size-caption)').text((d) => lab(d));
    let ml = 0; tl.each(function () { ml = Math.max(ml, this.getComputedTextLength()); });
    const left = ml + 8, x = d3.scaleLinear([2012, 2026], [left, W - 12]);
    svg.append('g').selectAll('line').data(ticks).join('line').attr('x1', left).attr('x2', W - 12).attr('y1', (d) => y(d)).attr('y2', (d) => y(d)).attr('stroke', (d) => d === 0 ? 'var(--cds-chart-reference)' : 'var(--cds-chart-grid)');
    svg.append('g').selectAll('text').data([2012, 2016, 2020, 2024, 2026]).join('text').attr('x', (d) => x(d)).attr('y', H - 6).attr('text-anchor', (d) => d === 2026 ? 'end' : 'middle').attr('fill', 'var(--color-fg-muted)').attr('font-size', 'var(--cds-font-size-caption)').text((d) => d);
    const line = d3.line().x((d) => x(d.year)).y((d) => y(d.margin));
    for (const s of ser.slice().sort((a, b) => a.focus - b.focus)) {
      svg.append('path').datum(s.pts).attr('d', line).attr('fill', 'none').attr('stroke', s.focus ? s.col : 'var(--cds-chart-muted)').attr('stroke-width', s.focus ? 2.2 : 1.2).attr('stroke-linecap', 'round').attr('stroke-linejoin', 'round');
      svg.append('g').selectAll('circle').data(s.pts).join('circle').attr('cx', (d) => x(d.year)).attr('cy', (d) => y(d.margin)).attr('r', (d) => d.race === raceId ? 5 : s.focus ? 3 : 2)
        .attr('fill', (d) => d.race === raceId ? 'var(--color-panel)' : s.focus ? s.col : 'var(--cds-chart-muted)').attr('stroke', s.focus ? s.col : 'none').attr('stroke-width', (d) => d.race === raceId ? 2.5 : 0)
        .style('cursor', 'pointer').on('click', (e, d) => dash.setParams({ fb_race: d.race }))
        .append('title').text((d) => `${d.race}: ${d.margin_label}`);
    }
    const lg = document.getElementById('fb-trend-legend'); lg.replaceChildren();
    const g = document.createElement('span'); g.className = 'grp'; const s = document.createElement('i'); s.className = 'sw'; s.style.background = ser.find((x) => x.focus).col; s.style.height = '3px'; s.style.verticalAlign = '3px'; g.append(s, document.createTextNode(office)); lg.append(g);
    const g2 = document.createElement('span'); g2.className = 'grp'; const s2 = document.createElement('i'); s2.className = 'sw'; s2.style.background = 'var(--cds-chart-muted)'; s2.style.height = '3px'; s2.style.verticalAlign = '3px'; g2.append(s2, document.createTextNode('Other Fort Bend races (unopposed races left out)')); lg.append(g2);
  }

  function drawTable(precincts, C, pending) {
    document.querySelectorAll('#fb-table th[data-field^="c"]').forEach((th) => {
      const f = th.dataset.field; if (!/^c\d_pct$/.test(f)) return;
      const c = C[Number(f[1]) - 1]; th.style.display = c ? '' : 'none';
      th.querySelector('button').dataset.label = c ? `${c.candidate} (${c.party})` : '—';
    });
    if (/^c\d_pct$/.test(sortKey) && !C[Number(sortKey[1]) - 1]) { sortKey = 'precinct'; sortDir = 1; }
    let list = precincts.filter((p) => !query || p.precinct.includes(query));
    list = list.slice().sort((a, b) => {
      const va = sortKey === 'precinct' ? Number(a.precinct) : a[sortKey], vb = sortKey === 'precinct' ? Number(b.precinct) : b[sortKey];
      if (va == null && vb == null) return 0; if (va == null) return 1; if (vb == null) return -1; return (va - vb) * sortDir;
    });
    document.getElementById('fb-count').textContent = pending ? 'No results yet.' : `${list.length} precincts`;
    document.querySelectorAll('#fb-table th').forEach((th) => {
      const b = th.querySelector('button'), k = b.dataset.sort;
      th.setAttribute('aria-sort', k === sortKey ? (sortDir > 0 ? 'ascending' : 'descending') : 'none');
      b.textContent = b.dataset.label + (k === sortKey ? (sortDir > 0 ? ' ▲' : ' ▼') : '');
    });
    const tb = document.querySelector('#fb-table tbody');
    tb.replaceChildren(...list.map((p) => {
      const tr = document.createElement('tr'); tr.dataset.key = enc(p.race) + ',' + enc(p.precinct);
      const td = (t, cls) => { const x = document.createElement('td'); x.textContent = t; if (cls) x.className = cls; tr.append(x); return x; };
      td(p.precinct);
      C.forEach((c, i) => { const v = p['c' + (i + 1) + '_pct']; const cell = td(v == null ? '—' : pct(v), i >= 2 ? 'lx-hide-narrow' : ''); cell.style.color = partyCol(c.party); });
      td(C.length === 1 ? 'Unopposed' : p.margin_label, C.length === 1 ? '' : p.margin > 0 ? 'lx-r' : p.margin < 0 ? 'lx-d' : '');
      td(p.reported ? fmt(p.total_votes) : '—', 'lx-hide-narrow');
      return tr;
    }));
  }

  dash.onData(draw);
})();
