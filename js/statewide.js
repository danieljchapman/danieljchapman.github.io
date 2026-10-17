(() => {
  const LX = window.LX;
  const { css, fmt, pct, enc, PARTY, partyCol } = LX;
  const lab = (m) => (m == null || isNaN(m)) ? '—' : Math.abs(m) < 0.0005 ? 'Even' : (m > 0 ? 'R+' : 'D+') + (Math.abs(m) * 100).toFixed(1);
  const OFFICES = [['Governor', 'Governor'], ['Senate', 'U.S. Senate'], ['Lt. Governor', 'Lt. Governor'], ['Attorney General', 'Attorney General'], ['Comptroller', 'Comptroller'],
    ['Land Commissioner', 'Land Commissioner'], ['Agriculture Commissioner', 'Agriculture Commissioner'], ['Railroad Commissioner', 'Railroad Commissioner'], ['Supreme Court', 'Texas Supreme Court']];
  const officeOf = (o) => o.startsWith('Railroad Commissioner') ? 'Railroad Commissioner' : o.startsWith('Supreme Court') ? 'Supreme Court' : o;
  const OFFICE_NAME = { Governor: 'governor', Senate: 'U.S. Senate', 'Lt. Governor': 'lieutenant governor', 'Attorney General': 'attorney general', Comptroller: 'comptroller',
    'Land Commissioner': 'land commissioner', 'Agriculture Commissioner': 'agriculture commissioner', 'Railroad Commissioner': 'Railroad Commission', 'Railroad Commissioner (unexpired term)': 'Railroad Commission (unexpired term)' };
  const officeName = (o) => OFFICE_NAME[o] || (o.startsWith('Supreme Court') ? 'Texas ' + o.replace(',', '').replace(' (unexpired term)', ' (unexpired term)') : o);
  const seatLabel = (o) => o.replace('Supreme Court, ', '').replace(' (unexpired term)', ', unexpired term');
  // county results the official canvass itself records in error; shown uncolored with a note
  const FLAGS = { '2010 Attorney General|48257': 'The official canvass records only 1,470 votes for Abbott here, against 13,600–15,000 for every other Republican on this ballot — almost certainly a reporting error. Shown without color; the certified numbers are kept in the totals.' };

  // ---------- calculations ----------
  dash.calc('by_county', {
    title: 'Results per county and race',
    description: 'Each county\'s vote shares, Republican-minus-Democratic margin, winner, and shift from the previous race for the same office; 2026 rows come from the election-night file.',
    inputs: ['results', 'live_2026'],
    fn: (results, live_2026) => {
      const lab = (m) => (m == null || isNaN(m)) ? '—' : Math.abs(m) < 0.0005 ? 'Even' : (m > 0 ? 'R+' : 'D+') + (Math.abs(m) * 100).toFixed(1);
      const all = results.map((r) => ({ ...r, status: 'final' })).concat(live_2026.filter((r) => r.level === 'statewide').map((r) => ({
        race: r.race, year: r.year, office: r.office, county_fips: String(r.unit).padStart(5, '0'), county: r.unit_name, candidate: r.candidate, party: r.party, votes: r.votes,
        status: r.status, reporting: r.reporting, reporting_total: r.reporting_total })));
      const m = new Map(), tot = new Map();
      for (const r of all) {
        const k = r.race + '|' + r.county_fips;
        let o = m.get(k);
        if (!o) { o = { race: r.race, year: Number(r.year), office: r.office, county_fips: r.county_fips, county: r.county, rep_votes: 0, dem_votes: 0, other_votes: 0, total_votes: 0, best: [], status: r.status,
          reporting: r.reporting === '' || r.reporting == null ? null : Number(r.reporting), reporting_total: r.reporting_total === '' || r.reporting_total == null ? null : Number(r.reporting_total) }; m.set(k, o); }
        const v = Number(r.votes) || 0;
        o.total_votes += v;
        if (r.party === 'R') o.rep_votes += v; else if (r.party === 'D') o.dem_votes += v; else o.other_votes += v;
        if (r.party !== 'W') { o.best.push([r.candidate, r.party, v]); const tk = r.race + '|' + r.candidate; tot.set(tk, (tot.get(tk) || 0) + v); }
      }
      const rankOf = new Map();
      for (const race of new Set(all.map((r) => r.race))) {
        [...tot.entries()].filter(([k]) => k.startsWith(race + '|')).sort((a, b) => b[1] - a[1]).forEach(([k], i) => rankOf.set(k, i + 1));
      }
      const rows = [...m.values()].map((o) => {
        o.best.sort((a, b) => b[2] - a[2]);
        const t = o.total_votes, rep = t > 0;
        const out = { race: o.race, year: o.year, office: o.office, county_fips: o.county_fips, county: o.county, status: o.status, reported: rep,
          reporting: o.reporting, reporting_total: o.reporting_total,
          rep_votes: o.rep_votes, dem_votes: o.dem_votes, other_votes: o.other_votes, total_votes: t,
          rep_pct: rep ? o.rep_votes / t : null, dem_pct: rep ? o.dem_votes / t : null, other_pct: rep ? o.other_votes / t : null,
          margin: rep ? (o.rep_votes - o.dem_votes) / t : null,
          winner_name: rep ? o.best[0][0] : null, winner_party: rep ? o.best[0][1] : null, winner_lead: rep ? (o.best[0][2] - (o.best[1] ? o.best[1][2] : 0)) / t : null };
        out.margin_label = lab(out.margin);
        for (const [name, , v] of o.best) {
          const rk = rankOf.get(o.race + '|' + name);
          if (rk && rk <= 4) out['c' + rk + '_pct'] = rep ? v / t : null;
        }
        return out;
      });
      // previous race for the same office (both Railroad Commission races count as one office)
      // Railroad Commission races form one series; each Supreme Court seat is its own series (compared with its last election, usually six years earlier)
      const off = (o) => o.indexOf('Railroad Commissioner') === 0 ? 'Railroad Commissioner' : o.replace(' (unexpired term)', '');
      // only races with both a Republican and a Democrat on the ballot are compared
      const hasR = new Set(all.filter((r) => r.party === 'R').map((r) => r.race)), hasD = new Set(all.filter((r) => r.party === 'D').map((r) => r.race));
      const seq = new Map();
      for (const r of rows) { if (!hasR.has(r.race) || !hasD.has(r.race)) continue; const k = off(r.office); if (!seq.has(k)) seq.set(k, new Map()); seq.get(k).set(r.race, r.year); }
      const prevRace = new Map();
      for (const [, races] of seq) {
        const list = [...races.entries()].sort((a, b) => a[1] - b[1] || a[0].length - b[0].length);
        list.forEach(([race], i) => prevRace.set(race, i > 0 ? list[i - 1][0] : null));
      }
      const idx = new Map(rows.map((r) => [r.race + '|' + r.county_fips, r]));
      for (const r of rows) {
        const pr = prevRace.get(r.race), p = pr ? idx.get(pr + '|' + r.county_fips) : null;
        r.prev_race = pr || null;
        const done = r.status === 'final' || (r.reporting_total != null && r.reporting >= r.reporting_total);
        r.shift = p && done && r.reported && p.reported ? r.margin - p.margin : null;
        r.shift_label = r.shift == null ? '—' : lab(r.shift);
      }
      return rows;
    },
  });

  dash.calc('statewide', {
    title: 'Statewide totals per race',
    description: 'Each race summed over all 254 counties: leader, vote shares, margin, shift from the previous race for the office, counties carried and counties reporting.',
    inputs: ['by_county'],
    fn: (by_county) => {
      const lab = (m) => (m == null || isNaN(m)) ? '—' : Math.abs(m) < 0.0005 ? 'Even' : (m > 0 ? 'R+' : 'D+') + (Math.abs(m) * 100).toFixed(1);
      const g = new Map();
      for (const c of by_county) {
        let o = g.get(c.race);
        if (!o) { o = { race: c.race, year: c.year, office: c.office, status: c.status, prev_race: c.prev_race, rep_votes: 0, dem_votes: 0, other_votes: 0, total_votes: 0,
          counties_rep: 0, counties_dem: 0, counties_other: 0, counties_reporting: 0, prec_rep: 0, prec_tot: 0 }; g.set(c.race, o); }
        o.rep_votes += c.rep_votes; o.dem_votes += c.dem_votes; o.other_votes += c.other_votes; o.total_votes += c.total_votes;
        if (c.reported) { o.counties_reporting++; if (c.winner_party === 'R') o.counties_rep++; else if (c.winner_party === 'D') o.counties_dem++; else o.counties_other++; }
        if (c.reporting != null) o.prec_rep += c.reporting;
        if (c.reporting_total != null) o.prec_tot += c.reporting_total;
      }
      const rows = [...g.values()].map((o) => {
        const t = o.total_votes, rep = t > 0, margin = rep ? (o.rep_votes - o.dem_votes) / t : null;
        return { race: o.race, year: o.year, office: o.office, status: o.status, prev_race: o.prev_race,
          rep_votes: o.rep_votes, dem_votes: o.dem_votes, other_votes: o.other_votes, total_votes: t,
          margin, margin_label: lab(margin), counties_rep: o.counties_rep, counties_dem: o.counties_dem, counties_other: o.counties_other,
          counties_reporting: o.counties_reporting, precincts_reporting_pct: o.prec_tot ? o.prec_rep / o.prec_tot : null };
      });
      const idx = new Map(rows.map((r) => [r.race, r]));
      for (const r of rows) {
        const p = r.prev_race ? idx.get(r.prev_race) : null;
        r.shift = p && r.status === 'final' && r.margin != null && p.margin != null ? r.margin - p.margin : null;
        r.shift_label = r.shift == null ? '—' : lab(r.shift);
      }
      return rows.sort((a, b) => a.year - b.year || a.office.localeCompare(b.office));
    },
  });

  dash.calc('candidates_statewide', {
    title: 'Top four candidates per race',
    description: 'Each race\'s ballot candidates ranked by statewide votes (write-ins excluded), with share of all votes cast; the top four are kept. "winner" is set only once a count is final.',
    inputs: ['results', 'live_2026'],
    fn: (results, live_2026) => {
      const all = results.map((r) => ({ race: r.race, candidate: r.candidate, party: r.party, votes: r.votes, status: 'final' }))
        .concat(live_2026.filter((r) => r.level === 'statewide').map((r) => ({ race: r.race, candidate: r.candidate, party: r.party, votes: r.votes, status: r.status })));
      const races = new Map();
      for (const r of all) {
        let o = races.get(r.race);
        if (!o) { o = { total: 0, status: r.status, cand: new Map() }; races.set(r.race, o); }
        const v = Number(r.votes) || 0; o.total += v;
        if (r.party !== 'W') { const c = o.cand.get(r.candidate) || { party: r.party, votes: 0 }; c.votes += v; o.cand.set(r.candidate, c); }
      }
      const rows = [];
      for (const [race, o] of races) {
        [...o.cand.entries()].sort((a, b) => b[1].votes - a[1].votes || a[0].localeCompare(b[0])).slice(0, 4).forEach(([candidate, c], i) => {
          rows.push({ race, rank: i + 1, candidate, party: c.party, votes: c.votes, pct: o.total ? c.votes / o.total : null, status: o.status, winner: o.status === 'final' && i === 0 && o.total > 0 });
        });
      }
      return rows;
    },
  });

  // ---------- page ----------
  const params = () => { const p = dash.params(); return { race: p.race || '2024 Senate', view: p.view || 'result', county: p.county || null }; };
  document.querySelectorAll('[data-view]').forEach((b) => b.addEventListener('click', () => dash.setParams({ view: b.dataset.view })));
  const clearBtn = document.getElementById('clear-county');
  clearBtn.addEventListener('click', () => dash.setParams({ county: null }));
  let sortKey = 'total_votes', sortDir = -1, query = '';
  document.querySelectorAll('#county-table th button').forEach((b) => b.addEventListener('click', () => {
    const k = b.dataset.sort;
    if (sortKey === k) sortDir = -sortDir; else { sortKey = k; sortDir = k === 'county' ? 1 : -1; }
    draw();
  }));
  const search = document.getElementById('search');
  search.addEventListener('input', () => { query = search.value.trim().toLowerCase(); draw(); });
  document.querySelector('#county-table tbody').addEventListener('click', (e) => {
    const tr = e.target.closest('tr[data-fips]');
    if (tr) dash.setParams({ county: params().county === tr.dataset.fips ? null : tr.dataset.fips });
  });

  function buildPickers(sw, current) {
    const races = new Map();
    for (const r of sw) races.set(r.race, { race: r.race, year: r.year, office: r.office });
    for (const o of LX.SCHEDULE_2026.statewide) if (!races.has('2026 ' + o)) races.set('2026 ' + o, { race: '2026 ' + o, year: 2026, office: o });
    const list = [...races.values()].map((r) => ({ race: r.race, year: r.year, group: officeOf(r.office),
      yearLabel: (r.year === 2026 ? '2026 (Nov. 3)' : String(r.year)) + (r.office.startsWith('Supreme Court') ? ' · ' + seatLabel(r.office) : r.office.includes('unexpired') ? ' (unexpired term)' : '') }));
    LX.racePicker(document.getElementById('race-rows'), OFFICES, list, current, (race) => dash.setParams({ race }));
  }

  let cacheKey = null, byRace = null, rawIdx = null;
  function draw() {
    if (LX.tab() !== 'statewide' || LX.swView() !== 'offices') return;
    const p = params();
    const res = dash.data('results'), live = dash.data('live_2026'), shp = dash.data('county_shapes'), bc = dash.data('by_county'), sw = dash.data('statewide'), cs = dash.data('candidates_statewide');
    const deps = [res, live, shp, bc, sw, cs];
    document.querySelectorAll('[data-view]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.view === p.view)));
    document.querySelectorAll('#view-offices [data-source="statewide"][data-field]').forEach((el) => el.setAttribute('data-where', 'race=' + LX.enc(p.race)));
    if (!deps.every((d) => d.status === 'ok')) {
      if (deps.some((d) => d.status === 'error' || d.status === 'missing')) ['map', 'trend', 'cand-cards'].forEach((id) => LX.failLine(document.getElementById(id)));
      return;
    }
    buildPickers(sw.data, p.race);
    if (cacheKey !== bc.data) {
      cacheKey = bc.data; byRace = d3.group(bc.data, (d) => d.race);
      const raw = res.data.concat(live.data.filter((r) => r.level === 'statewide').map((r) => ({ race: r.race, county_fips: String(r.unit).padStart(5, '0'), candidate: r.candidate, party: r.party, votes: r.votes })));
      rawIdx = d3.group(raw, (d) => d.race + '|' + d.county_fips);
    }
    const year = Number(p.race.slice(0, 4)), office = p.race.slice(5);
    const S = sw.data.find((r) => r.race === p.race) || null;
    const pending = !S || S.total_votes === 0;
    const status = S ? S.status : 'pending';
    const rows = (S && byRace.get(S.race)) || [];
    const C = cs.data.filter((r) => r.race === p.race).sort((a, b) => a.rank - b.rank);
    LX.liveBanner(document.getElementById('sw-live'), year);

    // takeaway
    const tk = document.getElementById('takeaway'); tk.classList.remove('dash-skeleton'); tk.replaceChildren();
    const add = (t, b, mark) => {
      const n = document.createElement(b ? 'b' : 'span'); n.textContent = t;
      if (mark) { n.setAttribute('data-source', 'statewide'); n.setAttribute('data-field', mark); n.setAttribute('data-where', 'race=' + enc(p.race)); }
      tk.append(n);
    };
    const oname = officeName(office);
    if (pending) {
      add(`The ${year} ${oname} race is on the ballot ${LX.ELECTION_2026}. `);
      add(C.length ? `${C.length} candidates are listed below; results will fill in as counties report.` : 'Candidates and results will appear here on election night.');
    } else {
      const lead = C[0];
      add(lead.candidate, true);
      if (S.rep_votes && S.dem_votes) {
        add(status === 'final' ? ` won the ${year} ${oname} race by ` : ` leads the ${year} ${oname} race by `);
        add(Math.abs(S.margin * 100).toFixed(1) + ' points', true);
        add(` (${S.margin_label})`);
      } else {
        add(status === 'final' ? ` won the ${year} ${oname} race with ` : ` leads the ${year} ${oname} race with `);
        add(pct(lead.pct), true); add(' of the vote');
      }
      if (status === 'counting') { add(', with '); add(String(S.counties_reporting), true, 'counties_reporting'); add(' of 254 counties reporting.'); }
      else { add(', carrying '); add(String(lead.party === 'R' ? S.counties_rep : lead.party === 'D' ? S.counties_dem : S.counties_other), true); add(' of 254 counties.'); }
      if (S.prev_race && S.shift != null) {
        add(` Compared with ${S.prev_race}, the statewide margin moved `);
        add(S.shift_label, true, 'shift_label');
        add(S.shift > 0 ? ' toward Republicans.' : S.shift < 0 ? ' toward Democrats.' : '.');
      } else if (S.margin != null && !S.dem_votes) add(' No Democrat was on the ballot.');
    }

    drawCands(C, status, pending);
    // KPIs
    const set = (sel, v) => document.querySelectorAll(sel).forEach((el) => { el.textContent = v; el.classList.remove('dash-skeleton'); });
    set('#kpi-margin .lx-kpi-value', pending ? '—' : S.margin_label);
    document.querySelector('#kpi-margin .lx-kpi-value').style.color = pending ? '' : S.margin > 0 ? css('--lx-rep') : css('--lx-dem');
    set('#kpi-margin [data-field="shift_label"]', S ? S.shift_label : '—');
    document.getElementById('kpi-prev').textContent = S && S.prev_race ? ' vs ' + S.prev_race : '';
    set('#kpi-counties [data-field="counties_rep"]', pending ? '—' : String(S.counties_rep));
    set('#kpi-counties [data-field="counties_dem"]', pending ? '—' : String(S.counties_dem));
    document.querySelector('#kpi-counties .lx-kpi-value').classList.remove('dash-skeleton');
    document.getElementById('kpi-counties-other').textContent = pending ? '' : status === 'counting' ? `${S.counties_reporting} of 254 counties reporting` : S.counties_other ? `${S.counties_other} won by another candidate` : '';
    set('#kpi-votes .lx-kpi-value', pending ? '—' : fmt(S.total_votes));
    set('#kpi-votes [data-field="other_votes"]', pending ? '—' : fmt(S.other_votes));
    document.getElementById('kpi-other-pct').textContent = pending ? '' : ' (' + pct(S.other_votes / S.total_votes) + ')';
    document.getElementById('kpi-votes-label').textContent = status === 'counting' ? 'Votes counted so far' : 'Total votes cast in race';

    drawMap(p, S, rows, shp.data, pending);
    drawTrend(p, sw.data, bc.data, office);
    drawTable(p, S, rows, C, pending);
  }

  function drawCands(list, status, pending) {
    const box = document.getElementById('cand-cards'); box.classList.remove('dash-skeleton');
    const photos = window.LX_PHOTOS || {};
    let anyPhoto = false, anyInitials = false;
    if (!list.length) {
      box.replaceChildren(); const m = document.createElement('div'); m.className = 'lx-card lx-empty'; m.textContent = 'Candidates will appear here once the state publishes election-night returns.'; box.append(m);
      document.getElementById('photo-credit').textContent = ''; return;
    }
    box.replaceChildren(...list.map((c) => {
      const card = document.createElement('div'); card.className = 'lx-card lx-cand' + (c.rank === 1 && !pending ? ' win' : ''); card.id = 'cand-' + c.rank;
      const col = partyCol(c.party), where = 'race=' + enc(c.race) + '&rank=' + c.rank;
      if (photos[c.candidate]) { anyPhoto = true; const img = document.createElement('img'); img.className = 'lx-photo'; img.src = photos[c.candidate]; img.alt = 'Official portrait of ' + c.candidate; card.append(img); }
      else { anyInitials = true; const ini = document.createElement('div'); ini.className = 'lx-initials'; ini.style.background = col; ini.setAttribute('aria-hidden', 'true'); ini.textContent = LX.initials(c.candidate); card.append(ini); }
      const body = document.createElement('div'); body.className = 'lx-cand-body';
      const nm = document.createElement('div'); nm.className = 'lx-cand-name'; nm.textContent = c.candidate;
      nm.setAttribute('data-source', 'candidates_statewide'); nm.setAttribute('data-field', 'candidate'); nm.setAttribute('data-where', where);
      const pt = document.createElement('div'); pt.className = 'lx-cand-party';
      const pn = document.createElement('span'); pn.textContent = (PARTY[c.party] || c.party) + ' (' + c.party + ')'; pn.style.color = col; pt.append(pn);
      const word = pending ? '' : LX.stateWord(status, c.rank === 1);
      if (word) { const b = document.createElement('span'); b.className = 'lx-badge'; b.textContent = word; pt.append(b); }
      const pc = document.createElement('div'); pc.className = 'lx-cand-pct'; pc.textContent = c.pct == null ? '—' : pct(c.pct);
      pc.setAttribute('data-source', 'candidates_statewide'); pc.setAttribute('data-field', 'pct'); pc.setAttribute('data-where', where);
      const vt = document.createElement('div'); vt.className = 'lx-cand-votes';
      const vs = document.createElement('span'); vs.textContent = fmt(c.votes);
      vs.setAttribute('data-source', 'candidates_statewide'); vs.setAttribute('data-field', 'votes'); vs.setAttribute('data-where', where);
      vt.append(vs, document.createTextNode(' votes'));
      const bar = document.createElement('div'); bar.className = 'lx-cand-bar'; const bi = document.createElement('i'); bi.style.width = ((c.pct || 0) * 100).toFixed(1) + '%'; bi.style.background = col; bar.append(bi);
      body.append(nm, pt, pc, vt, bar); card.append(body); return card;
    }));
    const n = list.length;
    let note = n < 4 && !pending ? `Only ${n} candidates were on the ballot in this race. ` : '';
    if (anyPhoto) note += 'Photos are official U.S. Congress portraits (public domain).';
    if (anyInitials) note += (anyPhoto ? ' ' : '') + 'Initials stand in for candidates without a public-domain official portrait.';
    document.getElementById('photo-credit').textContent = note;
  }

  const SHIFT_BINS = [-0.1, -0.05, -0.02, 0, 0.02, 0.05, 0.1];
  function drawMap(p, S, rows, shapes, pending) {
    const el = document.getElementById('map'); el.classList.remove('dash-skeleton');
    const R = LX.RAMP, byF = new Map(rows.map((r) => [r.county_fips, r])), muted = css('--cds-chart-muted');
    const resultColor = (r) => r.winner_party !== 'R' && r.winner_party !== 'D' ? LX.rampColor('I', r.winner_lead) : LX.rampColor(r.margin >= 0 ? 'R' : 'D', r.margin);
    const shiftColor = (s) => s == null ? muted : [R.D[4], R.D[3], R.D[1], R.D[0], R.R[0], R.R[1], R.R[3], R.R[4]][d3.bisect(SHIFT_BINS, s)];
    const fill = (r) => !r || !r.reported || FLAGS[p.race + '|' + r.county_fips] ? muted : p.view === 'shift' ? shiftColor(r.shift) : resultColor(r);
    let svg = d3.select(el).select('svg');
    if (svg.empty()) { el.replaceChildren(); svg = d3.select(el).append('svg').attr('viewBox', '0 0 678 645').attr('width', '100%').attr('role', 'img').attr('aria-label', 'Map of Texas counties'); svg.append('g').attr('class', 'cties'); svg.append('g').attr('class', 'selg'); }
    const card = document.getElementById('map-card'), tip = document.getElementById('map-tip');
    svg.select('g.cties').selectAll('path.cty').data(shapes, (d) => d.county_fips).join('path')
      .attr('class', 'cty').attr('d', (d) => d.path).attr('fill', (d) => fill(byF.get(d.county_fips)))
      .on('mousemove', (event, d) => {
        const r = byF.get(d.county_fips); tip.replaceChildren();
        const t = document.createElement('div'); t.className = 't'; t.textContent = `${d.county} County · ${p.race}`; tip.append(t);
        const flag = FLAGS[p.race + '|' + d.county_fips];
        if (flag) { const n = document.createElement('div'); n.style.maxWidth = '15rem'; n.style.margin = '2px 0 4px'; n.style.color = 'var(--color-bad)'; n.textContent = flag; tip.append(n); }
        if (!r || !r.reported) LX.tipLine(tip, null, 'No results yet', '');
        else {
          const raw = (rawIdx.get(p.race + '|' + d.county_fips) || []).slice().sort((a, b) => (a.party === 'W') - (b.party === 'W') || Number(b.votes) - Number(a.votes));
          for (const c of raw) LX.tipLine(tip, partyCol(c.party), c.candidate + (c.party === 'W' ? '' : ' (' + c.party + ')'), `${fmt(Number(c.votes))} · ${pct(Number(c.votes) / (r.total_votes || 1))}`);
          LX.tipLine(tip, null, 'Margin', r.margin_label);
          if (r.prev_race && r.shift != null) LX.tipLine(tip, null, `Shift vs ${r.prev_race}`, r.shift_label);
          if (r.status === 'counting' && r.reporting_total) LX.tipLine(tip, null, 'Precincts reporting', r.reporting_total === 100 ? `${r.reporting}%` : `${r.reporting} of ${r.reporting_total}`);
        }
        LX.placeTip(tip, card, event);
      })
      .on('mouseleave', () => { tip.style.display = 'none'; })
      .on('click', (event, d) => dash.setParams({ county: p.county === d.county_fips ? null : d.county_fips }));
    svg.select('g.selg').selectAll('path').data(shapes.filter((d) => d.county_fips === p.county), (d) => d.county_fips).join('path')
      .attr('d', (d) => d.path).attr('fill', 'none').attr('stroke', css('--color-fg')).attr('stroke-width', 2.2).attr('pointer-events', 'none');
    document.getElementById('map-title').textContent = p.view === 'shift' ? `${p.race}: shift since ${S && S.prev_race ? S.prev_race : '—'}` : `${p.race}: county results`;
    document.getElementById('map-note').textContent = pending ? 'No county has reported yet. Counties fill in as results arrive on election night.'
      : p.view === 'shift' ? (S.prev_race ? `Change in each county's R − D margin compared with ${S.prev_race}.` : 'No earlier race for this office in the data, so there is no shift to show.')
      : 'Red: Republican margin, blue: Democratic margin. The darker the shade, the bigger the margin. Click a county to follow it over time.';
    const lg = document.getElementById('legend'); lg.replaceChildren();
    const sw = (c, t) => { const g = document.createElement('span'); g.className = 'grp'; const s = document.createElement('i'); s.className = 'sw'; s.style.background = c; g.append(s, document.createTextNode(t)); lg.append(g); };
    if (p.view === 'shift') {
      ['D >10', 'D 5–10', 'D 2–5', 'D 0–2', 'R 0–2', 'R 2–5', 'R 5–10', 'R >10'].forEach((t, i) => sw(shiftColor([-0.2, -0.07, -0.03, -0.01, 0.01, 0.03, 0.07, 0.2][i]), t));
      const n = document.createElement('span'); n.textContent = 'points of shift'; lg.append(n);
    } else {
      const parties = [['R', 'Republican'], ['D', 'Democrat']];
      if (S && S.counties_other) parties.push(['I', 'Other candidate']);
      for (const [pt, nm] of parties) {
        const g = document.createElement('span'); g.className = 'grp'; g.append(document.createTextNode(nm + ' '));
        R[pt].forEach((c) => { const s = document.createElement('i'); s.className = 'sw'; s.style.background = c; s.style.marginRight = '1px'; g.append(s); });
        lg.append(g);
      }
      const n = document.createElement('span'); n.textContent = 'margin, light → dark: <10 · 10–20 · 20–40 · 40–60 · 60+ pts'; lg.append(n);
    }
    if (rows.length < 254 || rows.some((r) => !r.reported)) sw(muted, 'No results yet');
  }

  function drawTrend(p, sw, bc, office) {
    const el = document.getElementById('trend'); el.classList.remove('dash-skeleton'); el.replaceChildren();
    const W = Math.max(280, el.clientWidth), H = 260;
    const cty = p.county ? bc.filter((r) => r.county_fips === p.county && r.reported) : [];
    const ctyName = cty.length ? cty[0].county : null;
    const focus = officeOf(office);
    const series = [];
    OFFICES.forEach(([o, label], i) => {
      const col = dash.colors[i % dash.colors.length];
      const isF = o === focus;
      series.push({ office: o, label, col, kind: ctyName ? 'state' : 'main', focus: isF, pts: sw.filter((r) => officeOf(r.office) === o && r.margin != null).sort((a, b) => a.year - b.year).map((r) => ({ year: r.year, m: r.margin, race: r.race, label: r.margin_label })) });
      if (ctyName) series.push({ office: o, label, col, kind: 'county', focus: isF, pts: cty.filter((r) => officeOf(r.office) === o).sort((a, b) => a.year - b.year).map((r) => ({ year: r.year, m: r.margin, race: r.race, label: r.margin_label })) });
    });
    const all = series.flatMap((s) => s.pts.map((d) => d.m));
    let lo = Math.min(0, d3.min(all) ?? 0), hi = Math.max(0, d3.max(all) ?? 0);
    const pad = (hi - lo) * 0.08 || 0.05; lo -= pad; hi += pad;
    const y = d3.scaleLinear([lo, hi], [H - 26, 10]).nice(6);
    const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', '100%').attr('role', 'img').attr('aria-label', 'Margin over time');
    const ticks = y.ticks(6), tg = svg.append('g');
    const tl = tg.selectAll('text').data(ticks).join('text').attr('x', 0).attr('y', (d) => y(d)).attr('dy', '0.32em').attr('fill', 'var(--color-fg-muted)').attr('font-size', 'var(--cds-font-size-caption)').text((d) => lab(d));
    let ml = 0; tl.each(function () { ml = Math.max(ml, this.getComputedTextLength()); });
    const left = ml + 8, right = 12, x = d3.scaleLinear([2000, 2026], [left, W - right]);
    tg.selectAll('line').data(ticks).join('line').attr('x1', left).attr('x2', W - right).attr('y1', (d) => y(d)).attr('y2', (d) => y(d)).attr('stroke', (d) => d === 0 ? 'var(--cds-chart-reference)' : 'var(--cds-chart-grid)');
    const xt = [2000, 2006, 2012, 2018, 2026];
    svg.append('g').selectAll('text').data(xt).join('text').attr('x', (d) => x(d)).attr('y', H - 6).attr('text-anchor', (d, i) => i === xt.length - 1 ? 'end' : 'middle').attr('fill', 'var(--color-fg-muted)').attr('font-size', 'var(--cds-font-size-caption)').text((d) => d);
    const line = d3.line().x((d) => x(d.year)).y((d) => y(d.m));
    const order = series.slice().sort((a, b) => a.focus - b.focus);
    for (const s of order) {
      const muted = !s.focus, dashd = s.kind === 'state';
      svg.append('path').datum(s.pts).attr('d', line).attr('fill', 'none').attr('stroke', muted ? 'var(--cds-chart-muted)' : s.col)
        .attr('stroke-width', muted ? 1.2 : dashd ? 1.5 : 2.2).attr('stroke-dasharray', dashd ? '4 3' : null).attr('stroke-linecap', 'round').attr('stroke-linejoin', 'round').attr('opacity', muted ? 0.7 : 1);
      if (!muted) svg.append('g').selectAll('circle').data(s.pts).join('circle').attr('cx', (d) => x(d.year)).attr('cy', (d) => y(d.m))
        .attr('r', (d) => d.race === p.race ? 5 : 3).attr('fill', (d) => d.race === p.race ? 'var(--color-panel)' : s.col).attr('stroke', s.col).attr('stroke-width', (d) => d.race === p.race ? 2.5 : 0);
    }
    const card = document.getElementById('trend-card'), tip = document.getElementById('trend-tip');
    const pts = series.filter((s) => s.focus).flatMap((s) => s.pts.map((d) => ({ ...d, s })));
    const rule = svg.append('line').attr('y1', 10).attr('y2', H - 26).attr('stroke', 'var(--cds-chart-axis)').attr('opacity', 0);
    svg.append('rect').attr('x', left).attr('y', 0).attr('width', W - left - right).attr('height', H).attr('fill', 'transparent')
      .on('mousemove', (event) => {
        if (!pts.length) return;
        const [mx] = d3.pointer(event);
        const yrs = [...new Set(pts.map((d) => d.year))].sort((a, b) => a - b);
        const yrN = yrs.reduce((a, b) => Math.abs(x(b) - mx) < Math.abs(x(a) - mx) ? b : a);
        rule.attr('x1', x(yrN)).attr('x2', x(yrN)).attr('opacity', 1);
        tip.replaceChildren(); const t = document.createElement('div'); t.className = 't'; t.textContent = String(yrN); tip.append(t);
        for (const d of pts.filter((d) => d.year === yrN)) LX.tipLine(tip, d.s.col, (d.s.kind === 'county' ? ctyName : 'Statewide') + ' · ' + d.race.slice(5), d.label);
        LX.placeTip(tip, card, event);
      })
      .on('mouseleave', () => { tip.style.display = 'none'; rule.attr('opacity', 0); })
      .on('click', (event) => {
        if (!pts.length) return;
        const [mx] = d3.pointer(event);
        const near = pts.reduce((a, b) => Math.abs(x(b.year) - mx) < Math.abs(x(a.year) - mx) ? b : a);
        dash.setParams({ race: near.race });
      });
    const flabel = (OFFICES.find((o) => o[0] === focus) || [focus, focus])[1];
    document.getElementById('trend-title').textContent = ctyName ? `${ctyName} County vs statewide: ${flabel}` : `Statewide margin over time: ${flabel}`;
    document.getElementById('trend-note').textContent = (ctyName ? 'Solid: this county. Dashed: statewide. ' : '') + 'Republican minus Democratic share. Grey lines are the other offices. Click a point to open that race.';
    clearBtn.hidden = !ctyName; clearBtn.textContent = ctyName ? `${ctyName} ×` : '';
    const lg = document.getElementById('trend-legend'); lg.replaceChildren();
    const g = document.createElement('span'); g.className = 'grp'; const s = document.createElement('i'); s.className = 'sw'; s.style.background = dash.colors[OFFICES.findIndex((o) => o[0] === focus) % dash.colors.length]; s.style.height = '3px'; s.style.verticalAlign = '3px'; g.append(s, document.createTextNode(flabel)); lg.append(g);
    const g2 = document.createElement('span'); g2.className = 'grp'; const s2 = document.createElement('i'); s2.className = 'sw'; s2.style.background = 'var(--cds-chart-muted)'; s2.style.height = '3px'; s2.style.verticalAlign = '3px'; g2.append(s2, document.createTextNode('Other offices')); lg.append(g2);
  }

  function drawTable(p, S, rows, cands, pending) {
    document.getElementById('table-title').textContent = `All 254 counties · ${p.race}`;
    document.querySelectorAll('#county-table th[data-field^="c"]').forEach((th) => {
      const f = th.dataset.field; if (!/^c\d_pct$/.test(f)) return;
      const c = cands[Number(f[1]) - 1];
      th.style.display = c ? '' : 'none';
      const b = th.querySelector('button'); b.dataset.label = c ? `${c.candidate} (${c.party})` : '—';
    });
    if (/^c\d_pct$/.test(sortKey) && !cands[Number(sortKey[1]) - 1]) { sortKey = 'total_votes'; sortDir = -1; }
    let list = rows.filter((r) => !query || r.county.toLowerCase().includes(query));
    list = list.slice().sort((a, b) => {
      const va = a[sortKey], vb = b[sortKey];
      if (va == null && vb == null) return 0; if (va == null) return 1; if (vb == null) return -1;
      return (typeof va === 'string' ? va.localeCompare(vb) : va - vb) * sortDir;
    });
    document.getElementById('count').textContent = pending ? 'No counties have reported yet.' : query ? `${list.length} of ${rows.length}` : '';
    document.querySelectorAll('#county-table th').forEach((th) => {
      const b = th.querySelector('button'), k = b.dataset.sort;
      th.setAttribute('aria-sort', k === sortKey ? (sortDir > 0 ? 'ascending' : 'descending') : 'none');
      b.textContent = (b.dataset.label || b.textContent.replace(/ [▲▼]$/, '')) + (k === sortKey ? (sortDir > 0 ? ' ▲' : ' ▼') : '');
      if (!b.dataset.label) b.dataset.label = b.textContent.replace(/ [▲▼]$/, '');
    });
    const maxAbs = d3.max(rows, (r) => Math.abs(r.margin || 0)) || 1;
    const RED = css('--lx-rep'), BLUE = css('--lx-dem');
    const tb = document.querySelector('#county-table tbody');
    tb.replaceChildren(...list.map((r) => {
      const tr = document.createElement('tr'); tr.dataset.key = enc(r.race) + ',' + enc(r.county_fips); tr.dataset.fips = r.county_fips;
      if (r.county_fips === p.county) tr.className = 'sel';
      const td = (t, cls) => { const c = document.createElement('td'); c.textContent = t; if (cls) c.className = cls; tr.append(c); return c; };
      td(r.county);
      cands.forEach((c, i) => { const v = r['c' + (i + 1) + '_pct']; const cell = td(v == null ? '—' : pct(v), i >= 2 ? 'lx-hide-narrow' : ''); cell.style.color = partyCol(c.party); });
      const mc = td(r.margin_label, r.margin > 0 ? 'lx-r' : r.margin < 0 ? 'lx-d' : '');
      if (r.margin != null) { const bar = document.createElement('i'); bar.className = 'lx-bar'; bar.style.width = (Math.abs(r.margin) / maxAbs * 3.5).toFixed(2) + 'rem'; bar.style.background = r.margin > 0 ? RED : BLUE; bar.style.opacity = '.7'; mc.append(bar); }
      td(r.shift_label, r.shift == null ? '' : r.shift > 0 ? 'lx-r' : 'lx-d');
      td(r.reported ? fmt(r.total_votes) : '—', 'lx-hide-narrow');
      return tr;
    }));
  }

  dash.onData(draw);
})();
