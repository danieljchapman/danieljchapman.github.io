(() => {
  const LX = window.LX;
  const { css, fmt, pct, enc, PARTY, partyCol } = LX;
  const lab = (m) => (m == null || isNaN(m)) ? '—' : Math.abs(m) < 0.0005 ? 'Even' : (m > 0 ? 'R+' : 'D+') + (Math.abs(m) * 100).toFixed(1);

  // areas on the Key Local Races tab; Fort Bend keeps its own precinct view (fortbend.js)
  const AREAS = LX.LOCAL_AREAS;
  const OFFICE_NAME = { 'County Judge': 'County Judge', 'Commissioner Pct 1': 'Commissioner, Precinct 1', 'Commissioner Pct 2': 'Commissioner, Precinct 2',
    'Commissioner Pct 3': 'Commissioner, Precinct 3', 'Commissioner Pct 4': 'Commissioner, Precinct 4', 'Proposition A': 'Proposition A', 'Proposition G': 'Proposition G' };
  const NOTES = {
    tarrant: 'Tarrant County redrew its commissioner precincts in 2025, so 2026 commissioner races are not compared with earlier ones.',
    austin: 'Austin covers parts of Travis, Williamson and Hays counties. Election-night totals add Travis and Williamson; the small Hays County share is added when the city canvasses the result.',
    dallas: 'Dallas covers parts of Dallas, Collin and Denton counties; election-night totals add all three.',
    williamson: 'The 2010 Williamson County Judge result is not included; no official copy could be reached.',
    denton: 'Mary Horn ran unopposed in 2010 and 2014, so those races were not on the ballot and have no vote count.',
  };
  const isProp = (office) => /^Proposition/.test(office);
  const raceKey = (area, year, office) => `${year} ${area} ${office}`;

  dash.calc('local_candidates', {
    title: 'Key local races: candidates and choices',
    description: 'Every candidate (or For/Against) in each local race, summed across the counties that report it, with share of the vote. 2026 comes from the election-night file, or the certified candidate list before any results are posted.',
    inputs: ['local_results', 'local_2026', 'live_2026'],
    fn: (local_results, local_2026, live_2026) => {
      const live = live_2026.filter((r) => r.level === 'local');
      const liveRaces = new Set(live.map((r) => r.race));
      const rows = local_results.map((r) => ({ race: `${r.year} ${r.area} ${r.office}`, area: r.area, year: Number(r.year), office: r.office, candidate: r.candidate, party: r.party || '', votes: r.votes === '' || r.votes == null ? null : Number(r.votes), status: 'final', note: r.note || '' }))
        .concat(live.map((r) => ({ race: r.race, area: r.plan, year: Number(r.year), office: r.office, candidate: r.candidate, party: r.party || '', votes: Number(r.votes) || 0, status: r.status, note: '' })))
        .concat(local_2026.filter((r) => !liveRaces.has(`2026 ${r.area} ${r.office}`)).map((r) => ({ race: `2026 ${r.area} ${r.office}`, area: r.area, year: 2026, office: r.office, candidate: r.candidate, party: r.party || '', votes: 0, status: 'pending', note: '' })));
      const detail = new Map(local_2026.filter((r) => r.detail).map((r) => [`2026 ${r.area} ${r.office}|${r.candidate}`, r.detail]));
      for (const r of rows) if (!r.note && detail.has(r.race + '|' + r.candidate)) r.note = detail.get(r.race + '|' + r.candidate);
      const races = new Map();
      for (const r of rows) {
        let o = races.get(r.race);
        if (!o) { o = { area: r.area, year: r.year, office: r.office, status: r.status, total: 0, cand: new Map() }; races.set(r.race, o); }
        if (r.status === 'counting' || (r.status === 'pending' && o.status === 'final')) o.status = r.status;
        if (r.votes != null && r.party !== 'W') o.total += r.votes;
        if (r.party === 'W') continue;
        const c = o.cand.get(r.candidate) || { party: r.party, votes: r.votes == null ? null : 0, note: r.note };
        if (r.votes != null) c.votes = (c.votes || 0) + r.votes;
        o.cand.set(r.candidate, c);
      }
      const out = [];
      for (const [race, o] of races) {
        const prop = /^Proposition/.test(o.office);
        const list = [...o.cand.entries()].sort((a, b) => prop ? (a[0] === 'For' ? -1 : 1) : (b[1].votes || 0) - (a[1].votes || 0) || a[0].localeCompare(b[0]));
        const unopposed = !prop && list.length === 1;
        const lead = list.slice().sort((a, b) => (b[1].votes || 0) - (a[1].votes || 0))[0];
        list.forEach(([candidate, c], i) => out.push({ race, area: o.area, year: o.year, office: o.office, rank: i + 1, candidate, party: c.party, votes: c.votes,
          pct: o.total ? (c.votes || 0) / o.total : unopposed ? 1 : null, unopposed, status: o.status, note: c.note,
          leading: o.total > 0 && candidate === lead[0], winner: o.status === 'final' && (unopposed || (o.total > 0 && candidate === lead[0])) }));
      }
      return out;
    },
  });

  dash.calc('local_races', {
    title: 'Key local races',
    description: 'Each local race: total votes, Republican-minus-Democratic margin (or share voting For a proposition), and the shift from the previous race for the same office in the same area.',
    inputs: ['local_candidates'],
    fn: (local_candidates) => {
      const lab = (m) => (m == null || isNaN(m)) ? '—' : Math.abs(m) < 0.0005 ? 'Even' : (m > 0 ? 'R+' : 'D+') + (Math.abs(m) * 100).toFixed(1);
      const g = new Map();
      for (const c of local_candidates) {
        let o = g.get(c.race);
        if (!o) { o = { race: c.race, area: c.area, year: c.year, office: c.office, status: c.status, kind: /^Proposition/.test(c.office) ? 'proposition' : 'candidate', total_votes: 0, rep: 0, dem: 0, yes: 0, n: 0, has_votes: false }; g.set(c.race, o); }
        o.n++; o.total_votes += c.votes || 0; if (c.votes != null) o.has_votes = true;
        if (c.party === 'R') o.rep += c.votes || 0; if (c.party === 'D') o.dem += c.votes || 0;
        if (c.candidate === 'For') o.yes += c.votes || 0;
      }
      const rows = [...g.values()].map((o) => {
        const both = o.rep > 0 && o.dem > 0;
        const r = { race: o.race, area: o.area, year: o.year, office: o.office, status: o.status, kind: o.kind, total_votes: o.has_votes ? o.total_votes : null, unopposed: o.kind === 'candidate' && o.n === 1, both_parties: both,
          margin: o.kind === 'candidate' && o.total_votes && both ? (o.rep - o.dem) / o.total_votes : null,
          for_pct: o.kind === 'proposition' && o.total_votes ? o.yes / o.total_votes : null };
        r.margin_label = r.unopposed ? 'Unopposed' : lab(r.margin);
        r.result = r.kind !== 'proposition' || r.for_pct == null ? null : r.status === 'final' ? (r.for_pct > 0.5 ? 'Passed' : 'Failed') : (r.for_pct > 0.5 ? 'For leading' : 'Against leading');
        return r;
      });
      const byOff = new Map();
      for (const r of rows) { const k = r.area + '|' + r.office; if (!byOff.has(k)) byOff.set(k, []); byOff.get(k).push(r); }
      for (const list of byOff.values()) {
        list.sort((a, b) => a.year - b.year);
        let prev = null;
        for (const r of list) {
          const redrawn = r.area === 'tarrant' && r.year === 2026 && /^Commissioner/.test(r.office);
          r.prev_race = r.margin != null && prev && !redrawn ? prev.race : null;
          r.shift = r.prev_race && r.status === 'final' ? r.margin - prev.margin : null;
          r.shift_label = r.shift == null ? '—' : lab(r.shift);
          if (r.margin != null && r.status === 'final') prev = r;
        }
      }
      return rows.sort((a, b) => a.area.localeCompare(b.area) || a.office.localeCompare(b.office) || a.year - b.year);
    },
  });

  dash.calc('local_parts', {
    title: 'Key local races by county',
    description: '2026 election-night votes for each local race by the county reporting them (cities that cross county lines are reported by each county).',
    inputs: ['live_2026'],
    fn: (live_2026) => live_2026.filter((r) => r.level === 'local').map((r) => ({ race: r.race, area: r.plan, office: r.office, county: r.unit_name || r.unit, choice: r.candidate, party: r.party, votes: Number(r.votes) || 0,
      status: r.status, reporting: r.reporting === '' || r.reporting == null ? null : Number(r.reporting), reporting_total: r.reporting_total === '' || r.reporting_total == null ? null : Number(r.reporting_total) })),
  });

  // ---------- page ----------
  let ready = false;
  function setup() {
    if (ready) return;
    LX.mount('tab-fortbend');
    const area = LX.makeSelect('Area', (a) => dash.setParams({ lr_area: a }));
    area.wrap.id = 'lr-area-select';
    document.getElementById('lr-area').append(area.wrap);
    ready = true;
  }

  function draw() {
    if (LX.tab() !== 'fortbend') return;
    setup();
    const areaId = LX.localArea();
    LX.setOptions(document.querySelector('#lr-area-select select'), AREAS, areaId);
    const isFB = areaId === 'fortbend';
    document.getElementById('fb-view').hidden = !isFB;
    document.getElementById('lr-view').hidden = isFB;
    document.getElementById('fb-race-rows').hidden = !isFB;
    document.getElementById('lr-race-rows').hidden = isFB;
    if (isFB) return;

    const cd = dash.data('local_candidates'), rc = dash.data('local_races'), pt = dash.data('local_parts'), lv = dash.data('live_status');
    const deps = [cd, rc, pt];
    if (!deps.every((d) => d.status === 'ok')) {
      if (deps.some((d) => d.status === 'error' || d.status === 'missing')) ['lr-cands', 'lr-trend', 'lr-history'].forEach((id) => LX.failLine(document.getElementById(id)));
      return;
    }
    const races = rc.data.filter((r) => r.area === areaId);
    const offices = [...new Set(races.map((r) => r.office))].sort((a, b) => (a === 'County Judge' ? -1 : b === 'County Judge' ? 1 : a.localeCompare(b)));
    const want = dash.params().lr_race;
    const R = races.find((r) => r.race === want) || races.find((r) => r.year === 2026 && r.office === offices[0]) || races[races.length - 1];
    LX.racePicker(document.getElementById('lr-race-rows'), offices.map((o) => [o, OFFICE_NAME[o] || o]),
      races.map((r) => ({ race: r.race, year: r.year, group: r.office, yearLabel: r.year === 2026 ? '2026 (Nov. 3)' : String(r.year) })),
      R.race, (race) => dash.setParams({ lr_race: race }));
    const areaName = AREAS.find((a) => a[0] === areaId)[1];
    const C = cd.data.filter((c) => c.race === R.race).sort((a, b) => a.rank - b.rank);
    const prop = R.kind === 'proposition';
    const pending = R.status === 'pending' || !(R.total_votes > 0) && !R.unopposed;
    LX.liveBanner(document.getElementById('lr-live'), R.year, 'county election offices (unofficial)');
    document.querySelectorAll('#lr-view [data-source="local_races"][data-field]').forEach((el) => el.setAttribute('data-where', 'race=' + enc(R.race)));

    // takeaway
    const tk = document.getElementById('lr-take'); tk.classList.remove('dash-skeleton'); tk.replaceChildren();
    const add = (t, b, field) => { const n = document.createElement(b ? 'b' : 'span'); n.textContent = t; if (field) { n.setAttribute('data-source', 'local_races'); n.setAttribute('data-field', field); n.setAttribute('data-where', 'race=' + enc(R.race)); } tk.append(n); };
    const oname = prop ? `${areaName} ${R.office}` : R.office === 'County Judge' ? `${areaName} judge` : `${areaName} ${R.office.replace('Commissioner Pct ', 'Precinct ')} commissioner`;
    const desc = prop ? (C.find((c) => c.candidate === 'For') || {}).note : '';
    if (pending) {
      add(`The ${oname} ${prop ? 'vote' : 'race'} is on the ballot ${LX.ELECTION_2026}.`);
      if (prop && desc) add(' ' + desc);
      add(' Results will appear here as counties report on election night.');
    } else if (prop) {
      const f = R.for_pct;
      add(`${R.office} ${R.status === 'final' ? (f > 0.5 ? 'passed' : 'failed') : (f > 0.5 ? 'is passing' : 'is failing')} with `); add(pct(f), true, 'for_pct'); add(' of votes For.');
      if (desc) add(' ' + desc);
    } else if (R.unopposed) {
      add(C[0].candidate, true); add(` (${C[0].party}) ran unopposed for ${oname} in ${R.year}.`);
      if (C[0].votes == null) add(' The race was not on the ballot, so there is no vote count.');
    } else {
      add(C[0].candidate, true); add(R.status === 'final' ? ` won the ${R.year} ${oname} race by ` : ` leads the ${R.year} ${oname} race by `);
      add(Math.abs((C[0].pct - C[1].pct) * 100).toFixed(1) + ' points', true);
      if (R.margin != null) add(` (${R.margin_label}).`); else add('.');
      if (R.prev_race && R.shift != null) { add(' Compared with ' + R.prev_race.slice(0, 4) + ', the margin moved '); add(R.shift_label, true, 'shift_label'); add(R.shift > 0 ? ' toward Republicans.' : R.shift < 0 ? ' toward Democrats.' : '.'); }
    }

    // candidate / choice cards
    const box = document.getElementById('lr-cands'); box.classList.remove('dash-skeleton');
    box.replaceChildren(...C.map((c) => {
      const card = document.createElement('div'); card.className = 'lx-card lx-cand' + ((c.winner || (!pending && c.leading)) ? ' win' : '');
      const col = prop ? css(c.candidate === 'For' ? '--color-ok' : '--color-bad') : partyCol(c.party), where = 'race=' + enc(c.race) + '&candidate=' + enc(c.candidate);
      const ini = prop ? LX.avatar('', col, c.candidate === 'For' ? '✓' : '✕') : LX.avatar(c.candidate, col);
      const body = document.createElement('div'); body.className = 'lx-cand-body';
      const nm = document.createElement('div'); nm.className = 'lx-cand-name'; nm.textContent = c.candidate; nm.setAttribute('data-source', 'local_candidates'); nm.setAttribute('data-field', 'candidate'); nm.setAttribute('data-where', where);
      const pl = document.createElement('div'); pl.className = 'lx-cand-party';
      if (!prop) { const pn = document.createElement('span'); pn.style.color = col; pn.textContent = (PARTY[c.party] || c.party || 'No party') + (c.party ? ' (' + c.party + ')' : ''); pl.append(pn); }
      const word = c.unopposed ? 'Unopposed' : pending ? '' : c.winner ? (prop ? (c.candidate === 'For' ? 'Passed' : 'Failed') : 'Winner') : c.leading && c.status !== 'final' ? 'Leading' : '';
      if (word && (!prop || c.leading)) { const b = document.createElement('span'); b.className = 'lx-badge'; b.textContent = word; pl.append(b); }
      const pc = document.createElement('div'); pc.className = 'lx-cand-pct'; pc.textContent = c.pct == null || pending ? '—' : pct(c.pct); pc.setAttribute('data-source', 'local_candidates'); pc.setAttribute('data-field', 'pct'); pc.setAttribute('data-where', where);
      const vt = document.createElement('div'); vt.className = 'lx-cand-votes';
      if (c.votes == null) vt.textContent = 'No vote count';
      else { const vs = document.createElement('span'); vs.textContent = fmt(c.votes); vs.setAttribute('data-source', 'local_candidates'); vs.setAttribute('data-field', 'votes'); vs.setAttribute('data-where', where); vt.append(vs, document.createTextNode(' votes')); }
      const bar = document.createElement('div'); bar.className = 'lx-cand-bar'; const bi = document.createElement('i'); bi.style.width = ((pending ? 0 : c.pct || 0) * 100).toFixed(1) + '%'; bi.style.background = col; bar.append(bi);
      body.append(nm, pl, pc, vt, bar); card.append(ini, body); return card;
    }));
    LX.photoCredit(LX.creditAfter(box, 'lr-photo-credit'), prop ? [] : C.map((c) => c.candidate));

    // KPIs
    const parts = pt.data.filter((p) => p.race === R.race);
    const setK = (id, v) => { const el = document.getElementById(id); el.textContent = v; el.classList.remove('dash-skeleton'); };
    document.getElementById('lr-k1-label').textContent = prop ? 'Share voting For' : 'Margin (R − D)';
    document.getElementById('lr-k1').setAttribute('data-field', prop ? 'for_pct' : 'margin_label');
    setK('lr-k1', pending ? '—' : prop ? pct(R.for_pct) : R.margin_label);
    document.getElementById('lr-k1').style.color = pending || R.unopposed ? '' : prop ? css(R.for_pct > 0.5 ? '--color-ok' : '--color-bad') : R.margin == null ? '' : R.margin > 0 ? css('--lx-rep') : css('--lx-dem');
    document.getElementById('lr-k1-sub').textContent = prop ? (pending ? 'Needs a majority to pass' : R.result || '') : R.prev_race && R.shift != null ? `Shift: ${R.shift_label} vs ${R.prev_race.slice(0, 4)}` : R.area === 'tarrant' && R.year === 2026 && /^Commissioner/.test(R.office) ? 'Precinct redrawn in 2025' : '';
    setK('lr-k2', R.total_votes == null || pending ? '—' : fmt(R.total_votes));
    const rep = parts.filter((p) => p.reporting != null && p.reporting_total);
    const repTxt = (p) => p.reporting_total === 100 && p.reporting <= 100 ? `${p.reporting}% reporting` : `${fmt(p.reporting)} of ${fmt(p.reporting_total)} precincts`;
    const byCounty = [...d3.group(parts, (p) => p.county)].map(([county, list]) => ({ county, list }));
    setK('lr-k3', R.year !== 2026 ? 'Final' : pending ? 'Not yet' : R.status === 'final' ? 'Complete' : 'Counting');
    document.getElementById('lr-k3-sub').textContent = R.year !== 2026 ? (R.unopposed && C[0].votes == null ? 'Not on the ballot' : 'Certified result') : byCounty.length ? byCounty.map(({ county, list }) => { const p = rep.find((x) => x.county === county); return county + (p ? ': ' + repTxt(p) : list.some((x) => x.votes) ? ': reporting' : ': none yet'); }).join(' · ') : 'Waiting for county results';

    drawSide(R, races, C, byCounty, prop, pending);
    drawHistory(races, R);
    document.getElementById('lr-foot').textContent = (NOTES[areaId] ? NOTES[areaId] + ' ' : '') + 'Past results: county election offices’ official reports (Harris County Clerk, Tarrant, Collin and Denton County Elections) and OpenElections copies of the county canvass. 2026 results come from each county’s election-night reports (Clarity, Harris County Clerk, Collin County) and are unofficial until canvassed.';
  }

  function drawSide(R, races, C, byCounty, prop, pending) {
    const title = document.getElementById('lr-side-title'), note = document.getElementById('lr-side-note'), el = document.getElementById('lr-trend');
    el.classList.remove('dash-skeleton'); el.replaceChildren();
    const lg = document.getElementById('lr-trend-legend'); lg.replaceChildren();
    if (prop || R.year === 2026 && byCounty.length > 1) {
      title.textContent = 'Results by county'; note.textContent = prop ? 'Each county reports its part of the city.' : 'Votes reported by each county.';
      const t = document.createElement('table'); t.className = 'lx-table';
      const head = document.createElement('tr');
      ['County', ...C.map((c) => c.candidate), prop ? 'For %' : 'Margin'].forEach((h, i) => { const th = document.createElement('th'); th.textContent = h; th.style.padding = '0.45rem 0.5rem'; if (i === 0) th.style.textAlign = 'left'; head.append(th); });
      const tb = document.createElement('tbody');
      for (const { county, list } of byCounty) {
        const tr = document.createElement('tr'); tr.style.cursor = 'default';
        const td = (txt, cls) => { const x = document.createElement('td'); x.textContent = txt; if (cls) x.className = cls; tr.append(x); };
        td(county); let tot = 0, yes = 0, r = 0, d = 0;
        for (const c of C) { const v = list.filter((p) => p.choice === c.candidate).reduce((s, p) => s + p.votes, 0); td(fmt(v)); tot += v; if (c.candidate === 'For') yes += v; if (c.party === 'R') r += v; if (c.party === 'D') d += v; }
        td(!tot ? '—' : prop ? pct(yes / tot) : lab((r - d) / tot));
        tb.append(tr);
      }
      if (!byCounty.length) { const tr = document.createElement('tr'); const x = document.createElement('td'); x.colSpan = C.length + 2; x.textContent = 'No county has posted results yet.'; x.style.textAlign = 'left'; tr.append(x); tb.append(tr); }
      const th = document.createElement('thead'); th.append(head); t.append(th, tb); el.append(t);
      return;
    }
    title.textContent = 'Margin over time'; note.textContent = 'Republican minus Democratic share in each contested race. Click a point to open that race.';
    const offices = [...new Set(races.filter((r) => r.kind === 'candidate').map((r) => r.office))];
    const W = Math.max(280, el.clientWidth), H = 240;
    const ser = offices.map((o, i) => ({ o, col: dash.colors[i % dash.colors.length], focus: o === R.office, pts: races.filter((r) => r.office === o && r.margin != null && r.status === 'final').sort((a, b) => a.year - b.year) })).filter((s) => s.pts.length);
    if (!ser.length || !ser.some((s) => s.focus)) {
      const m = document.createElement('div'); m.className = 'lx-empty-map'; m.style.minHeight = '12rem'; m.textContent = R.year === 2026 && pending ? 'Earlier results for this office appear once a contested race is on record.' : 'No contested race between a Republican and a Democrat to chart for this office.'; el.append(m);
      if (!ser.length) return;
    }
    const all = ser.flatMap((s) => s.pts.map((p) => p.margin));
    let lo = Math.min(0, d3.min(all)), hi = Math.max(0, d3.max(all)); const pad = (hi - lo) * 0.1 || 0.05; lo -= pad; hi += pad;
    const y = d3.scaleLinear([lo, hi], [H - 26, 10]).nice(5);
    const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', '100%').attr('role', 'img').attr('aria-label', 'Margin over time');
    const ticks = y.ticks(5);
    const tl = svg.append('g').selectAll('text').data(ticks).join('text').attr('x', 0).attr('y', (d) => y(d)).attr('dy', '0.32em').attr('fill', 'var(--color-fg-muted)').attr('font-size', 'var(--cds-font-size-caption)').text((d) => lab(d));
    let ml = 0; tl.each(function () { ml = Math.max(ml, this.getComputedTextLength()); });
    const left = ml + 8, x = d3.scaleLinear([2010, 2026], [left, W - 12]);
    svg.append('g').selectAll('line').data(ticks).join('line').attr('x1', left).attr('x2', W - 12).attr('y1', (d) => y(d)).attr('y2', (d) => y(d)).attr('stroke', (d) => d === 0 ? 'var(--cds-chart-reference)' : 'var(--cds-chart-grid)');
    svg.append('g').selectAll('text').data([2010, 2014, 2018, 2022, 2026]).join('text').attr('x', (d) => x(d)).attr('y', H - 6).attr('text-anchor', (d) => d === 2026 ? 'end' : d === 2010 ? 'start' : 'middle').attr('fill', 'var(--color-fg-muted)').attr('font-size', 'var(--cds-font-size-caption)').text((d) => d);
    const line = d3.line().x((d) => x(d.year)).y((d) => y(d.margin));
    for (const s of ser.slice().sort((a, b) => a.focus - b.focus)) {
      svg.append('path').datum(s.pts).attr('d', line).attr('fill', 'none').attr('stroke', s.focus ? s.col : 'var(--cds-chart-muted)').attr('stroke-width', s.focus ? 2.2 : 1.2).attr('stroke-linecap', 'round').attr('stroke-linejoin', 'round');
      svg.append('g').selectAll('circle').data(s.pts).join('circle').attr('cx', (d) => x(d.year)).attr('cy', (d) => y(d.margin)).attr('r', (d) => d.race === R.race ? 5 : s.focus ? 3.5 : 2)
        .attr('fill', (d) => d.race === R.race ? 'var(--color-panel)' : s.focus ? s.col : 'var(--cds-chart-muted)').attr('stroke', s.focus ? s.col : 'none').attr('stroke-width', (d) => d.race === R.race ? 2.5 : 0)
        .style('cursor', 'pointer').on('click', (e, d) => dash.setParams({ lr_race: d.race }))
        .append('title').text((d) => `${d.year} ${OFFICE_NAME[d.office]}: ${d.margin_label}`);
    }
    const f = ser.find((s) => s.focus);
    if (f) { const g = document.createElement('span'); g.className = 'grp'; const s = document.createElement('i'); s.className = 'sw'; s.style.background = f.col; s.style.height = '3px'; s.style.verticalAlign = '3px'; g.append(s, document.createTextNode(OFFICE_NAME[R.office])); lg.append(g); }
    if (ser.length > 1) { const g2 = document.createElement('span'); g2.className = 'grp'; const s2 = document.createElement('i'); s2.className = 'sw'; s2.style.background = 'var(--cds-chart-muted)'; s2.style.height = '3px'; s2.style.verticalAlign = '3px'; g2.append(s2, document.createTextNode('Other races in this county')); lg.append(g2); }
  }

  function drawHistory(races, R) {
    const list = races.filter((r) => r.office === R.office).sort((a, b) => b.year - a.year);
    const cd = dash.data('local_candidates').data;
    document.getElementById('lr-hist-title').textContent = `Every ${OFFICE_NAME[R.office]} race`;
    const tb = document.querySelector('#lr-history tbody'); tb.replaceChildren();
    for (const r of list) {
      const C = cd.filter((c) => c.race === r.race).sort((a, b) => (b.votes || 0) - (a.votes || 0));
      const tr = document.createElement('tr'); tr.dataset.key = enc(r.race); if (r.race === R.race) tr.className = 'sel';
      tr.addEventListener('click', () => dash.setParams({ lr_race: r.race }));
      const td = (t, cls) => { const x = document.createElement('td'); x.textContent = t; if (cls) x.className = cls; tr.append(x); return x; };
      td(r.year === 2026 ? '2026' + (r.status === 'final' ? '' : r.status === 'counting' ? ' (counting)' : ' (upcoming)') : String(r.year));
      const pend = r.status === 'pending';
      const w = C[0], s = C[1];
      const nm = (c) => !c ? '—' : r.kind === 'proposition' ? c.candidate : `${c.candidate}${c.party ? ' (' + c.party + ')' : ''}`;
      const a = td(pend ? (r.kind === 'proposition' ? 'On the ballot' : C.map(nm).join(' vs ')) : nm(w), 'lx-cand-cell'); if (!pend && w && r.kind !== 'proposition') a.style.color = partyCol(w.party);
      td(pend ? '' : r.unopposed ? 'Unopposed' : nm(s), 'lx-cand-cell lx-hide-narrow');
      const m = td(pend ? '—' : r.kind === 'proposition' ? pct(r.for_pct) + ' For' : r.margin_label, r.margin > 0 ? 'lx-r' : r.margin < 0 ? 'lx-d' : '');
      if (r.kind === 'candidate' && r.margin == null && !r.unopposed && !pend && w && s) m.textContent = 'Won by ' + ((w.pct - s.pct) * 100).toFixed(1);
      td(r.total_votes == null || pend ? '—' : fmt(r.total_votes), 'lx-hide-narrow');
      tb.append(tr);
    }
  }

  dash.onData(draw);
})();
