(() => {
  const LX = window.LX;
  const { css, fmt, pct, enc, PARTY, partyCol } = LX;

  // ---------- calculations (each function is self-contained) ----------
  const byDistrictFn = (results, live_2026) => {
    const lab = (m) => (m == null || isNaN(m)) ? '—' : Math.abs(m) < 0.0005 ? 'Even' : (m > 0 ? 'R+' : 'D+') + (Math.abs(m) * 100).toFixed(1);
    const LEVEL = { 'House': 'house', 'Senate': 'senate', 'U.S. House': 'ushouse', 'SBOE': 'sboe' };
    const level = results.length ? LEVEL[String(results[0].race).slice(5)] : null;
    const all = results.map((r) => ({ ...r, status: 'final' })).concat(live_2026.filter((r) => r.level === level).map((r) => ({
      year: r.year, race: r.race, plan: r.plan, district: r.unit, candidate: r.candidate, party: r.party, votes: r.votes, status: r.status, reporting: r.reporting, reporting_total: r.reporting_total })));
    const g = new Map();
    for (const r of all) {
      const k = r.year + '|' + r.district;
      let o = g.get(k);
      if (!o) { o = { race: r.race, year: Number(r.year), plan: r.plan, district: Number(r.district), cands: [], writein: 0, unknown: false, status: r.status,
        reporting: r.reporting === '' || r.reporting == null ? null : Number(r.reporting), reporting_total: r.reporting_total === '' || r.reporting_total == null ? null : Number(r.reporting_total) }; g.set(k, o); }
      const v = (r.votes === '' || r.votes == null) ? null : Number(r.votes);
      if (r.party === 'W') { o.writein += v || 0; continue; }
      if (v == null) o.unknown = true;
      o.cands.push({ name: r.candidate, party: r.party, votes: v });
    }
    const rows = [];
    for (const o of g.values()) {
      o.cands.sort((a, b) => (b.votes ?? Infinity) - (a.votes ?? Infinity) || a.name.localeCompare(b.name));
      const sum = o.unknown ? null : o.cands.reduce((s, c) => s + c.votes, 0) + o.writein;
      const total = sum === 0 ? null : sum;
      const single = o.cands.length === 1;
      const rep = o.cands.find((c) => c.party === 'R'), dem = o.cands.find((c) => c.party === 'D');
      const margin = total ? ((rep ? rep.votes : 0) - (dem ? dem.votes : 0)) / total : single ? (o.cands[0].party === 'R' ? 1 : o.cands[0].party === 'D' ? -1 : 0) : null;
      const decided = single || total != null;
      const row = { race: o.race, year: o.year, plan: o.plan, district: o.district, status: o.status, contested: !single, votes_reported: total != null, decided,
        reporting: o.reporting, reporting_total: o.reporting_total,
        total_votes: total, winner_name: decided ? o.cands[0].name : null, winner_party: decided ? o.cands[0].party : null, margin, margin_label: single ? 'Unopposed' : lab(margin), n_cands: o.cands.length };
      o.cands.slice(0, 4).forEach((c, i) => {
        row['c' + (i + 1) + '_name'] = c.name; row['c' + (i + 1) + '_party'] = c.party; row['c' + (i + 1) + '_votes'] = c.votes;
        row['c' + (i + 1) + '_pct'] = total ? c.votes / total : (single ? 1 : null);
        row['c' + (i + 1) + '_label'] = c.name + ' (' + c.party + ')';
      });
      rows.push(row);
    }
    return rows.sort((a, b) => a.year - b.year || a.district - b.district);
  };

  const summaryFn = (by_district) => {
    const lab = (m) => Math.abs(m) < 0.0005 ? 'Even' : (m > 0 ? 'R+' : 'D+') + (Math.abs(m) * 100).toFixed(1);
    const g = new Map();
    for (const r of by_district) {
      let o = g.get(r.year);
      if (!o) { o = { race: r.race, year: r.year, plan: r.plan, status: r.status, seats_total: 0, seats_r: 0, seats_d: 0, seats_other: 0, undecided: 0, uncontested: 0, uncontested_r: 0, uncontested_d: 0, no_votes_reported: 0, total_votes: 0, closest: null }; g.set(r.year, o); }
      o.seats_total++;
      if (!r.decided) o.undecided++;
      else if (r.winner_party === 'R') o.seats_r++; else if (r.winner_party === 'D') o.seats_d++; else o.seats_other++;
      if (!r.contested) { o.uncontested++; if (r.winner_party === 'R') o.uncontested_r++; if (r.winner_party === 'D') o.uncontested_d++; }
      if (!r.votes_reported) o.no_votes_reported++; else o.total_votes += r.total_votes;
      const both = [r.c1_party, r.c2_party].includes('R') && [r.c1_party, r.c2_party].includes('D');
      if (r.contested && r.votes_reported && both && (!o.closest || Math.abs(r.margin) < Math.abs(o.closest.margin))) o.closest = r;
    }
    return [...g.values()].map((o) => ({ race: o.race, year: o.year, plan: o.plan, status: o.status, seats_total: o.seats_total, seats_r: o.seats_r, seats_d: o.seats_d, seats_other: o.seats_other, undecided: o.undecided,
      uncontested: o.uncontested, uncontested_r: o.uncontested_r, uncontested_d: o.uncontested_d, no_votes_reported: o.no_votes_reported, total_votes: o.total_votes,
      closest_district: o.closest ? o.closest.district : null, closest_label: o.closest ? 'District ' + o.closest.district + ', ' + lab(o.closest.margin) : '—' })).sort((a, b) => a.year - b.year);
  };

  const partiesFn = (by_district) => {
    const g = new Map();
    for (const r of by_district) {
      let y = g.get(r.year);
      if (!y) { y = { race: r.race, total: 0, p: new Map() }; g.set(r.year, y); }
      if (r.decided) { const e = y.p.get(r.winner_party) || { votes: 0, seats: 0 }; e.seats++; y.p.set(r.winner_party, e); }
      if (!r.votes_reported) continue;
      y.total += r.total_votes;
      for (let i = 1; i <= 4; i++) {
        const p = r['c' + i + '_party']; if (!p) continue;
        const e = y.p.get(p) || { votes: 0, seats: 0 }; e.votes += r['c' + i + '_votes']; y.p.set(p, e);
      }
    }
    const rows = [];
    for (const [year, y] of g) {
      [...y.p.entries()].sort((a, b) => b[1].seats - a[1].seats || b[1].votes - a[1].votes).slice(0, 4)
        .forEach(([party, e], i) => rows.push({ race: y.race, year, party, rank: i + 1, seats: e.seats, votes: e.votes, vote_pct: y.total ? e.votes / y.total : null }));
    }
    return rows;
  };

  // whole-chamber makeup after each election: seats won that year plus holdovers carried from the last election in each district (same map)
  const chamberFn = (by_district) => {
    const years = [...new Set(by_district.map((r) => r.year))].sort((a, b) => a - b);
    const out = []; let comp = new Map(), plan = null, prev = null;
    for (const y of years) {
      const rows = by_district.filter((r) => r.year === y);
      if (rows[0].plan !== plan) { comp = new Map(); plan = rows[0].plan; }
      const up = new Set();
      for (const r of rows) { up.add(r.district); comp.set(r.district, r.decided ? r.winner_party : '?'); }
      const c = { R: 0, D: 0, O: 0, U: 0 }, cu = { R: 0, D: 0, O: 0, U: 0 };
      for (const [d, p] of comp) { const k = p === 'R' || p === 'D' ? p : p === '?' ? 'U' : 'O'; c[k]++; if (up.has(d)) cu[k]++; }
      const total = comp.size;
      const row = { race: rows[0].race, year: y, plan, status: rows[0].status, seats_total: total, seats_up: rows.length,
        r_seats: c.R, d_seats: c.D, other_seats: c.O, undecided_seats: c.U, r_up: cu.R, d_up: cu.D, other_up: cu.O, undecided_up: cu.U,
        r_change: prev ? c.R - prev.r_seats : null, d_change: prev ? c.D - prev.d_seats : null, prev_year: prev ? prev.year : null,
        majority: c.R > total / 2 ? 'R' : c.D > total / 2 ? 'D' : null };
      out.push(row); prev = row;
    }
    return out;
  };

  const CH = {
    house: { p: 'h', host: 'tab-house', label: 'Texas House', body: 'House', full: 150, results: 'house_results', shapes: 'house_shapes', id: 'house', level: 'house' },
    senate: { p: 's', host: 'tab-senate', label: 'Texas Senate', body: 'Senate', full: 31, results: 'senate_results', shapes: 'senate_shapes', id: 'senate', level: 'senate' },
    ushouse: { p: 'u', host: 'view-ushouse', label: 'U.S. House', body: 'Texas U.S. House delegation', full: null, results: 'ushouse_results', shapes: 'ushouse_shapes', id: 'ushouse', level: 'ushouse' },
    sboe: { p: 'b', host: 'view-sboe', label: 'State Board of Education', body: 'State Board of Education', full: 15, results: 'sboe_results', shapes: 'sboe_shapes', id: 'sboe', level: 'sboe' },
  };
  dash.calc('house_by_district', { title: 'Texas House results per district', description: 'Each Texas House race: top four candidates with vote shares, winner or leader, and Republican-minus-Democratic margin (±100 for an unopposed race); 2026 comes from the election-night file.', inputs: ['house_results', 'live_2026'], fn: byDistrictFn });
  dash.calc('house_summary', { title: 'Texas House seats per election', description: 'Seats won (or led) by party, uncontested races, closest race and total votes reported, for each Texas House election.', inputs: ['house_by_district'], fn: summaryFn });
  dash.calc('house_chamber', { title: 'Texas House makeup after each election', description: 'All 150 seats after each general election, by party of the winner.', inputs: ['house_by_district'], fn: chamberFn });
  dash.calc('house_parties', { title: 'Texas House results by party', description: 'Seats won and share of all reported votes for the top four parties in each Texas House election.', inputs: ['house_by_district'], fn: partiesFn });
  dash.calc('senate_by_district', { title: 'Texas Senate results per district', description: 'Each Texas Senate race: top four candidates with vote shares, winner or leader, and Republican-minus-Democratic margin (±100 for an unopposed race); 2026 comes from the election-night file.', inputs: ['senate_results', 'live_2026'], fn: byDistrictFn });
  dash.calc('senate_summary', { title: 'Texas Senate seats per election', description: 'Seats won (or led) by party, uncontested races, closest race and total votes reported, for each Texas Senate election.', inputs: ['senate_by_district'], fn: summaryFn });
  dash.calc('senate_chamber', { title: 'Texas Senate makeup after each election', description: 'All 31 seats after each general election: seats won that year plus senators not up, carried from the last general election in their district under the same map. Special elections and party switches between general elections are not included.', inputs: ['senate_by_district'], fn: chamberFn });
  dash.calc('senate_parties', { title: 'Texas Senate results by party', description: 'Seats won and share of all reported votes for the top four parties in each Texas Senate election.', inputs: ['senate_by_district'], fn: partiesFn });
  dash.calc('ushouse_by_district', { title: 'U.S. House results per district', description: 'Each U.S. House race: top four candidates with vote shares, winner or leader, and Republican-minus-Democratic margin (±100 for an unopposed race); 2026 comes from the election-night file.', inputs: ['ushouse_results', 'live_2026'], fn: byDistrictFn });
  dash.calc('ushouse_summary', { title: 'U.S. House seats per election', description: 'Seats won (or led) by party, uncontested races, closest race and total votes reported, for each U.S. House election.', inputs: ['ushouse_by_district'], fn: summaryFn });
  dash.calc('ushouse_parties', { title: 'U.S. House results by party', description: 'Seats won and share of all reported votes for the top four parties in each U.S. House election.', inputs: ['ushouse_by_district'], fn: partiesFn });
  dash.calc('sboe_by_district', { title: 'State Board of Education results per district', description: 'Each State Board of Education race: top four candidates with vote shares, winner or leader, and Republican-minus-Democratic margin (±100 for an unopposed race); 2026 comes from the election-night file.', inputs: ['sboe_results', 'live_2026'], fn: byDistrictFn });
  dash.calc('sboe_summary', { title: 'State Board of Education seats per election', description: 'Seats won (or led) by party, uncontested races, closest race and total votes reported, for each State Board of Education election.', inputs: ['sboe_by_district'], fn: summaryFn });
  dash.calc('sboe_parties', { title: 'State Board of Education results by party', description: 'Seats won and share of all reported votes for the top four parties in each State Board of Education election.', inputs: ['sboe_by_district'], fn: partiesFn });

  const METROS = [['Statewide', null], ['Houston', [545.7, 385.8, 60.7, 54.4]], ['Dallas–Fort Worth', [470.6, 190.2, 64.5, 53.1]], ['Austin', [438.5, 341.6, 52.4, 52.9]],
    ['San Antonio', [406.0, 410.4, 34.9, 38.7]], ['El Paso', [3.7, 275.9, 32.4, 36.9]], ['Rio Grande Valley', [417.3, 589.0, 74.1, 55.6]]];
  const fillFor = (r) => {
    const side = r.winner_party === 'R' || r.winner_party === 'D' ? (r.margin >= 0 ? 'R' : 'D') : 'I';
    const lead = side === 'I' ? (r.c1_pct ?? 1) - (r.c2_pct ?? 0) : Math.abs(r.margin);
    return LX.rampColor(side, lead);
  };
  const state = {};
  for (const k of Object.keys(CH)) state[k] = { sortKey: 'district', sortDir: 1, q: '', zoom: null };

  function setup(key) {
    const c = CH[key], P = c.p, st = state[key];
    if (!LX.mount(c.host)) return;
    const q = (id) => document.getElementById(P + '-' + id);
    q('clear').addEventListener('click', () => dash.setParams({ [P + '_district']: null }));
    q('search').addEventListener('input', (e) => { st.q = e.target.value.trim().toLowerCase(); draw(); });
    q('table').querySelectorAll('th button').forEach((b) => b.addEventListener('click', () => {
      const k = b.dataset.sort; if (st.sortKey === k) st.sortDir = -st.sortDir; else { st.sortKey = k; st.sortDir = k === 'district' || k.endsWith('_label') ? 1 : -1; } draw();
    }));
    q('table').querySelector('tbody').addEventListener('click', (e) => {
      const tr = e.target.closest('tr[data-district]');
      if (tr) { dash.setParams({ [P + '_district']: Number(tr.dataset.district) }); q('detail-card').scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
    });
    const zoomSel = LX.makeSelect('Zoom to', (name) => { st.zoom = (METROS.find((m) => m[0] === name) || [])[1] || null; draw(); });
    q('zoom').replaceChildren(zoomSel.wrap); st.zoomSel = zoomSel.sel;
    const yearSel = LX.makeSelect('', (y) => dash.setParams({ [P + '_year']: Number(y) }), 'Election year');
    q('years').replaceChildren(yearSel.wrap); st.yearSel = yearSel.sel;
  }

  function draw() {
    const tab = LX.tab(), view = LX.swView();
    const key = tab === 'house' || tab === 'senate' ? tab : tab === 'statewide' && view !== 'offices' ? view : null;
    if (!key) return;
    setup(key);
    drawBody(key);
  }

  function drawBody(key) {
    const c = CH[key], P = c.p, st = state[key];
    const q = (id) => document.getElementById(P + '-' + id);
    const bd = dash.data(c.id + '_by_district'), sm = dash.data(c.id + '_summary'), pa = dash.data(c.id + '_parties'), shp = dash.data(c.shapes), lv = dash.data('live_2026');
    const all = [dash.data(c.results), lv, bd, sm, pa, shp];
    const years = sm.status === 'ok' ? [...new Set(sm.data.map((r) => r.year).concat([2026]))].sort((a, b) => a - b) : [];
    const pr = dash.params();
    const year = years.includes(Number(pr[P + '_year'])) ? Number(pr[P + '_year']) : 2024;
    if (years.length) LX.setOptions(st.yearSel, years.slice().reverse().map((y) => [y, y === 2026 ? '2026 (Nov. 3)' : String(y)]), year);
    LX.setOptions(st.zoomSel, METROS.map(([n]) => [n, n]), (METROS.find((m) => m[1] === st.zoom) || METROS[0])[0]);
    document.querySelectorAll(`#${c.host} [data-source="${c.id}_summary"][data-field]`).forEach((el) => el.setAttribute('data-where', 'year=' + year));
    if (!all.every((d) => d.status === 'ok')) {
      if (all.some((d) => d.status === 'error' || d.status === 'missing')) ['parties', 'map', 'seats', 'detail'].forEach((id) => LX.failLine(q(id)));
      return;
    }
    LX.liveBanner(q('live'), year);
    const S = sm.data.find((r) => r.year === year) || null;
    const rows = bd.data.filter((r) => r.year === year);
    const byD = new Map(rows.map((r) => [r.district, r]));
    const plan = S ? S.plan : year === 2026 ? LX.SCHEDULE_2026.plans[c.level] : '';
    const shapes = shp.data.filter((s) => s.plan === plan);
    const pending = !S || S.status === 'pending';
    const counting = S && S.status === 'counting';
    let sel = Number(pr[P + '_district']) || null;
    if (sel == null && S) sel = S.closest_district;
    const fullSize = c.full || (shapes.length || (S ? S.seats_total : 0));

    // takeaway
    const tk = q('take'); tk.classList.remove('dash-skeleton'); tk.replaceChildren();
    const add = (t, b, field) => { const n = document.createElement(b ? 'b' : 'span'); n.textContent = t; if (field) { n.setAttribute('data-source', c.id + '_summary'); n.setAttribute('data-field', field); n.setAttribute('data-where', 'year=' + year); } tk.append(n); };
    if (pending) add(S ? `${S.seats_total} ${year} ${c.label} races are listed so far, ${S.uncontested} with a single candidate. Results fill in on election night, ${LX.ELECTION_2026}.` : `${year} ${c.label} races are on the ballot ${LX.ELECTION_2026}. Candidates and results will appear here as results come in on election night.`);
    else {
      const lead = S.seats_r >= S.seats_d ? ['Republicans', S.seats_r, 'seats_r'] : ['Democrats', S.seats_d, 'seats_d'];
      add(`In ${year}, `); add(lead[0], true); add(counting ? ' have won or lead in ' : ' won '); add(String(lead[1]), true, lead[2]);
      add(` of the ${S.seats_total} ${c.label} seats on the ballot`);
      add(c.full && S.seats_total < c.full ? ` (the other ${c.full - S.seats_total} weren't up that year). ` : '. ');
      if (counting && S.undecided) { add(String(S.undecided), true, 'undecided'); add(' races have no votes counted yet. '); }
      add(String(S.uncontested), true, 'uncontested'); add(S.uncontested === 1 ? ' race had only one candidate on the ballot.' : ' races had only one candidate on the ballot.');
    }

    // party cards
    const parties = pa.data.filter((r) => r.year === year).sort((a, b) => a.rank - b.rank);
    const pc = q('parties'); pc.classList.remove('dash-skeleton');
    if (pending) { const m = document.createElement('div'); m.className = 'lx-card lx-empty'; m.textContent = 'Seat counts by party will appear here once results come in.'; pc.replaceChildren(m); }
    else pc.replaceChildren(...parties.map((p) => {
      const card = document.createElement('div'); card.className = 'lx-card lx-cand' + (p.rank === 1 ? ' win' : '');
      const col = partyCol(p.party), where = 'year=' + year + '&party=' + enc(p.party);
      const ini = document.createElement('div'); ini.className = 'lx-initials'; ini.style.background = col; ini.textContent = p.party; ini.setAttribute('aria-hidden', 'true');
      const body = document.createElement('div'); body.className = 'lx-cand-body';
      const nm = document.createElement('div'); nm.className = 'lx-cand-name'; nm.textContent = (PARTY[p.party] || p.party) + 's';
      const sub = document.createElement('div'); sub.className = 'lx-cand-party';
      const sp = document.createElement('span'); sp.style.color = col; sp.textContent = (PARTY[p.party] || p.party) + ' (' + p.party + ')'; sub.append(sp);
      if (p.rank === 1 && p.seats > S.seats_total / 2) { const b = document.createElement('span'); b.className = 'lx-badge'; b.textContent = counting ? 'Leading' : 'Most seats'; sub.append(b); }
      const big = document.createElement('div'); big.className = 'lx-cand-pct';
      const seats = document.createElement('span'); seats.textContent = String(p.seats); seats.setAttribute('data-source', c.id + '_parties'); seats.setAttribute('data-field', 'seats'); seats.setAttribute('data-where', where);
      const unit = document.createElement('span'); unit.style.fontSize = 'var(--cds-font-size-body)'; unit.style.color = 'var(--color-fg-muted)'; unit.textContent = p.seats === 1 ? ' seat' : ' seats';
      big.append(seats, unit);
      const vt = document.createElement('div'); vt.className = 'lx-cand-votes';
      const vp = document.createElement('span'); vp.textContent = p.vote_pct == null ? '—' : pct(p.vote_pct); vp.setAttribute('data-source', c.id + '_parties'); vp.setAttribute('data-field', 'vote_pct'); vp.setAttribute('data-where', where);
      vt.append(vp, document.createTextNode(' of votes · ' + fmt(p.votes)));
      const bar = document.createElement('div'); bar.className = 'lx-cand-bar'; const bi = document.createElement('i'); bi.style.width = (p.seats / S.seats_total * 100).toFixed(1) + '%'; bi.style.background = col; bar.append(bi);
      body.append(nm, sub, big, vt, bar); card.append(ini, body); return card;
    }));
    q('parties-note').textContent = pending ? '' : 'Bars show share of seats on the ballot. Vote shares count only races with reported totals' +
      (S.no_votes_reported ? ` (${S.no_votes_reported} race${S.no_votes_reported > 1 ? 's have' : ' has'} no vote total${counting ? ' yet' : ' in the official data'}).` : '.');

    // KPIs
    const setK = (id, v) => { const el = q(id); el.textContent = v; el.classList.remove('dash-skeleton'); };
    setK('k-seats', S ? String(S.seats_total) : '—');
    q('k-seats-sub').textContent = !S ? '' : c.full && S.seats_total < c.full ? `of ${c.full} seats; the rest were not up` : `all ${S.seats_total} seats`;
    setK('k-unc', S ? String(S.uncontested) : '—'); q('k-unc-sub').textContent = S ? `${S.uncontested_r} Republican · ${S.uncontested_d} Democratic` : '';
    setK('k-close', S ? S.closest_label : '—');
    setK('k-votes', S ? fmt(S.total_votes) : '—');

    if (c.id === 'house' || c.id === 'senate') drawChamber(c, year);
    drawMap(c, st, shapes, byD, year, sel, plan);
    drawDetail(c, byD.get(sel), year, sel, pending);
    drawSeats(c, sm.data, year, fullSize);
    drawTable(c, st, rows, sel, pending);
  }

  const CHAMBER_NOTES = { senate: { 2018: 'Republican Pete Flores won District 19 in a September 2018 special election, so the Senate seated in January 2019 was 19–12. This count uses general-election results only.' } };
  function drawChamber(c, year) {
    const P = c.p, el = document.getElementById(P + '-chamber'), txt = document.getElementById(P + '-chamber-text');
    const ch = dash.data(c.id + '_chamber');
    if (ch.status !== 'ok') { if (ch.status === 'error' || ch.status === 'missing') LX.failLine(el); return; }
    el.classList.remove('dash-skeleton');
    let row = ch.data.find((r) => r.year === year), before = false;
    if (!row || row.status === 'pending') { row = ch.data.filter((r) => r.year < year).pop(); before = true; }
    if (!row) { el.replaceChildren(); return; }
    const N = row.seats_total, maj = Math.floor(N / 2) + 1;
    // seat order, left to right: Democrats (won this year, then holdovers), others, undecided, Republicans (holdovers, then won this year)
    const showUp = !before && row.seats_up < N;
    const seq = [];
    const push = (n, party, kind) => { for (let i = 0; i < n; i++) seq.push({ party, kind }); };
    push(row.d_up, 'D', showUp ? 'up' : 'all'); push(row.d_seats - row.d_up, 'D', 'hold');
    push(row.other_seats, 'O', 'all'); push(row.undecided_seats, 'U', 'all');
    push(row.r_seats - row.r_up, 'R', 'hold'); push(row.r_up, 'R', showUp ? 'up' : 'all');
    if (before) seq.forEach((s) => { s.kind = 'all'; });
    // hemicycle geometry
    const W = 360, H = 196, cx = W / 2, cy = H - 8, R0 = N > 60 ? 70 : 92, R1 = 170;
    const rows = N > 100 ? 8 : N > 40 ? 6 : 4;
    const radii = d3.range(rows).map((i) => R0 + (R1 - R0) * (rows === 1 ? 0 : i / (rows - 1)));
    const sumR = d3.sum(radii);
    let counts = radii.map((r) => Math.round(N * r / sumR));
    counts[rows - 1] += N - d3.sum(counts);
    const pts = [];
    radii.forEach((r, i) => { const n = counts[i]; for (let j = 0; j < n; j++) { const a = Math.PI - (n === 1 ? Math.PI / 2 : Math.PI * j / (n - 1)); pts.push({ a, r, x: cx + r * Math.cos(a), y: cy - r * Math.sin(a) }); } });
    pts.sort((p, q) => q.a - p.a || p.r - q.r);
    const dotR = Math.min(((R1 - R0) / (rows - 1 || 1)) * 0.42, (Math.PI * R0 / (counts[0] || 1)) * 0.42);
    const col = { R: css('--lx-rep'), D: css('--lx-dem'), O: css('--lx-ind'), U: css('--cds-chart-muted') };
    el.replaceChildren();
    const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', '100%').attr('role', 'img')
      .attr('aria-label', `${c.label}: ${row.r_seats} Republicans, ${row.d_seats} Democrats` + (row.undecided_seats ? `, ${row.undecided_seats} undecided` : ''));
    svg.append('g').selectAll('circle').data(pts.map((p, i) => ({ ...p, ...seq[i] }))).join('circle')
      .attr('cx', (d) => d.x).attr('cy', (d) => d.y).attr('r', dotR)
      .attr('fill', (d) => d.kind === 'hold' ? 'var(--color-panel)' : col[d.party]).attr('stroke', (d) => col[d.party]).attr('stroke-width', (d) => d.kind === 'hold' ? 1.6 : 0);
    svg.append('text').attr('x', cx).attr('y', cy - 22).attr('text-anchor', 'middle').attr('font-family', 'var(--font-anthropic-serif)').attr('font-size', 30).attr('fill', 'var(--color-fg)')
      .text(row.undecided_seats ? '' : `${Math.max(row.r_seats, row.d_seats)}–${Math.min(row.r_seats, row.d_seats)}`);
    svg.append('text').attr('x', cx).attr('y', cy - 4).attr('text-anchor', 'middle').attr('font-size', 'var(--cds-font-size-caption)').attr('fill', 'var(--color-fg-muted)').text(`${maj} seats for a majority`);
    // text panel
    txt.replaceChildren();
    const line = (cls, t) => { const d = document.createElement('div'); d.className = cls; d.textContent = t; txt.append(d); return d; };
    line('lx-kpi-label', before ? `Current makeup (from the ${row.year} election)` : row.status === 'counting' ? `${year} makeup so far` : `Makeup after the ${year} election`);
    const big = document.createElement('div'); big.className = 'lx-chamber-nums';
    const num = (party, n, field) => { const s = document.createElement('span'); s.style.color = col[party]; const b = document.createElement('b'); b.textContent = String(n);
      b.setAttribute('data-source', c.id + '_chamber'); b.setAttribute('data-field', field); b.setAttribute('data-where', 'year=' + row.year);
      s.append(b, document.createTextNode(party === 'R' ? ' Republicans' : ' Democrats')); return s; };
    big.append(num('R', row.r_seats, 'r_seats'), num('D', row.d_seats, 'd_seats'));
    if (row.undecided_seats) { const s = document.createElement('span'); s.style.color = 'var(--color-fg-muted)'; s.textContent = `${row.undecided_seats} not yet decided`; big.append(s); }
    txt.append(big);
    if (!before && row.r_change != null) {
      const sw = row.r_change;
      line('lx-kpi-sub', sw === 0 ? `No net change from ${row.prev_year}.` : `${sw > 0 ? 'Republicans' : 'Democrats'} gained ${Math.abs(sw)} seat${Math.abs(sw) === 1 ? '' : 's'} net since ${row.prev_year}.`).style.color = sw === 0 ? '' : sw > 0 ? col.R : col.D;
    }
    if (row.majority && !row.undecided_seats) line('lx-kpi-sub', `${row.majority === 'R' ? 'Republican' : 'Democratic'} majority`);
    if (showUp) line('lx-kpi-sub', c.id === 'house' ? `Solid dots: the ${row.seats_up} seats with ${year} results. Outlined: seats not yet in the ${year} results, shown with their current party.` : `Solid dots: the ${row.seats_up} seats on the ${year} ballot. Outlined: senators not up that year, from their last election.`);
    if (before && year === 2026) line('lx-kpi-sub', 'Seats fill in from the 2026 results on election night.');
    const note = (CHAMBER_NOTES[c.id] || {})[row.year];
    if (note && !before) line('lx-chamber-note', note);
  }

  function drawMap(c, st, shapes, byD, year, sel, plan) {
    const P = c.p, el = document.getElementById(P + '-map'); el.classList.remove('dash-skeleton');
    const card = document.getElementById(P + '-map-card'), tip = document.getElementById(P + '-map-tip');
    if (!shapes.length) {
      el.replaceChildren(); const m = document.createElement('div'); m.className = 'lx-empty-map';
      m.textContent = `The ${year} district map isn't in the Legislative Council's archive, so this year has results without a map. See the table below.`; el.append(m);
      document.getElementById(P + '-legend').replaceChildren(); return;
    }
    let svg = d3.select(el).select('svg');
    if (svg.empty()) { el.replaceChildren(); svg = d3.select(el).append('svg').attr('width', '100%').attr('role', 'img').attr('aria-label', c.label + ' district map'); svg.append('g').attr('class', 'd'); svg.append('g').attr('class', 's'); }
    svg.attr('viewBox', (st.zoom || [0, 0, 678, 645]).join(' '));
    const muted = css('--cds-chart-muted');
    const hasFill = (r) => r && r.decided;
    svg.select('g.d').selectAll('path').data(shapes, (d) => d.plan + d.district).join('path')
      .attr('d', (d) => d.path).attr('fill', (d) => hasFill(byD.get(d.district)) ? fillFor(byD.get(d.district)) : muted).attr('fill-rule', 'evenodd')
      .attr('stroke', 'var(--color-panel)').attr('stroke-width', 0.6).attr('vector-effect', 'non-scaling-stroke').style('cursor', 'pointer')
      .on('mousemove', (event, d) => {
        const r = byD.get(d.district); tip.replaceChildren();
        const t = document.createElement('div'); t.className = 't'; t.textContent = `District ${d.district} · ${year}`; tip.append(t);
        if (!r) LX.tipLine(tip, null, year === 2026 ? 'No results yet' : 'Not on the ballot this year', '');
        else {
          for (let i = 1; i <= 4; i++) if (r['c' + i + '_name']) LX.tipLine(tip, partyCol(r['c' + i + '_party']), r['c' + i + '_label'], r['c' + i + '_votes'] == null ? 'Unopposed' : `${fmt(r['c' + i + '_votes'])} · ${r['c' + i + '_pct'] == null ? '—' : pct(r['c' + i + '_pct'])}`);
          LX.tipLine(tip, null, 'Margin', r.margin_label);
          if (r.status === 'counting' && r.reporting_total) LX.tipLine(tip, null, 'Precincts reporting', r.reporting_total === 100 ? `${r.reporting}%` : `${r.reporting} of ${r.reporting_total}`);
        }
        LX.placeTip(tip, card, event);
      })
      .on('mouseleave', () => { tip.style.display = 'none'; })
      .on('click', (event, d) => dash.setParams({ [P + '_district']: d.district }));
    svg.select('g.s').selectAll('path').data(shapes.filter((d) => d.district === sel), (d) => d.plan + d.district).join('path')
      .attr('d', (d) => d.path).attr('fill', 'none').attr('stroke', css('--color-fg')).attr('stroke-width', 2.2).attr('vector-effect', 'non-scaling-stroke').attr('pointer-events', 'none');
    const lg = document.getElementById(P + '-legend'); lg.replaceChildren();
    for (const [pt, nm] of [['R', 'Republican'], ['D', 'Democrat']]) {
      const g = document.createElement('span'); g.className = 'grp'; g.append(document.createTextNode(nm + ' '));
      LX.RAMP[pt].forEach((col) => { const s = document.createElement('i'); s.className = 'sw'; s.style.background = col; s.style.marginRight = '1px'; g.append(s); });
      lg.append(g);
    }
    const n = document.createElement('span'); n.textContent = 'margin, light → dark: <10 · 10–20 · 20–40 · 40–60 · 60+ pts (unopposed = darkest)'; lg.append(n);
    if (shapes.some((d) => !hasFill(byD.get(d.district)))) { const g = document.createElement('span'); g.className = 'grp'; const s = document.createElement('i'); s.className = 'sw'; s.style.background = muted; g.append(s, document.createTextNode(year === 2026 ? 'No results yet' : 'Not on the ballot')); lg.append(g); }
  }

  function drawDetail(c, r, year, sel, pending) {
    const P = c.p, box = document.getElementById(P + '-detail'); box.classList.remove('dash-skeleton');
    const title = document.getElementById(P + '-detail-title'), note = document.getElementById(P + '-detail-note'), clr = document.getElementById(P + '-clear');
    const chosen = dash.params()[P + '_district'] != null;
    clr.hidden = !chosen; clr.textContent = 'Show closest race';
    title.textContent = sel ? `District ${sel} · ${year}` : `${year} races`;
    if (!r) { box.replaceChildren(); note.textContent = sel ? (year === 2026 ? `No results for District ${sel} yet.` : `District ${sel} was not on the ballot in ${year}. Pick another district on the map or in the table.`) : 'Click a district on the map to see its candidates.'; return; }
    const counting = r.status === 'counting';
    note.textContent = (chosen ? '' : 'Closest race of the year, shown until you pick a district. ') + (!r.contested ? 'Unopposed' + (r.votes_reported ? ` · ${fmt(r.total_votes)} votes` : '') : r.votes_reported ? `Margin ${r.margin_label} · ${fmt(r.total_votes)} votes` : 'No votes counted yet') +
      (counting && r.reporting_total ? (r.reporting_total === 100 ? ` · ${r.reporting}% of precincts reporting` : ` · ${r.reporting} of ${r.reporting_total} precincts reporting`) : '');
    const list = [1, 2, 3, 4].filter((i) => r['c' + i + '_name']);
    box.replaceChildren(...list.map((i) => {
      const name = r['c' + i + '_name'], party = r['c' + i + '_party'], col = partyCol(party), where = 'year=' + year + '&district=' + r.district;
      const card = document.createElement('div'); card.className = 'lx-card lx-cand' + (i === 1 && r.decided ? ' win' : '');
      const ini = document.createElement('div'); ini.className = 'lx-initials'; ini.style.background = col; ini.textContent = LX.initials(name); ini.setAttribute('aria-hidden', 'true');
      const body = document.createElement('div'); body.className = 'lx-cand-body';
      const nm = document.createElement('div'); nm.className = 'lx-cand-name'; nm.textContent = name;
      nm.setAttribute('data-source', c.id + '_by_district'); nm.setAttribute('data-field', 'c' + i + '_name'); nm.setAttribute('data-where', where);
      const sub = document.createElement('div'); sub.className = 'lx-cand-party';
      const sp = document.createElement('span'); sp.style.color = col; sp.textContent = (PARTY[party] || party) + ' (' + party + ')'; sub.append(sp);
      const word = !r.contested ? (i === 1 ? 'Unopposed' : '') : !r.votes_reported ? '' : LX.stateWord(r.status, i === 1);
      if (word) { const b = document.createElement('span'); b.className = 'lx-badge'; b.textContent = word; sub.append(b); }
      const big = document.createElement('div'); big.className = 'lx-cand-pct'; big.textContent = r['c' + i + '_pct'] == null ? '—' : pct(r['c' + i + '_pct']);
      big.setAttribute('data-source', c.id + '_by_district'); big.setAttribute('data-field', 'c' + i + '_pct'); big.setAttribute('data-where', where);
      const vt = document.createElement('div'); vt.className = 'lx-cand-votes'; vt.textContent = r['c' + i + '_votes'] == null ? 'No vote total reported' : fmt(r['c' + i + '_votes']) + ' votes';
      const bar = document.createElement('div'); bar.className = 'lx-cand-bar'; const bi = document.createElement('i'); bi.style.width = ((r['c' + i + '_pct'] ?? 0) * 100).toFixed(1) + '%'; bi.style.background = col; bar.append(bi);
      body.append(nm, sub, big, vt, bar);
      const bio = year === 2026 ? bioFor(c.id, r.district, name) : null;
      if (bio) {
        const p = document.createElement('p'); p.className = 'lx-cand-bio';
        p.setAttribute('data-source', 'candidate_bios'); p.setAttribute('data-field', 'summary'); p.setAttribute('data-where', 'level=' + c.id + '&district=' + r.district + '&candidate=' + enc(name));
        if (bio.summary) {
          p.append(document.createTextNode(bio.summary + ' '));
          const a = document.createElement('a'); a.href = bio.source_url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = 'Source: ' + bio.source; p.append(a);
        } else p.textContent = 'No background information found.';
        card.append(ini, body, p); return card;
      }
      card.append(ini, body); return card;
    }));
  }

  // one- or two-sentence background for 2026 candidates (U.S. House, Texas House, Texas Senate)
  const normName = (s) => String(s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z]/g, '');
  let bioIndex = null, bioRows = null;
  function bioFor(level, district, name) {
    const d = dash.data('candidate_bios');
    if (d.status !== 'ok') return null;
    if (bioRows !== d.data) { bioRows = d.data; bioIndex = new Map(d.data.map((b) => [b.level + '|' + Number(b.district) + '|' + normName(b.candidate), b])); }
    return bioIndex.get(level + '|' + Number(district) + '|' + normName(name)) || null;
  }

  function drawSeats(c, sum, year, fullSize) {
    const P = c.p, el = document.getElementById(P + '-seats'); el.classList.remove('dash-skeleton'); el.replaceChildren();
    const W = Math.max(280, el.clientWidth), H = 240, card = document.getElementById(P + '-seats-card'), tip = document.getElementById(P + '-seats-tip');
    const yrs = [...new Set(sum.map((r) => r.year).concat([2026]))].sort((a, b) => a - b);
    const byY = new Map(sum.map((r) => [r.year, r]));
    const maxS = d3.max(sum, (r) => r.seats_total) || 1;
    const y = d3.scaleLinear([0, maxS], [H - 24, 8]).nice(5);
    const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', '100%').attr('role', 'img').attr('aria-label', 'Seats won by party per election');
    const ticks = y.ticks(5);
    const tl = svg.append('g').selectAll('text').data(ticks).join('text').attr('x', 0).attr('y', (d) => y(d)).attr('dy', '0.32em').attr('fill', 'var(--color-fg-muted)').attr('font-size', 'var(--cds-font-size-caption)').text((d) => d);
    let ml = 0; tl.each(function () { ml = Math.max(ml, this.getComputedTextLength()); });
    const left = ml + 8, x = d3.scaleBand(yrs, [left, W - 4]).padding(0.28);
    svg.append('g').selectAll('line').data(ticks).join('line').attr('x1', left).attr('x2', W - 4).attr('y1', (d) => y(d)).attr('y2', (d) => y(d)).attr('stroke', 'var(--cds-chart-grid)');
    const RED = css('--lx-rep'), BLUE = css('--lx-dem'), OTH = css('--lx-ind'), MUT = css('--cds-chart-muted');
    const data = yrs.map((yy) => { const r = byY.get(yy); return r && r.status !== 'pending' ? r : { year: yy, seats_total: 0, seats_r: 0, seats_d: 0, seats_other: 0, undecided: 0, pending: true }; });
    const g = svg.append('g').selectAll('g').data(data).join('g').attr('opacity', (d) => d.year === year ? 1 : 0.55).style('cursor', 'pointer')
      .on('click', (e, d) => dash.setParams({ [P + '_year']: d.year }))
      .on('mousemove', (event, d) => { tip.replaceChildren(); const t = document.createElement('div'); t.className = 't'; t.textContent = d.pending ? `${d.year} · results on election night` : `${d.year} · ${d.seats_total} seats on the ballot`; tip.append(t);
        if (!d.pending) { LX.tipLine(tip, RED, 'Republican', String(d.seats_r)); LX.tipLine(tip, BLUE, 'Democratic', String(d.seats_d)); if (d.seats_other) LX.tipLine(tip, OTH, 'Other', String(d.seats_other)); if (d.undecided) LX.tipLine(tip, MUT, 'No votes yet', String(d.undecided)); }
        LX.placeTip(tip, card, event); })
      .on('mouseleave', () => { tip.style.display = 'none'; });
    let base = (d) => 0;
    const seg = (key, col) => g.append('rect').attr('x', (d) => x(d.year)).attr('width', x.bandwidth()).attr('fill', col)
      .attr('y', (d) => y(base(d) + d[key])).attr('height', (d) => y(base(d)) - y(base(d) + d[key]));
    seg('seats_r', RED); base = (d) => d.seats_r; seg('seats_d', BLUE); base = (d) => d.seats_r + d.seats_d; seg('seats_other', OTH); base = (d) => d.seats_r + d.seats_d + d.seats_other; seg('undecided', MUT);
    g.filter((d) => d.pending).append('rect').attr('x', (d) => x(d.year)).attr('width', x.bandwidth()).attr('y', y(maxS)).attr('height', y(0) - y(maxS)).attr('fill', 'none').attr('stroke', MUT).attr('stroke-dasharray', '3 3').attr('rx', 3);
    g.filter((d) => d.year === year && !d.pending).append('rect').attr('x', (d) => x(d.year) - 2).attr('width', x.bandwidth() + 4).attr('y', (d) => y(d.seats_total) - 2).attr('height', (d) => y(0) - y(d.seats_total) + 4).attr('fill', 'none').attr('stroke', 'var(--color-fg)').attr('stroke-width', 1.5).attr('rx', 3);
    // majority line for years where the whole body was elected
    const maj = Math.floor(fullSize / 2) + 1;
    if (fullSize && sum.some((r) => r.seats_total === fullSize)) svg.append('line').attr('x1', left).attr('x2', W - 4).attr('y1', y(maj)).attr('y2', y(maj)).attr('stroke', 'var(--cds-chart-reference)').attr('stroke-dasharray', '4 3');
    const every = W < 420 ? 3 : 1;
    svg.append('g').selectAll('text').data(data.filter((d, i) => i % every === 0 || d.year === year)).join('text').attr('x', (d) => x(d.year) + x.bandwidth() / 2).attr('y', H - 6).attr('text-anchor', 'middle').attr('fill', 'var(--color-fg-muted)').attr('font-size', 'var(--cds-font-size-caption)').text((d) => W < 520 ? "'" + String(d.year).slice(2) : String(d.year));
    document.getElementById(P + '-seats-note').textContent = `Seats on the ballot each year, by winning party. ${fullSize ? `Dashed line: ${maj} seats, a majority of ${fullSize}. ` : ''}Click a bar to switch years.`;
  }

  function drawTable(c, st, rows, sel, pending) {
    const P = c.p;
    let list = rows.filter((r) => !st.q || String(r.district) === st.q || [1, 2, 3, 4].some((i) => (r['c' + i + '_name'] || '').toLowerCase().includes(st.q)));
    list = list.slice().sort((a, b) => {
      const va = a[st.sortKey], vb = b[st.sortKey];
      if (va == null && vb == null) return 0; if (va == null) return 1; if (vb == null) return -1;
      return (typeof va === 'string' ? va.localeCompare(vb) : va - vb) * st.sortDir;
    });
    document.getElementById(P + '-count').textContent = pending ? 'No results yet.' : st.q ? `${list.length} of ${rows.length}` : `${rows.length} districts`;
    document.querySelectorAll(`#${P}-table th`).forEach((th) => {
      const b = th.querySelector('button'), k = b.dataset.sort;
      th.setAttribute('aria-sort', k === st.sortKey ? (st.sortDir > 0 ? 'ascending' : 'descending') : 'none');
      b.textContent = b.dataset.label + (k === st.sortKey ? (st.sortDir > 0 ? ' ▲' : ' ▼') : '');
    });
    const tb = document.querySelector(`#${P}-table tbody`);
    tb.replaceChildren(...list.map((r) => {
      const tr = document.createElement('tr'); tr.dataset.key = r.year + ',' + r.district; tr.dataset.district = r.district; if (r.district === sel) tr.className = 'sel';
      const td = (t, cls) => { const x = document.createElement('td'); x.textContent = t; if (cls) x.className = cls; tr.append(x); return x; };
      td(String(r.district));
      for (let i = 1; i <= 4; i++) {
        const cell = td('', i >= 3 ? 'lx-hide-narrow lx-cand-cell' : 'lx-cand-cell');
        if (!r['c' + i + '_name']) { cell.textContent = '—'; continue; }
        const n = document.createElement('span'); n.textContent = r['c' + i + '_label']; n.style.color = partyCol(r['c' + i + '_party']);
        const v = document.createElement('span'); v.className = 'lx-cell-pct'; v.textContent = !r.contested ? ' unopposed' : r['c' + i + '_pct'] == null ? '' : ' ' + pct(r['c' + i + '_pct']);
        cell.append(n, v);
      }
      td(r.margin_label, !r.contested ? '' : r.margin > 0 ? 'lx-r' : r.margin < 0 ? 'lx-d' : '');
      td(r.votes_reported ? fmt(r.total_votes) : '—', 'lx-hide-narrow');
      return tr;
    }));
  }

  dash.onData(draw);
})();
