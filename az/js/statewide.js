(() => {
  const LX = window.LX;
  const { css, fmt, pct, enc, PARTY, partyCol } = LX;
  const lab = (m) => (m == null || isNaN(m)) ? '—' : Math.abs(m) < 0.0005 ? 'Even' : (m > 0 ? 'R+' : 'D+') + (Math.abs(m) * 100).toFixed(1);
  const OFFICES = [['President', 'President'], ['Senate', 'U.S. Senate'], ['Governor', 'Governor'], ['Secretary of State', 'Secretary of State'],
    ['Attorney General', 'Attorney General'], ['Treasurer', 'State Treasurer'], ['Superintendent of Public Instruction', 'Superintendent of Public Instruction'],
    ['Mine Inspector', 'State Mine Inspector'], ['Corporation Commission', 'Corporation Commission']];
  // Corporation Commission seats are elected at large: voters pick two or three, and the top vote-getters win
  const SEATS = { 'Corporation Commission': { 2016: 3, 2018: 2, 2020: 3, 2022: 2, 2024: 3, 2026: 2 } };
  const seatsOf = (race) => ((SEATS[race.slice(5)] || {})[Number(race.slice(0, 4))]) || 1;
  const NUM = ['', 'one', 'two', 'three', 'four'];
  const COURTS = ['Supreme Court'];
  // office group for the menus and the chart: runoffs and the 2020 special Senate election join their office; every PSC seat is one office
  const officeOf = (o) => { o = o.replace(/ runoff$/, '').replace(/ \(special\)$/, ''); return o.startsWith('PSC,') ? 'Public Service Commission' : COURTS.find((c) => o.startsWith(c + ',')) || o; };
  const isRunoff = (o) => / runoff$/.test(o);
  const OFFICE_NAME = { President: 'presidential', Governor: 'governor', Senate: 'U.S. Senate', 'Senate (special)': 'special U.S. Senate', 'Lt. Governor': 'lieutenant governor',
    'Attorney General': 'attorney general', 'Secretary of State': 'secretary of state', 'Agriculture Commissioner': 'agriculture commissioner',
    'Insurance Commissioner': 'insurance commissioner', 'Labor Commissioner': 'labor commissioner', 'School Superintendent': 'state school superintendent',
    Auditor: 'state auditor', Treasurer: 'state treasurer', 'Superintendent of Public Instruction': 'superintendent of public instruction',
    'Mine Inspector': 'state mine inspector', 'Corporation Commission': 'Corporation Commission' };
  const officeName = (o) => { const b = o.replace(/ runoff$/, ''); return OFFICE_NAME[b] || (b.startsWith('PSC,') ? 'Public Service Commission ' + b.slice(5) : COURTS.some((c) => b.startsWith(c + ',')) ? 'Arizona ' + b.replace(', ', ' (') + ')' : b); };
  // "the 2018 secretary of state race" / "the 2018 secretary of state runoff"
  const raceName = (year, o) => `${year} ${officeName(o)} ${isRunoff(o) ? 'runoff' : 'race'}`;
  const seatLabel = (o) => o.replace(/ runoff$/, '').replace(/^(Supreme Court|Court of Appeals), /, '').replace(/^PSC, /, '');
  const RUNOFF_DATE = { 2018: 'Dec. 4', 2021: 'Jan. 5', 2022: 'Dec. 6', 2026: 'Dec. 1' };
  const COURT_DATE = { 2016: 'May 24', 2018: 'May 22', 2020: 'June 9', 2022: 'May 24', 2024: 'May 21', 2026: 'May 19' };
  const yearLabel = (year, o) => {
    if (isRunoff(o)) return `${year} runoff (${RUNOFF_DATE[year] || ''})` + (o.startsWith('PSC,') ? ' · ' + seatLabel(o) : o.includes('(special)') ? ' · special' : '');
    if (COURTS.some((c) => o.startsWith(c + ','))) return `${year} · ${seatLabel(o)}`;
    return String(year) + (o === 'Senate (special)' ? ' · special' : '') + (seatsOf(year + ' ' + o) > 1 ? ` · ${seatsOf(year + ' ' + o)} seats` : '');
  };
  // county results the official canvass itself records in error; shown uncolored with a note (none found for Arizona)
  const FLAGS = {};

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
      // previous race for the same office
      // both Senate seats are one series and every PSC seat is one series; a runoff is compared with the general election it followed
      const off = (o) => { o = o.replace(/ \(special\)$/, ''); return o.indexOf('PSC,') === 0 ? 'PSC' : o; };
      // only races with both a Republican and a Democrat on the ballot are compared
      const hasR = new Set(all.filter((r) => r.party === 'R').map((r) => r.race)), hasD = new Set(all.filter((r) => r.party === 'D').map((r) => r.race));
      const seq = new Map();
      const runoffs = new Set();
      for (const r of rows) { if (!hasR.has(r.race) || !hasD.has(r.race)) continue; if (/ runoff$/.test(r.office)) { runoffs.add(r.race + '|' + r.year + '|' + r.office); continue; } const k = off(r.office); if (!seq.has(k)) seq.set(k, new Map()); seq.get(k).set(r.race, r.year); }
      const prevRace = new Map();
      for (const [, races] of seq) {
        const list = [...races.entries()].sort((a, b) => a[1] - b[1] || a[0].length - b[0].length);
        // the previous race is the latest one in an earlier year (two PSC seats or both Senate seats can be on one ballot); same seat preferred
        list.forEach(([race, yr]) => {
          const earlier = list.filter(([, y]) => y < yr);
          if (!earlier.length) { prevRace.set(race, null); return; }
          const lastYear = earlier[earlier.length - 1][1], cands = earlier.filter(([, y]) => y === lastYear);
          prevRace.set(race, (cands.find(([r]) => r.slice(5) === race.slice(5)) || cands[0])[0]);
        });
      }
      for (const k of runoffs) {
        const [race, y, o] = k.split('|'), g = o.replace(/ runoff$/, '');
        const gen = [Number(y), Number(y) - 1].map((yy) => yy + ' ' + g).find((rr) => hasR.has(rr) && hasD.has(rr));
        prevRace.set(race, gen || null);
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
    description: 'Each race summed over all 15 counties: leader, vote shares, margin, shift from the previous race for the office, counties carried and counties reporting.',
    inputs: ['by_county'],
    fn: (by_county) => {
      const lab = (m) => (m == null || isNaN(m)) ? '—' : Math.abs(m) < 0.0005 ? 'Even' : (m > 0 ? 'R+' : 'D+') + (Math.abs(m) * 100).toFixed(1);
      const g = new Map();
      for (const c of by_county) {
        let o = g.get(c.race);
        if (!o) { o = { race: c.race, year: c.year, office: c.office, status: c.status, prev_race: c.prev_race, rep_votes: 0, dem_votes: 0, other_votes: 0, total_votes: 0,
          counties_rep: 0, counties_dem: 0, counties_other: 0, counties_reporting: 0, counties_complete: 0, prec_rep: 0, prec_tot: 0 }; g.set(c.race, o); }
        o.rep_votes += c.rep_votes; o.dem_votes += c.dem_votes; o.other_votes += c.other_votes; o.total_votes += c.total_votes;
        if (c.reported) { o.counties_reporting++; if (c.winner_party === 'R') o.counties_rep++; else if (c.winner_party === 'D') o.counties_dem++; else o.counties_other++; }
        if (c.reporting != null && c.reporting_total && c.reporting >= c.reporting_total) o.counties_complete++;
        if (c.reporting != null) o.prec_rep += c.reporting;
        if (c.reporting_total != null) o.prec_tot += c.reporting_total;
      }
      const rows = [...g.values()].map((o) => {
        const t = o.total_votes, rep = t > 0, margin = rep ? (o.rep_votes - o.dem_votes) / t : null;
        return { race: o.race, year: o.year, office: o.office, status: o.status, prev_race: o.prev_race,
          rep_votes: o.rep_votes, dem_votes: o.dem_votes, other_votes: o.other_votes, total_votes: t,
          margin, margin_label: lab(margin), counties_rep: o.counties_rep, counties_dem: o.counties_dem, counties_other: o.counties_other,
          counties_reporting: o.counties_reporting, counties_complete: o.counties_complete, precincts_reporting_pct: o.prec_tot ? o.prec_rep / o.prec_tot : null };
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
    description: 'Each race\'s ballot candidates ranked by statewide votes (write-ins excluded), with share of all votes cast; the top four are kept (twice the number of seats for the Corporation Commission). "winner" is set only once a count is final.',
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
        // Corporation Commission: two or three seats, so show more candidates and mark every winner
        const SEATS = { 'Corporation Commission': { 2016: 3, 2018: 2, 2020: 3, 2022: 2, 2024: 3, 2026: 2 } };
        const n = ((SEATS[race.slice(5)] || {})[Number(race.slice(0, 4))]) || 1;
        [...o.cand.entries()].sort((a, b) => b[1].votes - a[1].votes || a[0].localeCompare(b[0])).slice(0, Math.max(4, 2 * n)).forEach(([candidate, c], i) => {
          rows.push({ race, rank: i + 1, candidate, party: c.party, votes: c.votes, pct: o.total ? c.votes / o.total : null, status: o.status, seats: n, winner: o.status === 'final' && i < n && o.total > 0 });
        });
      }
      return rows;
    },
  });

  const lead0 = (C, rows) => `${C[0].candidate} carried ${rows.filter((r) => r.winner_name === C[0].candidate).length}, ${C[1] ? C[1].candidate : 'others'} ${rows.filter((r) => r.reported && r.winner_name !== C[0].candidate).length}`;
  // winner of another race, from the candidate list
  const C2name = (race) => { const c = (dash.data('candidates_statewide').data || []).find((r) => r.race === race && r.rank === 1); return c ? c.candidate : ''; };
  // ---------- page ----------
  const params = () => { const p = dash.params(); return { race: p.race || '2026 Governor', view: p.view || 'result', county: p.county ? String(p.county).padStart(5, '0') : null }; };
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
      yearLabel: yearLabel(r.year, r.office) }));
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
    // the Reporting view only applies to the live 2026 count; older races fall back to Winner & margin
    const repBtn = document.querySelector('[data-view="reporting"]'); if (repBtn) repBtn.hidden = year !== 2026;
    if (p.view === 'reporting' && year !== 2026) p.view = 'result';
    document.querySelectorAll('[data-view]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.view === p.view)));
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
    if (pending) {
      add(`The ${raceName(year, office)} is on the ballot ${isRunoff(office) ? 'Tuesday, Dec. 1, 2026' : LX.ELECTION_2026}. `);
      add(C.length ? `${C.length} candidates are listed below; results will fill in as counties report.` : 'Candidates and results will appear here on election night.');
    } else {
      const lead = C[0];
      add(lead.candidate, true);
      // Arizona elects by plurality: no runoffs
      const runoffRace = null;
      if (false) {
        add(status === 'final' ? ` led the ${raceName(year, office)} with ` : ` leads the ${raceName(year, office)} with `);
        add(pct(lead.pct), true);
        if (status === 'final') { add(' of the vote, short of a majority, so the top two went to a runoff'); if (runoffRace) { add(', which '); add(C2name(runoffRace.race), true); add(` won (${runoffRace.margin_label})`); } add('.'); }
        else add(' of the vote; a candidate needs a majority to avoid a runoff on Dec. 1');
      } else if (seatsOf(p.race) > 1) {
        const n = seatsOf(p.race), W = C.slice(0, n);
        tk.replaceChildren();
        W.forEach((c, i) => { if (i) add(i === n - 1 ? ' and ' : ', '); add(c.candidate, true); add(` (${c.party})`); });
        add(status === 'final' ? ` won the ${NUM[n]} ${year} Corporation Commission seats` : ` lead for the ${NUM[n]} ${year} Corporation Commission seats`);
        add('. Voters could pick up to ' + NUM[n] + ' candidates; Republican candidates together drew ');
        add(pct(S.rep_votes / S.total_votes), true); add(' of the votes and Democrats '); add(pct(S.dem_votes / S.total_votes), true); add(` (party margin ${S.margin_label})`);
      } else if (S.rep_votes && S.dem_votes) {
        add(status === 'final' ? ` won the ${raceName(year, office)} by ` : ` leads the ${raceName(year, office)} by `);
        // very close races (under 0.1 point, e.g. 2020 Chief Justice by 401 votes) are stated in votes
        if (Math.abs(S.margin) < 0.001) add(fmt(Math.abs(S.rep_votes - S.dem_votes)) + (Math.abs(S.rep_votes - S.dem_votes) === 1 ? ' vote' : ' votes'), true);
        else { add(Math.abs(S.margin * 100).toFixed(1) + ' points', true); add(` (${S.margin_label})`); }
      } else {
        add(status === 'final' ? ` won the ${raceName(year, office)} with ` : ` leads the ${raceName(year, office)} with `);
        add(pct(lead.pct), true); add(' of the vote');
      }
      if (status === 'counting') { if (S.precincts_reporting_pct != null) { add(', with '); add(pct(S.precincts_reporting_pct).replace('.0%', '%'), true, 'precincts_reporting_pct'); add(' of precincts reporting.'); } else { add(', with '); add(String(S.counties_reporting), true, 'counties_reporting'); add(' of 15 counties reporting.'); } }
      else if (seatsOf(p.race) > 1) add('.');
      else { add(', carrying '); add(String(lead.party === 'R' ? S.counties_rep : lead.party === 'D' ? S.counties_dem : rows.filter((r) => r.winner_name === lead.candidate).length), true); add(' of 15 counties.'); }
      if (S.prev_race && S.shift != null) {
        add(isRunoff(office) ? ` Compared with the general election (${S.prev_race}), the statewide margin moved ` : ` Compared with ${S.prev_race}, the statewide margin moved `);
        if (Math.abs(S.shift) < 0.0005) { tk.lastChild.textContent = tk.lastChild.textContent.replace(/the statewide margin moved $/, 'the statewide margin was essentially unchanged.'); }
        else { add(S.shift_label, true, 'shift_label'); add(S.shift > 0 ? ' toward Republicans.' : ' toward Democrats.'); }
      } else if (S.margin != null && !S.dem_votes) add(' No Democrat was on the ballot.');
    }

    drawCands(C, status, pending, false, seatsOf(p.race));  // plurality wins: no runoff badge
    // KPIs
    const set = (sel, v) => document.querySelectorAll(sel).forEach((el) => { el.textContent = v; el.classList.remove('dash-skeleton'); });
    const twoParty = S && S.rep_votes > 0 && S.dem_votes > 0;
    set('#kpi-margin .lx-kpi-value', pending ? '—' : twoParty ? S.margin_label : 'n/a');
    document.querySelector('#kpi-margin .lx-kpi-value').style.color = pending || !twoParty ? '' : S.margin > 0 ? css('--lx-rep') : css('--lx-dem');
    set('#kpi-margin [data-field="shift_label"]', S ? S.shift_label : '—');
    document.getElementById('kpi-prev').textContent = S && S.prev_race ? ' vs ' + S.prev_race : '';
    set('#kpi-counties [data-field="counties_rep"]', pending || C.every((c) => c.party === 'N') ? '—' : String(S.counties_rep));
    set('#kpi-counties [data-field="counties_dem"]', pending || C.every((c) => c.party === 'N') ? '—' : String(S.counties_dem));
    document.querySelector('#kpi-counties .lx-kpi-value').classList.remove('dash-skeleton');
    const nonpartisan = C.length && C.every((c) => c.party === 'N');
    document.getElementById('kpi-counties-other').textContent = pending ? '' : nonpartisan ? `Nonpartisan: ${lead0(C, rows)}` : status === 'counting' ? (S.precincts_reporting_pct != null ? `${S.counties_complete} of 15 counties fully counted` : `${S.counties_reporting} of 15 counties reporting`) : S.counties_other ? `${S.counties_other} won by another candidate` : '';
    set('#kpi-votes .lx-kpi-value', pending ? '—' : fmt(S.total_votes));
    set('#kpi-votes [data-field="other_votes"]', pending ? '—' : fmt(S.other_votes));
    document.getElementById('kpi-other-pct').textContent = pending ? '' : ' (' + pct(S.other_votes / S.total_votes) + ')';
    if (nonpartisan) { set('#kpi-votes [data-field="other_votes"]', 'n/a (nonpartisan)'); document.getElementById('kpi-other-pct').textContent = ''; }
    document.getElementById('kpi-votes-label').textContent = status === 'counting' ? 'Votes counted so far' : 'Total votes cast in race';
    const T = null;   // turnout is not shown for Arizona yet

    drawMap(p, S, rows, shp.data, pending, T, year, nonpartisan ? C : null);
    if (p.view === 'turnout') drawTurnoutTrend(p, sw.data, bc.data, office, T); else drawTrend(p, sw.data, bc.data, office);
    drawTable(p, S, rows, C, pending, T, year);
  }

  function drawCands(list, status, pending, noMajority, seats = 1) {
    const box = document.getElementById('cand-cards'); box.classList.remove('dash-skeleton');
    const photos = window.LX_PHOTOS || {};
    let anyPhoto = false, anyInitials = false;
    if (!list.length) {
      box.replaceChildren(); const m = document.createElement('div'); m.className = 'lx-card lx-empty'; m.textContent = 'Candidates will appear here once the state publishes election-night returns.'; box.append(m);
      document.getElementById('photo-credit').textContent = ''; return;
    }
    box.replaceChildren(...list.map((c) => {
      const card = document.createElement('div'); card.className = 'lx-card lx-cand' + (c.rank <= seats && !pending ? ' win' : ''); card.id = 'cand-' + c.rank;
      const col = partyCol(c.party), where = 'race=' + enc(c.race) + '&rank=' + c.rank;
      if (photos[c.candidate]) anyPhoto = true; else anyInitials = true;
      card.append(LX.avatar(c.candidate, col));
      const body = document.createElement('div'); body.className = 'lx-cand-body';
      const nm = document.createElement('div'); nm.className = 'lx-cand-name'; nm.textContent = c.candidate;
      nm.setAttribute('data-source', 'candidates_statewide'); nm.setAttribute('data-field', 'candidate'); nm.setAttribute('data-where', where);
      const pt = document.createElement('div'); pt.className = 'lx-cand-party';
      const pn = document.createElement('span'); pn.textContent = (PARTY[c.party] || c.party) + ' (' + c.party + ')'; pn.style.color = col; pt.append(pn);
      const word = pending ? '' : noMajority ? (status === 'final' && c.rank <= 2 ? 'Runoff' : '') : LX.stateWord(status, c.rank <= seats);
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
    const pc = document.getElementById('photo-credit');
    LX.photoCredit(pc, list.map((c) => c.candidate));
    if (n < 4 && !pending) { pc.hidden = false; pc.prepend(document.createTextNode(`Only ${n} candidates were on the ballot in this race. `)); }
    if (seats > 1) { pc.hidden = false; pc.prepend(document.createTextNode(`${seats} seats were up; the top ${seats} vote-getters win. Shares are of all votes cast, and each voter could cast up to ${seats}. `)); }
  }

  const SHIFT_BINS = [-0.1, -0.05, -0.02, 0, 0.02, 0.05, 0.1];
  // Reporting view: share of a county's precincts counted. Early and mail votes are counted first, before any
  // precinct, so a county can have most of its votes in with 0 precincts reporting ("early votes only").
  const REP_RAMP = ['#fdecc8', '#fbd38d', '#f6ae4b', '#e08a1e', '#b4650b', '#7a3f04'];
  const REP_LABELS = ['Early votes only', 'Under 25%', '25–50%', '50–75%', '75–99%', 'All precincts'];
  const repShare = (r) => r.status === 'final' ? 1 : r.reporting_total ? Math.min(1, r.reporting / r.reporting_total) : null;
  const repBin = (r) => { const f = repShare(r); return f == null ? null : f >= 1 ? 5 : f <= 0 ? 0 : f < 0.25 ? 1 : f < 0.5 ? 2 : f < 0.75 ? 3 : 4; };
  const repColor = (r) => { const b = repBin(r); return b == null ? css('--cds-chart-muted') : REP_RAMP[b]; };
  function drawMap(p, S, rows, shapes, pending, T, year, NP) {
    const el = document.getElementById('map'); el.classList.remove('dash-skeleton');
    const R = LX.RAMP, byF = new Map(rows.map((r) => [r.county_fips, r])), muted = css('--cds-chart-muted');
    // nonpartisan races: purple for the statewide leader's counties, green for the runner-up's
    const resultColor = (r) => NP ? LX.rampColor(r.winner_name === NP[0].candidate ? 'I' : 'G', r.winner_lead)
      : r.winner_party !== 'R' && r.winner_party !== 'D' ? LX.rampColor('I', r.winner_lead) : LX.rampColor(r.margin >= 0 ? 'R' : 'D', r.margin);
    const shiftColor = (s) => s == null ? muted : [R.D[4], R.D[3], R.D[1], R.D[0], R.R[0], R.R[1], R.R[3], R.R[4]][d3.bisect(SHIFT_BINS, s)];
    const stillCounting = (r) => !!r && r.reported && r.status === 'counting' && r.reporting_total != null && r.reporting < r.reporting_total;
    const toOf = (f) => T ? T.county.get(year + '|' + f) : null;
    const fill = (r, f) => p.view === 'turnout' ? (toOf(f) ? LX.turnoutColor(toOf(f).turnout) : muted)
      : p.view === 'reporting' ? (r && r.reported ? repColor(r) : muted)
      : !r || !r.reported || FLAGS[p.race + '|' + r.county_fips] ? muted : p.view === 'shift' ? shiftColor(r.shift) : resultColor(r);
    let svg = d3.select(el).select('svg');
    if (svg.empty()) { el.replaceChildren(); svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${LX.MAP_W} ${LX.MAP_H}`).attr('width', '100%').attr('role', 'img').attr('aria-label', 'Map of Arizona counties'); const zm = LX.zoomMap(el, svg, LX.MAP_W, LX.MAP_H); zm.layer.append('g').attr('class', 'cties'); zm.layer.append('g').attr('class', 'selg'); }
    const card = document.getElementById('map-card'), tip = document.getElementById('map-tip');
    svg.select('g.cties').selectAll('path.cty').data(shapes, (d) => d.county_fips).join('path')
      .attr('class', 'cty').attr('d', (d) => d.path).attr('fill', (d) => fill(byF.get(d.county_fips), d.county_fips))
      .attr('fill-opacity', (d) => { const r = byF.get(d.county_fips); return stillCounting(r) && p.view !== 'turnout' && p.view !== 'reporting' ? 0.45 : 1; })
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
          if (r.status === 'counting' && r.reporting_total) LX.tipLine(tip, p.view === 'reporting' ? repColor(r) : null, 'Precincts reporting', `${r.reporting} of ${r.reporting_total} (${pct(r.reporting / r.reporting_total).replace('.0%', '%')})` + (r.reporting === 0 ? ' · early votes only' : ''));
          else if (p.view === 'reporting' && r.status === 'final') LX.tipLine(tip, repColor(r), 'Precincts reporting', 'All');
        }
        const to = toOf(d.county_fips);
        if (to) LX.tipLine(tip, p.view === 'turnout' ? LX.turnoutColor(to.turnout) : null, to.live ? 'Turnout so far' : 'Turnout', LX.turnoutText(to));
        LX.placeTip(tip, card, event);
      })
      .on('mouseleave', () => { tip.style.display = 'none'; })
      .on('click', (event, d) => dash.setParams({ county: p.county === d.county_fips ? null : d.county_fips }));
    svg.select('g.selg').selectAll('path').data(shapes.filter((d) => d.county_fips === p.county), (d) => d.county_fips).join('path')
      .attr('d', (d) => d.path).attr('fill', 'none').attr('stroke', css('--color-fg')).attr('stroke-width', 2.2).attr('pointer-events', 'none');
    document.getElementById('map-title').textContent = p.view === 'reporting' ? `${p.race}: precincts reporting` : p.view === 'turnout' ? `${year} turnout by county` : p.view === 'shift' ? `${p.race}: shift since ${S && S.prev_race ? S.prev_race : '—'}` : `${p.race}: county results`;
    document.getElementById('map-note').textContent = p.view === 'turnout' ? (T && T.county.has(year + '|TX') ? (T.county.get(year + '|TX').live ? 'Ballots counted so far as a share of registered voters. These rise through the night as counties report. ' : '') + `Share of registered voters who cast a ballot in the ${year} general election. It is the same for every race that year; some voters skip races further down the ballot. Click a county to follow it over time.` : year === 2026 ? 'Turnout fills in on election night as counties report ballots cast.' : `No turnout figures for ${year}.`)
      : p.view === 'reporting' ? (pending ? 'No county has reported yet. Counties fill in as results arrive on election night.' : 'Share of each county\'s voting precincts counted so far. Counties release early and mail votes first, before any precinct, so a county marked "early votes only" may already have most of its votes in. Click a county to follow it over time.')
      : pending ? 'No county has reported yet. Counties fill in as results arrive on election night.'
      : p.view === 'shift' ? (S.prev_race ? `Change in each county's R − D margin compared with ${S.prev_race}.` : 'No earlier race for this office in the data, so there is no shift to show.')
      : NP ? `Purple: counties ${NP[0].candidate} carried; green: ${NP[1] ? NP[1].candidate : 'other candidates'}. The darker the shade, the bigger the lead. Click a county to follow it over time.`
      : 'Red: Republican margin, blue: Democratic margin. The darker the shade, the bigger the margin. Click a county to follow it over time.';
    const lg = document.getElementById('legend'); lg.replaceChildren();
    const sw = (c, t) => { const g = document.createElement('span'); g.className = 'grp'; const s = document.createElement('i'); s.className = 'sw'; s.style.background = c; g.append(s, document.createTextNode(t)); lg.append(g); };
    if (p.view === 'turnout') {
      const g = document.createElement('span'); g.className = 'grp'; g.append(document.createTextNode('Turnout '));
      R.T.forEach((c) => { const s = document.createElement('i'); s.className = 'sw'; s.style.background = c; s.style.marginRight = '1px'; g.append(s); });
      lg.append(g); const n = document.createElement('span'); n.textContent = LX.TO_LEGEND; lg.append(n);
      if (shapes.some((d) => !toOf(d.county_fips))) sw(muted, 'No figure');
      return;
    }
    if (p.view === 'reporting') {
      const g = document.createElement('span'); g.className = 'grp'; g.append(document.createTextNode('Precincts reporting '));
      lg.append(g); REP_LABELS.forEach((t, i) => sw(REP_RAMP[i], t));
      if (shapes.some((d) => { const r = byF.get(d.county_fips); return !r || !r.reported; })) sw(muted, 'No results yet');
      return;
    }
    if (p.view === 'shift') {
      ['D >10', 'D 5–10', 'D 2–5', 'D 0–2', 'R 0–2', 'R 2–5', 'R 5–10', 'R >10'].forEach((t, i) => sw(shiftColor([-0.2, -0.07, -0.03, -0.01, 0.01, 0.03, 0.07, 0.2][i]), t));
      const n = document.createElement('span'); n.textContent = 'points of shift'; lg.append(n);
    } else {
      const parties = NP ? [['I', NP[0].candidate], ['G', NP[1] ? NP[1].candidate : 'Other']] : [['R', 'Republican'], ['D', 'Democrat']];
      if (!NP && S && S.counties_other) parties.push(['I', 'Other candidate']);
      for (const [pt, nm] of parties) {
        const g = document.createElement('span'); g.className = 'grp'; g.append(document.createTextNode(nm + ' '));
        R[pt].forEach((c) => { const s = document.createElement('i'); s.className = 'sw'; s.style.background = c; s.style.marginRight = '1px'; g.append(s); });
        lg.append(g);
      }
      const n = document.createElement('span'); n.textContent = NP ? 'lead, light → dark: <10 · 10–20 · 20–40 · 40–60 · 60+ pts' : 'margin, light → dark: <10 · 10–20 · 20–40 · 40–60 · 60+ pts'; lg.append(n);
    }
    if (p.view !== 'shift' && rows.some((r) => r.reported && r.status === 'counting' && r.reporting_total != null && r.reporting < r.reporting_total)) {
      const g = document.createElement('span'); g.className = 'grp'; const s = document.createElement('i'); s.className = 'sw'; s.style.background = R.R[2]; s.style.opacity = 0.45;
      const s2 = document.createElement('i'); s2.className = 'sw'; s2.style.background = R.D[2]; s2.style.opacity = 0.45; g.append(s, s2, document.createTextNode('Faded: still counting')); lg.append(g);
    }
    if (rows.length < 15 || rows.some((r) => !r.reported)) sw(muted, 'No results yet');
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
      series.push({ office: o, label, col, kind: ctyName ? 'state' : 'main', focus: isF, pts: sw.filter((r) => officeOf(r.office) === o && r.margin != null && r.rep_votes > 0 && r.dem_votes > 0 && (!isRunoff(r.office) || r.race === p.race)).sort((a, b) => a.year - b.year).map((r) => ({ year: r.year, m: r.margin, race: r.race, label: r.margin_label })) });
      if (ctyName) series.push({ office: o, label, col, kind: 'county', focus: isF, pts: cty.filter((r) => officeOf(r.office) === o && r.rep_votes > 0 && r.dem_votes > 0 && (!isRunoff(r.office) || r.race === p.race)).sort((a, b) => a.year - b.year).map((r) => ({ year: r.year, m: r.margin, race: r.race, label: r.margin_label })) });
    });
    const all = series.flatMap((s) => s.pts.map((d) => d.m));
    let lo = Math.min(0, d3.min(all) ?? 0), hi = Math.max(0, d3.max(all) ?? 0);
    const pad = (hi - lo) * 0.08 || 0.05; lo -= pad; hi += pad;
    const y = d3.scaleLinear([lo, hi], [H - 26, 10]).nice(6);
    const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', '100%').attr('role', 'img').attr('aria-label', 'Margin over time');
    const ticks = y.ticks(6), tg = svg.append('g');
    const tl = tg.selectAll('text').data(ticks).join('text').attr('x', 0).attr('y', (d) => y(d)).attr('dy', '0.32em').attr('fill', 'var(--color-fg-muted)').attr('font-size', 'var(--cds-font-size-caption)').text((d) => lab(d));
    let ml = 0; tl.each(function () { ml = Math.max(ml, this.getComputedTextLength()); });
    const left = ml + 8, right = 12, x = d3.scaleLinear([LX.YEAR0, LX.LIVE ? 2026 : LX.LAST_YEAR], [left, W - right]);
    tg.selectAll('line').data(ticks).join('line').attr('x1', left).attr('x2', W - right).attr('y1', (d) => y(d)).attr('y2', (d) => y(d)).attr('stroke', (d) => d === 0 ? 'var(--cds-chart-reference)' : 'var(--cds-chart-grid)');
    const END = LX.LIVE ? 2026 : LX.LAST_YEAR, xt = d3.range(LX.YEAR0, END + 1, END - LX.YEAR0 > 12 ? 6 : 2);
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

  function drawTurnoutTrend(p, sw, bc, office, T) {
    const el = document.getElementById('trend'); el.classList.remove('dash-skeleton'); el.replaceChildren();
    const W = Math.max(280, el.clientWidth), H = 260;
    const cty = p.county ? bc.find((r) => r.county_fips === p.county) : null, ctyName = cty ? cty.county : null;
    const years = [];
    for (let y = LX.YEAR0; y <= (LX.LIVE ? 2026 : LX.LAST_YEAR); y += 2) years.push(y);
    const ser = (u) => years.map((y) => ({ year: y, t: T && T.county.get(y + '|' + u) })).filter((d) => d.t).map((d) => ({ year: d.year, v: d.t.turnout, t: d.t }));
    const state = ser('TX'), county = ctyName ? ser(p.county) : [];
    const all = state.concat(county).map((d) => d.v);
    const y = d3.scaleLinear([Math.min(0.2, d3.min(all) ?? 0.2), Math.max(0.8, d3.max(all) ?? 0.8)], [H - 26, 10]).nice(6);
    const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', '100%').attr('role', 'img').attr('aria-label', 'Turnout over time');
    const ticks = y.ticks(6), tg = svg.append('g');
    const tl = tg.selectAll('text').data(ticks).join('text').attr('x', 0).attr('y', (d) => y(d)).attr('dy', '0.32em').attr('fill', 'var(--color-fg-muted)').attr('font-size', 'var(--cds-font-size-caption)').text((d) => d3.format('.0%')(d));
    let ml = 0; tl.each(function () { ml = Math.max(ml, this.getComputedTextLength()); });
    const left = ml + 8, right = 12, x = d3.scaleLinear([LX.YEAR0, LX.LIVE ? 2026 : LX.LAST_YEAR], [left, W - right]);
    tg.selectAll('line').data(ticks).join('line').attr('x1', left).attr('x2', W - right).attr('y1', (d) => y(d)).attr('y2', (d) => y(d)).attr('stroke', 'var(--cds-chart-grid)');
    const END = LX.LIVE ? 2026 : LX.LAST_YEAR, xt = d3.range(LX.YEAR0, END + 1, END - LX.YEAR0 > 12 ? 6 : 2);
    svg.append('g').selectAll('text').data(xt).join('text').attr('x', (d) => x(d)).attr('y', H - 6).attr('text-anchor', (d, i) => i === xt.length - 1 ? 'end' : 'middle').attr('fill', 'var(--color-fg-muted)').attr('font-size', 'var(--cds-font-size-caption)').text((d) => d);
    const COL = LX.RAMP.T[3], line = d3.line().x((d) => x(d.year)).y((d) => y(d.v));
    const curYear = Number(p.race.slice(0, 4));
    const GREY = 'var(--cds-chart-reference)';
    const draw1 = (pts, dashed, col = COL) => {
      svg.append('path').datum(pts).attr('d', line).attr('fill', 'none').attr('stroke', col).attr('stroke-width', dashed ? 1.5 : 2.2).attr('stroke-dasharray', dashed ? '4 3' : null).attr('stroke-linejoin', 'round');
      // presidential years filled, midterms hollow
      svg.append('g').selectAll('circle').data(pts).join('circle').attr('cx', (d) => x(d.year)).attr('cy', (d) => y(d.v)).attr('r', (d) => d.year === curYear ? 5 : 3.2)
        .attr('fill', (d) => d.year % 4 === 0 ? col : 'var(--color-panel)').attr('stroke', col).attr('stroke-width', (d) => d.year === curYear ? 2.5 : 1.5);
    };
    draw1(state, !!ctyName, ctyName ? GREY : COL); if (ctyName) draw1(county, false);
    const card = document.getElementById('trend-card'), tip = document.getElementById('trend-tip');
    const rule = svg.append('line').attr('y1', 10).attr('y2', H - 26).attr('stroke', 'var(--cds-chart-axis)').attr('opacity', 0);
    const yrs = [...new Set(state.concat(county).map((d) => d.year))].sort((a, b) => a - b);
    const near = (mx) => yrs.reduce((a, b) => Math.abs(x(b) - mx) < Math.abs(x(a) - mx) ? b : a);
    svg.append('rect').attr('x', left).attr('y', 0).attr('width', W - left - right).attr('height', H).attr('fill', 'transparent')
      .on('mousemove', (event) => {
        if (!yrs.length) return;
        const yr = near(d3.pointer(event)[0]); rule.attr('x1', x(yr)).attr('x2', x(yr)).attr('opacity', 1);
        tip.replaceChildren(); const t = document.createElement('div'); t.className = 't'; t.textContent = yr + (yr % 4 === 0 ? ' · presidential' : ' · midterm'); tip.append(t);
        const c = county.find((d) => d.year === yr), s = state.find((d) => d.year === yr);
        if (c) LX.tipLine(tip, COL, ctyName, LX.turnoutText(c.t));
        if (s) LX.tipLine(tip, ctyName ? GREY : COL, 'Statewide', LX.turnoutText(s.t));
        LX.placeTip(tip, card, event);
      })
      .on('mouseleave', () => { tip.style.display = 'none'; rule.attr('opacity', 0); })
      .on('click', (event) => {
        if (!yrs.length) return;
        const yr = near(d3.pointer(event)[0]), focus = officeOf(office);
        const r = sw.filter((s) => s.year === yr && officeOf(s.office) === focus)[0] || sw.find((s) => s.year === yr);
        if (r) dash.setParams({ race: r.race });
      });
    document.getElementById('trend-title').textContent = ctyName ? `Turnout over time: ${ctyName} County vs statewide` : 'Statewide turnout over time';
    document.getElementById('trend-note').textContent = (ctyName ? 'Green: this county. Grey dashed: statewide. ' : '') + 'Ballots cast as a share of registered voters, November general elections. Filled dots: presidential years; hollow: midterms. Click a point to open that year.';
    clearBtn.hidden = !ctyName; clearBtn.textContent = ctyName ? `${ctyName} ×` : '';
    const lg = document.getElementById('trend-legend'); lg.replaceChildren();
    for (const [fill, t] of [[COL, 'Presidential year'], ['var(--color-panel)', 'Midterm']]) { const g = document.createElement('span'); g.className = 'grp'; const s = document.createElement('i'); s.className = 'sw'; s.style.background = fill; s.style.border = '1.5px solid ' + COL; s.style.borderRadius = '50%'; g.append(s, document.createTextNode(t)); lg.append(g); }
  }

  function drawTable(p, S, rows, cands, pending, T, year) {
    rows = rows.map((r) => { const t = T ? T.county.get(year + '|' + r.county_fips) : null; return { ...r, turnout: t ? t.turnout : null, _to: t }; });
    document.getElementById('table-title').textContent = `All 15 counties · ${p.race}`;
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
