/* National page: U.S. Senate, U.S. House and governor races, 2024 and 2026.
   Data: data/us_results.csv (2024 official results), data/live_2026.csv + live_status.json (2026, election night),
   data/us_seats.json (who held each seat before each election), data/us_hex.json (House tile layout),
   data/us_states_albers.json (state shapes). Params in the URL: tab, year, sel, q. */
(() => {
  const root = document.querySelector('.lx');
  const css = (n) => getComputedStyle(root).getPropertyValue(n).trim();
  const fmt = d3.format(','), pct = d3.format('.1%');
  const PARTY = { R: 'Republican', D: 'Democrat', I: 'Independent', L: 'Libertarian', G: 'Green', C: 'Constitution', O: 'Other', W: 'Write-in' };
  const PLURAL = { R: 'Republicans', D: 'Democrats', I: 'Independents' };
  const pcol = (p) => css({ R: '--lx-rep', D: '--lx-dem', I: '--lx-ind', L: '--lx-lib', G: '--lx-grn' }[p] || '--cds-chart-muted');
  const RAMP = {
    R: ['#fcd5d0', '#f09a8f', '#da5a4c', '#b02a1f', '#73110b'],
    D: ['#d3e1fb', '#93b4ef', '#5583dc', '#2a56b4', '#0f2d70'],
    I: ['#e6dbf4', '#c3a9e6', '#9c74d3', '#7446b3', '#4a2580'],
  };
  const BINS = [0.05, 0.1, 0.2, 0.4];
  const LEVEL = { senate: 'U.S. Senate', house: 'U.S. House', governor: 'Governor' };
  // states with their own page on this site: link from the race details
  const STATE_PAGE = { TX: '../tx.html', NC: '../nc/', GA: '../ga/', OH: '../oh/', WI: '../wi/' };
  const FIPS = { '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA', '08': 'CO', '09': 'CT', '10': 'DE', '11': 'DC', '12': 'FL', '13': 'GA', '15': 'HI', '16': 'ID', '17': 'IL', '18': 'IN', '19': 'IA', '20': 'KS', '21': 'KY', '22': 'LA', '23': 'ME', '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN', '28': 'MS', '29': 'MO', '30': 'MT', '31': 'NE', '32': 'NV', '33': 'NH', '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND', '39': 'OH', '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI', '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT', '50': 'VT', '51': 'VA', '53': 'WA', '54': 'WV', '55': 'WI', '56': 'WY' };
  // small eastern states get a clickable box beside the map
  const SMALL = ['VT', 'NH', 'MA', 'RI', 'CT', 'NJ', 'DE', 'MD'];
  // independents who caucus with Democrats (for seat counts and flips)
  const CAUCUS_D = /^(Bern(ie|ard) Sanders|Angus S?\.? ?King|Kyrsten Sinema|Joe Manchin)/;

  // ---------- params ----------
  const P = () => dash.params();
  const set = (o) => dash.setParams(o);

  // ---------- model ----------
  const seatOf = (S, level, year, race) => {
    if (level === 'house') return (S.house[year] || {})[race.key] || null;
    if (level === 'governor') return (S.governor[year] || {})[race.state] || null;
    const list = (S.senate[year] || {})[race.state] || [];
    const up = list.filter((s) => s.up);
    if (up.length < 2) return up[0] || null;
    // two seats up (Nebraska 2024): the special is the class 2 seat
    return race.seat === 'special' ? up.find((s) => s.class === 2) : up.find((s) => s.class !== 2) || up[0];
  };
  const caucus = (party, name) => (party === 'I' && CAUCUS_D.test(name || '') ? 'D' : party);
  const holderCaucus = (h) => (h ? (h.party === 'I' ? 'D' : h.party) : null);   // every independent holding a seat before 2026 caucused with Democrats

  function buildRaces(level, year, results, live, S) {
    const rows = year === 2024 ? results.filter((r) => r.level === level && r.year === '2024') : live.filter((r) => r.level === level);
    const byKey = new Map();
    for (const r of rows) {
      const key = level === 'house' ? `${r.state}-${String(r.district).padStart(2, '0')}` : r.state + (r.seat === 'special' && year === 2024 ? '-S' : '');
      if (!byKey.has(key)) byKey.set(key, { key, state: r.state, district: level === 'house' ? Number(r.district) : null, seat: r.seat, rows: [] });
      byKey.get(key).rows.push(r);
    }
    const races = [];
    for (const race of byKey.values()) {
      const cands = race.rows.map((r) => ({ name: r.candidate, party: r.party, votes: Number(r.votes) || 0, winner: r.winner === '1', unopposed: r.unopposed === '1', incumbent: r.incumbent === '1' }));
      const total = d3.sum(cands, (c) => c.votes);
      cands.forEach((c) => { c.share = total ? c.votes / total : null; });
      cands.sort((a, b) => b.votes - a.votes || b.winner - a.winner);
      const unopposed = cands.some((c) => c.unopposed);
      let status = year === 2024 ? 'final' : race.rows[0].status;
      const win = cands.find((c) => c.winner) || (year === 2024 ? cands[0] : null);
      const lead = total ? cands[0] : null;
      const top = win || lead;
      const R = d3.sum(cands.filter((c) => c.party === 'R'), (c) => c.votes), D = d3.sum(cands.filter((c) => c.party === 'D'), (c) => c.votes);
      const second = cands[1];
      const margin = total && second ? (cands[0].votes - second.votes) / total : null;
      const h = seatOf(S, level, year, race);
      const redrawn = level === 'house' && (S.redrawn[year] || []).includes(race.state);
      const wc = top ? caucus(top.party, top.name) : null;
      const hc = holderCaucus(h);
      const flip = !!(win && h && !redrawn && wc !== hc);
      const leadFlip = !!(!win && lead && h && !redrawn && wc !== hc);
      const rep = race.rows[0].reporting;
      const name = S.names[race.state] || race.state;
      const label = level === 'house' ? `${name} ${race.district === 0 ? 'at-large' : race.district}` : name + (race.seat === 'special' ? ' (special)' : '');
      const short = level === 'house' ? `${race.state}-${race.district === 0 ? 'AL' : race.district}` : race.state + (race.seat === 'special' ? ' special' : '');
      races.push({ ...race, level, year, cands, total, status, win, lead, top, margin, rd: total && (R || D) ? (R - D) / total : null, holder: h, redrawn,
        flip, leadFlip, wc, hc, unopposed, reporting: rep === '' || rep == null ? null : Number(rep), label, short });
    }
    races.sort((a, b) => d3.ascending(a.state, b.state) || d3.ascending(a.district, b.district) || d3.ascending(a.seat, b.seat));
    return races;
  }

  dash.calc('model', {
    inputs: ['results', 'live_2026', 'seats'],
    fn: (results, live, seats) => {
      const S = Array.isArray(seats) ? seats[0] : seats;
      const m = { S };
      for (const lv of ['senate', 'house', 'governor']) m[lv] = { 2024: buildRaces(lv, 2024, results, live, S), 2026: buildRaces(lv, 2026, results, live, S) };
      return [m];
    },
  });

  // ---------- seat totals ----------
  function tally(level, year, races, S) {
    const won = { R: 0, D: 0, I: 0 }, lead = { R: 0, D: 0, I: 0 }, notUp = { R: 0, D: 0, I: 0 };
    let undecided = 0, flipsTo = { R: 0, D: 0, I: 0 }, flipsFrom = { R: 0, D: 0, I: 0 };
    const add = (o, p) => { o[p === 'R' || p === 'D' ? p : 'I'] += 1; };
    for (const r of races) {
      if (r.win) {
        add(won, r.wc);
        if (r.flip) { add(flipsTo, r.wc); add(flipsFrom, r.hc); }
      } else { undecided += 1; if (r.lead && r.total) add(lead, r.wc); }
    }
    if (level === 'senate') {
      for (const list of Object.values(S.senate[year] || {})) for (const s of list) if (!s.up) add(notUp, holderCaucus(s));
    } else if (level === 'governor') {
      for (const g of Object.values(S.governor[year] || {})) if (!g.up) add(notUp, g.party);
    }
    const total = { R: won.R + notUp.R, D: won.D + notUp.D, I: won.I + notUp.I };
    // the chamber before the election: seat holders (vacant seats keep their last member's party)
    const before = { R: 0, D: 0, I: 0 };
    if (level === 'senate') for (const list of Object.values(S.senate[year] || {})) for (const s of list) add(before, holderCaucus(s));
    if (level === 'governor') for (const g of Object.values(S.governor[year] || {})) add(before, g.party);
    if (level === 'house') for (const h of Object.values(S.house[year] || {})) add(before, h.party);
    return { won, lead, notUp, total, undecided, flipsTo, flipsFrom, before, n: races.length };
  }
  const SIZE = { senate: 100, house: 435, governor: 50 };
  const MAJ = { senate: 51, house: 218, governor: 26 };

  // ---------- DOM helpers ----------
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const colorOf = (r) => {
    if (!r || !r.top || !r.total) return null;
    const side = r.wc === 'R' || r.wc === 'D' ? r.wc : 'I';
    const m = r.margin == null ? 1 : r.margin;
    return RAMP[side][d3.bisect(BINS, m)];
  };
  const fillOf = (r) => {
    if (!r) return css('--color-bg');                                  // no race
    if (r.unopposed && r.win) return RAMP[r.wc === 'R' || r.wc === 'D' ? r.wc : 'I'][4];
    if (!r.total) return css('--lx-pending');                          // not counted yet
    return colorOf(r);
  };
  const mshort = (r) => {
    if (!r.top) return '—';
    if (r.unopposed) return 'Unopposed';
    if (r.margin == null) return '—';
    return `${r.top.party === 'R' || r.top.party === 'D' ? r.top.party : r.top.party === 'I' ? 'I' : 'O'}+${(r.margin * 100).toFixed(1)}`;
  };
  const tz = (iso) => new Date(iso).toLocaleString('en-US', { timeZone: 'America/New_York', weekday: 'short', hour: 'numeric', minute: '2-digit', month: 'short', day: 'numeric' }) + ' ET';

  // ---------- tabs and pickers ----------
  document.querySelectorAll('.lx-tab').forEach((b) => b.addEventListener('click', () => set({ tab: b.dataset.tab, sel: null, q: null })));
  document.querySelectorAll('[data-year]').forEach((b) => b.addEventListener('click', () => set({ year: Number(b.dataset.year), sel: null })));
  $('race-search').addEventListener('input', (e) => set({ q: e.target.value || null }));
  $('clear-sel').addEventListener('click', () => set({ sel: null }));

  // ---------- tooltip ----------
  const tip = $('map-tip');
  const showTip = (event, r, stateName) => {
    tip.replaceChildren();
    const t = el('div', 't', r ? r.label + (r.level === 'house' ? '' : ' · ' + LEVEL[r.level]) : stateName + ' · no race');
    tip.append(t);
    if (r) {
      if (r.total) {
        for (const c of r.cands.slice(0, 3)) {
          const l = el('div', 'l'); const a = el('span'); const s = el('i', 'sw'); s.style.background = pcol(c.party); a.append(s, document.createTextNode(`${c.name} (${c.party})${c.winner ? ' ✓' : ''}`));
          l.append(a, el('span', null, c.share == null ? '' : pct(c.share))); tip.append(l);
        }
        if (r.year === 2026 && r.status !== 'final' && r.reporting != null) tip.append(el('div', 't', `${Math.round(r.reporting)}% of expected vote counted`));
      } else if (r.unopposed && r.win) {
        tip.append(el('div', 'l', `${r.win.name} (${r.win.party}) unopposed`));
      } else {
        const names = r.cands.filter((c) => c.party === 'R' || c.party === 'D' || c.incumbent).slice(0, 3).map((c) => `${c.name} (${c.party})`).join(' v ');
        tip.append(el('div', 'l', names || 'No candidates listed'));
        tip.append(el('div', 't', 'Not counted yet'));
      }
      if (r.holder) tip.append(el('div', 't', (r.year === 2026 ? 'Now held by ' : 'Held by ') + `${r.holder.name} (${r.holder.party})` + (r.holder.vacant ? ', seat vacant' : '')));
      if (r.flip) tip.append(el('div', 't', `Flip: ${PLURAL[r.wc] || r.wc} gain`));
      if (r.redrawn) tip.append(el('div', 't', 'New district map this year'));
    } else if (stateName) {
      tip.append(el('div', 't', 'Not on the ballot this year'));
    }
    const card = tip.parentElement, rc = card.getBoundingClientRect();
    tip.style.display = 'block';
    let x = event.clientX - rc.left + 14, y = event.clientY - rc.top + 14;
    if (x + tip.offsetWidth > rc.width - 4) x = event.clientX - rc.left - tip.offsetWidth - 14;
    if (y + tip.offsetHeight > rc.height - 4) y = event.clientY - rc.top - tip.offsetHeight - 14;
    tip.style.left = Math.max(4, x) + 'px'; tip.style.top = Math.max(4, y) + 'px';
  };
  const hideTip = () => { tip.style.display = 'none'; };

  // ---------- zoom: pinch or Ctrl/⌘ + scroll to zoom, drag to pan once zoomed, +/−/reset buttons (as on the state pages) ----------
  function holder(id) {
    const box = $('map');
    let h = document.getElementById(id);
    if (!h) { h = el('div', 'lx-maphold'); h.id = id; box.append(h); }
    for (const c of box.querySelectorAll('.lx-maphold')) c.hidden = c !== h;
    return h;
  }
  function zoomable(hold, svg, vb, onZoom) {
    const node = svg.node();
    if (node._zm) { node._zm.onZoom = onZoom; return node._zm; }
    const [X0, Y0, W, H] = vb;
    const layer = svg.append('g').attr('class', 'lx-zl');
    let t = d3.zoomIdentity;
    const api = { layer, k: () => t.k, onZoom };
    const hint = el('div', 'lx-zoomhint', /Mac|iPhone|iPad/.test(navigator.platform) ? 'Use ⌘ + scroll to zoom the map' : 'Use Ctrl + scroll to zoom the map');
    let hintT = null;
    const zoom = d3.zoom().scaleExtent([1, 10]).extent([[X0, Y0], [X0 + W, Y0 + H]]).translateExtent([[X0, Y0], [X0 + W, Y0 + H]]).clickDistance(4)
      .filter((e) => {
        if (e.type === 'wheel') {
          if (e.ctrlKey || e.metaKey) return true;
          hint.classList.add('on'); clearTimeout(hintT); hintT = setTimeout(() => hint.classList.remove('on'), 1200); return false;
        }
        if (e.type === 'touchstart') return e.touches.length > 1 || t.k > 1.01;
        return !e.button && (t.k > 1.01 || e.type === 'dblclick');
      })
      .on('zoom', (e) => { t = e.transform; place(); });
    const place = () => {
      layer.attr('transform', t);
      svg.style('touch-action', t.k > 1.01 ? 'none' : 'pan-y').style('cursor', t.k > 1.01 ? 'grab' : null);
      reset.hidden = t.k <= 1.01;
      if (api.onZoom) api.onZoom(t.k);
    };
    svg.call(zoom).on('dblclick.zoom', null);
    hold.style.position = 'relative';
    const ctl = el('div', 'lx-zoomctl');
    const btn = (txt, aria, fn) => { const b = el('button', null, txt); b.type = 'button'; b.setAttribute('aria-label', aria); b.addEventListener('click', fn); ctl.append(b); return b; };
    btn('+', 'Zoom in', () => svg.transition().duration(250).call(zoom.scaleBy, 2));
    btn('−', 'Zoom out', () => svg.transition().duration(250).call(zoom.scaleBy, 0.5));
    const reset = btn('⟲', 'Reset zoom', () => svg.transition().duration(300).call(zoom.transform, d3.zoomIdentity));
    hold.append(ctl, hint);
    node._zm = api;
    place();
    return api;
  }

  // ---------- state map (Senate, governor) ----------
  let stateGeo = null;
  function drawStateMap(races, sel) {
    const topo = dash.data('states');
    const box = holder('map-states');
    if (topo.status !== 'ok') { if (topo.status === 'error') box.textContent = 'Map failed to load'; return; }
    const T = Array.isArray(topo.data) ? topo.data[0] : topo.data;
    if (!stateGeo) stateGeo = topojson.feature(T, T.objects.states).features.filter((f) => FIPS[f.id] && FIPS[f.id] !== 'DC');
    const byState = d3.group(races, (r) => r.state);
    const main = (st) => { const g = byState.get(st); return g ? g.find((r) => r.seat !== 'special') || g[0] : null; };
    const W = 1010, H = 610, path = d3.geoPath();
    const svg = d3.select(box).selectAll('svg').data([0]).join('svg').attr('viewBox', `-30 0 ${W} ${H}`).attr('role', 'img')
      .attr('aria-label', 'Map of the states, colored by the winner or leader of each race');
    const zm = zoomable(box, svg, [-30, 0, W, H], null);
    zm.onZoom = (k) => g.selectAll('circle.flip').attr('r', 4.5 / k).attr('stroke-width', 1.2 / k);
    const g = zm.layer.selectAll('g.states').data([0]).join('g').attr('class', 'states');
    g.selectAll('path').data(stateGeo, (f) => f.id).join('path')
      .attr('d', path)
      .attr('class', (f) => 'st' + (byState.has(FIPS[f.id]) ? ' has' : '') + (sel && sel.startsWith(FIPS[f.id]) ? ' sel' : ''))
      .attr('fill', (f) => fillOf(main(FIPS[f.id])))
      .attr('tabindex', (f) => (byState.has(FIPS[f.id]) ? 0 : null))
      .on('mousemove', (e, f) => showTip(e, main(FIPS[f.id]), dash.data('model').data[0].S.names[FIPS[f.id]]))
      .on('mouseleave', hideTip)
      .on('click', (e, f) => { const r = main(FIPS[f.id]); if (r) set({ sel: r.key }); })
      .on('keydown', (e, f) => { if (e.key === 'Enter') { const r = main(FIPS[f.id]); if (r) set({ sel: r.key }); } });
    // flip markers: a small dot at each flipped state's center
    const flips = stateGeo.filter((f) => { const r = main(FIPS[f.id]); return r && (r.flip || r.leadFlip); });
    g.selectAll('circle.flip').data(flips, (f) => f.id).join('circle').attr('class', 'flip')
      .attr('cx', (f) => path.centroid(f)[0] + (FIPS[f.id] === 'FL' ? 18 : FIPS[f.id] === 'LA' ? -8 : FIPS[f.id] === 'MI' ? 10 : 0))
      .attr('cy', (f) => path.centroid(f)[1] + (FIPS[f.id] === 'MI' ? 18 : 0))
      .attr('r', 4.5).attr('fill', '#fff').attr('stroke', css('--color-fg')).attr('stroke-width', 1.2)
      .attr('opacity', (f) => (main(FIPS[f.id]).flip ? 1 : 0.55)).attr('pointer-events', 'none');
    // two races in one state (Nebraska 2024): half-and-half label under the state
    // boxes for small eastern states
    const sb = g.selectAll('g.small').data(SMALL).join((en) => {
      const gg = en.append('g').attr('class', 'small');
      gg.append('rect').attr('width', 34).attr('height', 22).attr('rx', 3);
      gg.append('text').attr('x', 17).attr('y', 15).attr('text-anchor', 'middle');
      return gg;
    });
    sb.attr('transform', (d, i) => `translate(${930},${170 + i * 28})`)
      .classed('sel', (d) => sel && sel.startsWith(d))
      .on('mousemove', (e, d) => showTip(e, main(d), dash.data('model').data[0].S.names[d]))
      .on('mouseleave', hideTip)
      .on('click', (e, d) => { const r = main(d); if (r) set({ sel: r.key }); });
    sb.select('rect').attr('fill', (d) => fillOf(main(d))).attr('stroke', (d) => (main(d) ? css('--color-fg-muted') : css('--color-border-line')));
    zm.onZoom(zm.k());
    sb.select('text').text((d) => d).attr('fill', (d) => { const r = main(d); return r && (r.total || r.unopposed) && (r.margin == null || r.margin >= 0.1) ? '#fff' : css('--color-fg'); });
    svg.selectAll('text.small-note').data([0]).join('text').attr('class', 'small-note').attr('x', 947).attr('y', 160).attr('text-anchor', 'middle').text('');
  }

  // ---------- House tile map ----------
  function drawHexMap(races, sel, hexL) {
    const box = holder('map-hex');
    const R = 10, w = Math.sqrt(3) * R;   // pointy-top hexes; layout units: x = col + .5*(row&1), y = row*sqrt(3)/2 (width 1)
    const sc = w;                          // one layout unit = one hex width
    // states are pulled slightly apart (hexL.offsets, per state, in hex widths; us/tools/hex_separate.py)
    const OFF = hexL.offsets || {};
    const raw = (c, r, st) => { const o = OFF[st] || [0, 0]; return [c + 0.5 * (r & 1) + o[0], r * (Math.sqrt(3) / 2) + o[1]]; };
    const all = Object.entries(hexL.hexes).map(([k, [c, r]]) => raw(c, r, k.slice(0, 2)));
    const mnx = d3.min(all, (p) => p[0]), mny = d3.min(all, (p) => p[1]);
    const pos = (c, r, st) => { const [x, y] = raw(c, r, st); return [(x - mnx) * sc + w, (y - mny) * sc + R + 2]; };
    const corner = (i) => { const a = Math.PI / 180 * (60 * i - 30); return [R * Math.cos(a), R * Math.sin(a)]; };
    const hexPath = 'M' + d3.range(6).map((i) => corner(i).map((v) => v.toFixed(2)).join(',')).join('L') + 'Z';
    const byKey = new Map(races.map((r) => [r.key, r]));
    const items = Object.entries(hexL.hexes).map(([k, [c, r]]) => ({ k, st: k.slice(0, 2), c, r, xy: pos(c, r, k.slice(0, 2)) }));
    const W = d3.max(items, (d) => d.xy[0]) + w, H = d3.max(items, (d) => d.xy[1]) + R + 2;
    const svg = d3.select(box).selectAll('svg').data([0]).join('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img')
      .attr('aria-label', 'Tile map of the 435 House districts, one hexagon each, grouped by state');
    const g0 = zoomable(box, svg, [0, 0, W, H], null);
    const g = g0.layer.selectAll('g.hexes').data([0]).join('g').attr('class', 'hexes');
    g.selectAll('path.hx').data(items, (d) => d.k).join('path').attr('class', (d) => 'hx' + (sel === d.k ? ' sel' : ''))
      .attr('d', hexPath).attr('transform', (d) => `translate(${d.xy[0]},${d.xy[1]})`)
      .attr('fill', (d) => fillOf(byKey.get(d.k)))
      .attr('tabindex', 0)
      .on('mousemove', (e, d) => { showTip(e, byKey.get(d.k)); hov.attr('display', null).attr('transform', `translate(${d.xy[0]},${d.xy[1]})`); })
      .on('mouseleave', () => { hideTip(); hov.attr('display', 'none'); })
      .on('click', (e, d) => set({ sel: d.k }))
      .on('keydown', (e, d) => { if (e.key === 'Enter') set({ sel: d.k }); });
    // flip markers
    const fl = items.filter((d) => { const r = byKey.get(d.k); return r && (r.flip || r.leadFlip); });
    g.selectAll('circle.flip').data(fl, (d) => d.k).join('circle').attr('class', 'flip').attr('cx', (d) => d.xy[0]).attr('cy', (d) => d.xy[1]).attr('r', 2.6)
      .attr('fill', '#fff').attr('stroke', css('--color-fg')).attr('stroke-width', 0.8).attr('opacity', (d) => (byKey.get(d.k).flip ? 1 : 0.55)).attr('pointer-events', 'none');
    // state borders: hex edges whose neighbor belongs to another state
    const at = new Map(items.map((d) => [d.c + ',' + d.r, d.st]));
    const segs = [];
    const axial = (c, r) => [c - (r - (r & 1)) / 2, r];
    const offset = (q, r) => [q + (r - (r & 1)) / 2, r];
    const DIRS = [[1, 0, 0], [1, -1, -60], [0, -1, -120], [-1, 0, 180], [-1, 1, 120], [0, 1, 60]];
    for (const d of items) {
      const [q, r] = axial(d.c, d.r);
      for (const [dq, dr, ang] of DIRS) {
        const [nc, nr] = offset(q + dq, r + dr);
        if (at.get(nc + ',' + nr) === d.st) continue;
        const a1 = Math.PI / 180 * (ang - 30), a2 = Math.PI / 180 * (ang + 30);
        segs.push(`M${(d.xy[0] + R * Math.cos(a1)).toFixed(1)},${(d.xy[1] + R * Math.sin(a1)).toFixed(1)}L${(d.xy[0] + R * Math.cos(a2)).toFixed(1)},${(d.xy[1] + R * Math.sin(a2)).toFixed(1)}`);
      }
    }
    g.selectAll('path.border').data(hexL.offsets ? [] : [0]).join('path').attr('class', 'border').attr('d', segs.join(''));
    // state labels beside the blob's middle
    const lab = Object.entries(hexL.labels).map(([st, [x, y]]) => { const o = OFF[st] || [0, 0]; return { st, x: (x + o[0] - mnx) * sc + w, y: (y + o[1] - mny) * sc + R + 2 }; });
    const stl = g.selectAll('text.stl').data(lab, (d) => d.st).join('text').attr('class', 'stl').attr('x', (d) => d.x).text((d) => d.st);
    // district labels ("TX 7"), shown once zoomed in; dark text on light fills, white on dark
    const light = (c) => { const x = d3.color(c); if (!x) return true; const { r, g: gg, b } = x.rgb(); return 0.299 * r + 0.587 * gg + 0.114 * b > 150; };
    const dl = g.selectAll('text.dl').data(items, (d) => d.k).join('text').attr('class', 'dl').attr('x', (d) => d.xy[0])
      .text((d) => `${d.st} ${Number(d.k.slice(3)) || 'AL'}`).attr('fill', (d) => (light(fillOf(byKey.get(d.k))) ? '#1f1e1c' : '#fff'));
    // outlines for the selected and hovered hex, drawn above everything so neighbors can't cover them
    const sItem = items.find((d) => d.k === sel);
    g.selectAll('path.hsel').data(sItem ? [sItem] : []).join('path').attr('class', 'hsel').attr('d', hexPath).attr('transform', (d) => `translate(${d.xy[0]},${d.xy[1]})`);
    const hov = g.selectAll('path.hov').data([0]).join('path').attr('class', 'hov').attr('d', hexPath).attr('display', 'none');
    g.selectAll('path.border').raise();
    g.selectAll('circle.flip').raise();
    stl.raise(); dl.raise();
    g.selectAll('path.hsel').raise(); hov.raise();
    g0.onZoom = (k) => {
      const near = k >= 2.5;
      // labels grow with zoom, but less than the map does
      stl.attr('display', near ? 'none' : null).attr('font-size', 7.5 / Math.sqrt(k)).attr('stroke-width', 2.2 / Math.sqrt(k)).attr('y', (d) => d.y + 2.6 / Math.sqrt(k));
      dl.attr('display', near ? null : 'none').attr('font-size', 4.4).attr('y', (d) => d.xy[1] + 1.6);
      g.selectAll('circle.flip').attr('display', near ? 'none' : null);
    };
    g0.onZoom(g0.k());
  }

  // ---------- balance bar ----------
  function drawBalance(level, year, t) {
    const box = $('balance');
    const N = SIZE[level], maj = MAJ[level];
    const parts = level === 'house'
      ? [['D', t.won.D, 'won', 1], ['D', t.lead.D, 'leading', 0.6], ['U', t.undecided - t.lead.D - t.lead.R - t.lead.I, 'not yet counted', 1], ['I', t.won.I + t.lead.I, 'independent', 0.7], ['R', t.lead.R, 'leading', 0.6], ['R', t.won.R, 'won', 1]]
      : [['D', t.notUp.D + t.notUp.I, 'not up', 0.3], ['D', t.won.D, 'won', 1], ['D', t.lead.D, 'leading', 0.6], ['U', t.undecided - t.lead.D - t.lead.R - t.lead.I, 'not yet counted', 1],
        ['I', t.won.I + t.lead.I, 'independent', 0.8], ['R', t.lead.R, 'leading', 0.6], ['R', t.won.R, 'won', 1], ['R', t.notUp.R, 'not up', 0.3]];
    const Wd = 1000, Hd = 40;
    const x = d3.scaleLinear().domain([0, N]).range([0, Wd]);
    let acc = 0;
    const segs = parts.filter((p) => p[1] > 0).map((p) => { const s = { party: p[0], n: p[1], what: p[2], op: p[3], x0: acc }; acc += p[1]; return s; });
    const svg = d3.select(box).selectAll('svg').data([0]).join('svg').attr('viewBox', `0 0 ${Wd} ${Hd + 22}`).attr('preserveAspectRatio', 'none');
    svg.selectAll('rect.seg').data(segs).join('rect').attr('class', 'seg').attr('x', (d) => x(d.x0)).attr('width', (d) => Math.max(0, x(d.n) - x(0)))
      .attr('y', 0).attr('height', Hd).attr('fill', (d) => (d.party === 'U' ? css('--lx-pending') : pcol(d.party))).attr('fill-opacity', (d) => d.op)
      .attr('stroke', css('--color-panel')).attr('stroke-width', 1)
      .selectAll('title').data((d) => [d]).join('title').text((d) => `${d.n} ${d.party === 'U' ? 'races not yet counted' : (PLURAL[d.party] || '') + ' — ' + d.what}`);
    const half = level === 'governor' ? null : maj;
    svg.selectAll('line.maj').data(half ? [half] : []).join('line').attr('class', 'maj').attr('x1', (d) => x(N / 2)).attr('x2', (d) => x(N / 2))
      .attr('y1', -2).attr('y2', Hd + 4).attr('stroke', css('--color-fg')).attr('stroke-width', 2).attr('vector-effect', 'non-scaling-stroke');
    svg.selectAll('text.maj').data(half ? [half] : []).join('text').attr('class', 'maj').attr('x', x(N / 2)).attr('y', Hd + 17).attr('text-anchor', 'middle')
      .text((d) => `${d} for majority`);
    // numbers under the bar
    const dTot = t.total.D, rTot = t.total.R;
    $('bal-d').textContent = dTot; $('bal-r').textContent = rTot;
    $('bal-d-sub').textContent = level === 'house' ? (t.lead.D ? `+${t.lead.D} leading` : '') : `${t.notUp.D + t.notUp.I} not up, ${t.won.D} won` + (t.lead.D ? `, ${t.lead.D} leading` : '');
    $('bal-r-sub').textContent = level === 'house' ? (t.lead.R ? `+${t.lead.R} leading` : '') : `${t.notUp.R} not up, ${t.won.R} won` + (t.lead.R ? `, ${t.lead.R} leading` : '');
    $('bal-d-label').textContent = level === 'senate' ? 'Democrats + independents' : 'Democrats';
    const so = t.undecided ? ' · secured so far' : '';
    $('bal-d-label').textContent += so; $('bal-r-label').textContent = 'Republicans' + so;
    $('bal-mid').textContent = t.undecided ? `${t.undecided} ${t.undecided === 1 ? 'race' : 'races'} not decided` + (t.won.I && level !== 'senate' ? '' : '') : '';
    const legend = $('bal-legend');
    legend.replaceChildren();
    const item = (color, op, text) => { const s = el('span', 'grp'); const sw = el('i', 'sw'); sw.style.background = color; sw.style.opacity = op; s.append(sw, document.createTextNode(text)); legend.append(s); };
    item(pcol('D'), 1, 'won'); if (level !== 'house') item(pcol('D'), 0.3, 'seat not up'); if (year === 2026) { item(pcol('D'), 0.6, 'leading'); item(css('--lx-pending'), 1, 'not decided'); }
    if (t.won.I || t.lead.I) item(pcol('I'), 0.8, 'independent (caucus not declared)');
  }

  // ---------- details panel ----------
  function drawDetails(r, races, level, year) {
    const box = $('details');
    box.replaceChildren();
    $('clear-sel').hidden = !r;
    if (!r) {
      // no race chosen: the closest races (election night: the closest with votes counted)
      const close = races.filter((x) => x.total && x.margin != null && !x.unopposed).sort((a, b) => a.margin - b.margin).slice(0, 8);
      $('details-title').textContent = close.length ? (year === 2026 && races.some((x) => x.status !== 'final') ? 'Closest races so far' : 'Closest races') : 'Race details';
      if (!close.length) {
        const flipOdds = races.length;
        box.append(el('p', 'lx-note', year === 2026 ? `Choose a ${level === 'house' ? 'district' : 'state'} on the map to see its candidates. Results appear here after polls close on Nov. 3; ${flipOdds} races are on the ballot.` : 'Choose a race on the map.'));
        return;
      }
      const ol = el('ol', 'lx-close');
      for (const x of close) {
        const li = el('li'); const b = el('button', 'lx-linkbtn'); b.type = 'button';
        b.append(el('span', null, x.label), el('span', 'lx-close-m ' + (x.wc === 'R' ? 'lx-r' : x.wc === 'D' ? 'lx-d' : 'lx-i'), mshort(x) + (x.flip ? ' · flip' : x.leadFlip ? ' · flipping' : '')));
        b.addEventListener('click', () => set({ sel: x.key })); li.append(b); ol.append(li);
      }
      box.append(ol);
      return;
    }
    $('details-title').textContent = r.label + (level === 'house' ? '' : ' · ' + LEVEL[level]);
    const st = el('p', 'lx-note');
    let line = '';
    if (r.unopposed && r.win) line = `${r.win.name} is unopposed.`;
    else if (year === 2024 || r.status === 'final') line = r.win ? `${r.win.name} (${r.win.party}) won` + (r.margin != null ? ` by ${(r.margin * 100).toFixed(1)} points.` : '.') : 'Result final.';
    else if (r.status === 'counting') line = `${r.lead.name} (${r.lead.party}) leads by ${(r.margin * 100).toFixed(1)} points` + (r.reporting != null ? ` with about ${Math.round(r.reporting)}% of the expected vote counted.` : '.') + ' Not called yet.';
    else line = 'No votes counted yet.';
    st.textContent = line; box.append(st);
    const cards = el('div', 'lx-cands lx-cands-tight');
    const shown = r.cands.filter((c, i) => i < 4 || c.winner);
    for (const c of shown) {
      const cd = el('div', 'lx-card lx-cand' + (c.winner ? ' win' : ''));
      const ini = el('div', 'lx-initials', initials(c.name)); ini.style.background = pcol(c.party); ini.setAttribute('aria-hidden', 'true');
      const body = el('div', 'lx-cand-body');
      body.append(el('div', 'lx-cand-name', c.name));
      const pp = el('div', 'lx-cand-party', PARTY[c.party] || c.party);
      if (c.winner) pp.append(el('span', 'lx-badge', c.unopposed ? 'Unopposed' : year === 2024 ? 'Won' : 'Projected'));
      if (c.incumbent || (r.holder && !r.holder.vacant && sameName(r.holder.name, c.name))) pp.append(el('span', 'lx-badge lx-badge-muted', 'Incumbent'));
      body.append(pp);
      body.append(el('div', 'lx-cand-pct', c.share == null ? (r.total ? '0%' : '—') : pct(c.share)));
      body.append(el('div', 'lx-cand-votes', r.total ? fmt(c.votes) + ' votes' : c.unopposed ? 'No vote needed' : ''));
      const bar = el('div', 'lx-cand-bar'); const bi = el('i'); bi.style.width = ((c.share || 0) * 100).toFixed(1) + '%'; bi.style.background = pcol(c.party); bar.append(bi); body.append(bar);
      cd.append(ini, body); cards.append(cd);
    }
    box.append(cards);
    if (r.cands.length > shown.length) {
      const rest = r.cands.slice(shown.length);
      box.append(el('p', 'lx-note', `Also on the ballot: ${rest.map((c) => `${c.name} (${c.party}${r.total ? ', ' + fmt(c.votes) : ''})`).join('; ')}.`));
    }
    const facts = [];
    if (r.holder) facts.push((year === 2026 ? 'Seat now held by ' : 'Seat held before the election by ') + `${r.holder.name} (${r.holder.party})` + (r.holder.vacant ? ' — vacant since that member left' : '') + '.');
    if (r.flip) facts.push(`${PLURAL[r.wc] || 'The winner'} flipped this seat.`);
    else if (r.leadFlip) facts.push(`If the lead holds, ${PLURAL[r.wc] || 'the leader'} would flip this seat.`);
    if (r.state === 'GA' && level !== 'house' && r.top && r.top.share != null && r.top.share < 0.5 && r.total) facts.push(`No candidate has a majority${r.status === 'final' || year === 2024 ? '' : ' yet'}; Georgia holds a runoff between the top two on Dec. 1 if it stays that way.`);
    if (r.redrawn) facts.push(`${r.state} used a new congressional map in ${year}, so the district isn't directly comparable with ${year - 2}.`);
    if (level === 'senate' && year === 2024 && r.state === 'CA') facts.push('California also held a same-day contest for the last weeks of the term (Schiff won both); it is not shown.');
    if (level === 'house' && year === 2024 && r.key === 'ME-02') facts.push('Maine uses ranked-choice voting; votes shown are the final round, as reported in the official statistics.');
    if (level === 'house' && year === 2024 && r.key === 'AK-00') facts.push('Alaska uses ranked-choice voting; votes shown are first choices.');
    if (STATE_PAGE[r.state]) {
      const p = el('p', 'lx-note'); const a = el('a', null, `More ${S().names[r.state]} results, by county and district →`); a.href = STATE_PAGE[r.state]; p.append(a); box.append(...facts.map((f) => el('p', 'lx-note', f)), p);
    } else box.append(...facts.map((f) => el('p', 'lx-note', f)));
  }
  const initials = (name) => { const w = String(name).replace(/["“”(].*?["“”)]/g, '').split(/\s+/).filter((x) => /^[A-ZÁÉÍÓÚÑ]/.test(x) && !/^(Jr|Sr|II|III|IV)\.?,?$/.test(x)); return ((w[0] || name)[0] + (w.length > 1 ? w[w.length - 1][0] : '')).toUpperCase(); };
  const lastName = (n) => String(n).replace(/,?\s+(Jr|Sr|II|III|IV)\.?$/i, '').trim().split(/\s+/).pop().toLowerCase();
  const sameName = (a, b) => lastName(a) === lastName(b);
  const S = () => dash.data('model').data[0].S;

  // ---------- table ----------
  let sortBy = 'race', sortDir = 1;
  document.querySelectorAll('#race-table th button').forEach((b) => b.addEventListener('click', () => {
    if (sortBy === b.dataset.k) sortDir = -sortDir; else { sortBy = b.dataset.k; sortDir = 1; }
    draw();
  }));
  function drawTable(races, sel, q, year) {
    const tb = $('race-tbody');
    const qq = (q || '').trim().toLowerCase();
    let list = races.filter((r) => !qq || (r.label + ' ' + r.short + ' ' + r.cands.map((c) => c.name).join(' ')).toLowerCase().includes(qq));
    const key = {
      race: (r) => (S().names[r.state] || r.state) + String(r.district == null ? '' : r.district).padStart(2, '0') + r.seat,
      winner: (r) => (r.top ? r.top.name : '~'),
      margin: (r) => (r.unopposed ? 2 : r.margin == null ? 3 : (r.wc === 'D' ? -r.margin : r.margin)),
      change: (r) => (r.flip ? 0 : r.leadFlip ? 1 : 2),
      counted: (r) => (r.reporting == null ? -1 : r.reporting),
    }[sortBy];
    list.sort((a, b) => sortDir * d3.ascending(key(a), key(b)));
    $('race-count').textContent = `${list.length} of ${races.length} races`;
    $('col-counted').hidden = year !== 2026;
    d3.select(tb).selectAll('tr').data(list, (r) => r.key).join('tr')
      .classed('sel', (r) => r.key === sel)
      .on('click', (e, r) => set({ sel: r.key === sel ? null : r.key }))
      .each(function (r) {
        const tr = this; tr.replaceChildren();
        const td = (t, cls) => { const c = el('td', cls, t); tr.append(c); return c; };
        td(r.label);
        const w = td('', 'lx-cand-cell');
        if (r.top) { const s = el('span', r.wc === 'R' ? 'lx-r' : r.wc === 'D' ? 'lx-d' : 'lx-i', `${r.top.name} (${r.top.party})`); w.append(s); if (!r.win && r.total) w.append(document.createTextNode(' leads')); }
        else w.textContent = r.cands.length ? 'Not counted yet' : '—';
        td(mshort(r));
        td(r.flip ? `${r.wc} flip` : r.leadFlip ? `${r.wc} leading flip` : r.redrawn ? 'New map' : r.win ? 'Hold' : r.hc ? `${r.hc} seat now` : '');
        if (year === 2026) td(r.unopposed ? '' : r.status === 'final' ? 'Called' : r.reporting == null ? '' : Math.round(r.reporting) + '%');
      });
  }

  // ---------- live banner ----------
  function drawLive(year) {
    const box = $('live');
    const ls = dash.data('live_status');
    const s = ls.status === 'ok' ? (Array.isArray(ls.data) ? ls.data[0] : ls.data) : null;
    box.hidden = year !== 2026 || !s;
    if (box.hidden) return;
    box.replaceChildren();
    const dot = el('span', 'lx-live-dot' + (s.phase === 'counting' ? ' on' : ''));
    let txt;
    if (s.phase === 'pre-election') txt = 'Election Day is Tuesday, Nov. 3. Results appear here as polls close (first closings 6 pm ET) and update every 5 minutes through the night.';
    else if (s.phase === 'counting') txt = `Counting · ${s.called} of ${s.races} races called · updated ${tz(s.updated_at)}`;
    else txt = `All ${s.races} races called · updated ${tz(s.updated_at)} · unofficial until certified`;
    box.append(dot, el('span', null, txt), el('span', 'lx-live-src', 'Source: ' + (s.source || '')));
  }

  // ---------- takeaway ----------
  function takeaway(level, year, races, t) {
    const n = races.length, decided = races.filter((r) => r.win).length;
    const what = { senate: 'Senate', house: 'House', governor: 'governor' }[level];
    const net = (p) => t.flipsTo[p] - t.flipsFrom[p];
    if (year === 2024) {
      const gainer = net('R') > 0 ? 'R' : net('D') > 0 ? 'D' : null;
      const g = gainer ? ` and gained ${Math.abs(net(gainer))} ${Math.abs(net(gainer)) === 1 ? 'seat' : 'seats'}` : ', with no seats changing parties';
      const flipped = races.filter((r) => r.flip).map((r) => S().names[r.state]);
      const list = flipped.length > 1 ? flipped.slice(0, -1).join(', ') + ' and ' + flipped[flipped.length - 1] : flipped[0];
      if (level === 'senate') return `<b>${t.total.R > t.total.D ? 'Republicans' : 'Democrats'} won the Senate majority, ${Math.max(t.total.R, t.total.D)}–${Math.min(t.total.R, t.total.D)}.</b> Of the ${n} Senate races in 2024, Republicans won ${t.won.R}${g}${flipped.length ? ` (flipping ${list})` : ''}; Democrats and independents who caucus with them won ${t.won.D + t.won.I}.`;
      if (level === 'house') return `<b>Republicans kept the House, ${t.won.R}–${t.won.D}.</b> They won ${t.won.R} of the 435 districts, ${t.before.R - t.won.R > 0 ? `${t.before.R - t.won.R} fewer than they held before the election` : 'about as many as before'}. Seats are shaded by margin; a white dot marks a seat that changed parties (not shown in the five states with new maps in 2024).`;
      return `<b>Republicans won ${t.won.R} of the ${n} governor races in 2024</b>${g}; Democrats won ${t.won.D}. After the election Republicans held ${t.total.R} governorships and Democrats ${t.total.D}.`;
    }
    if (!races.some((r) => r.total)) {
      if (level === 'senate') return `<b>${n} Senate seats are on the ballot in 2026</b> (33 regular races plus specials in Florida and Ohio). Republicans hold ${t.notUp.R + races.filter((r) => r.hc === 'R').length} seats now; Democrats need a net gain of 4 seats for a majority (51), since Vice President Vance breaks ties.`;
      if (level === 'house') return `<b>All 435 House seats are on the ballot.</b> Republicans hold ${t.before.R} seats now (including vacancies, by the last member's party); 218 is a majority. Nine states vote under new maps drawn since 2024.`;
      return `<b>${n} governorships are up in 2026.</b> Republicans hold ${t.before.R} governorships now and Democrats ${t.before.D}; ${races.filter((r) => r.hc === 'R').length} of the seats up are held by Republicans.`;
    }
    const lead = t.total.R + t.lead.R > t.total.D + t.lead.D ? 'R' : 'D';
    const ctl = level === 'governor' ? '' : (t.total[lead] >= MAJ[level] ? `<b>${PLURAL[lead]} will control the ${what}</b> (${t.total[lead]} seats). ` : '');
    const fl = ['R', 'D', 'I'].filter((p) => t.flipsTo[p]).map((p) => `${PLURAL[p]} have flipped ${t.flipsTo[p]}`).join('; ');
    return `${ctl}${decided} of ${n} ${what} races called. ${PLURAL.R} have ${t.total.R}${level === 'house' ? '' : ' seats'} (leading in ${t.lead.R} more), ${level === 'senate' ? 'Democrats and allied independents' : 'Democrats'} ${t.total.D} (leading in ${t.lead.D} more). ${fl ? fl + '.' : ''}`;
  }

  // ---------- KPIs ----------
  function drawKpis(level, year, races, t) {
    const set1 = (id, v, sub) => { $(id).querySelector('.lx-kpi-value').textContent = v; $(id).querySelector('.lx-kpi-value').classList.remove('dash-skeleton'); $(id).querySelector('.lx-kpi-sub').textContent = sub || ''; };
    const name = { senate: 'Senate seats', house: 'House seats', governor: 'Governorships' }[level];
    const sf = year === 2026 && t.undecided ? ' secured so far' : '';
    $('k1').querySelector('.lx-kpi-label').textContent = `Republican ${name.toLowerCase()}` + sf;
    $('k2').querySelector('.lx-kpi-label').textContent = (level === 'senate' ? 'Democratic + independent seats' : `Democratic ${name.toLowerCase()}`) + sf;
    const delta = (p) => { const d = t.total[p] - t.before[p]; return year === 2026 && t.undecided ? `${t.before[p]} before the election` : d ? `${d > 0 ? '+' : '−'}${Math.abs(d)} from ${t.before[p]} before the election` : `no change from before the election`; };
    set1('k1', t.total.R, delta('R'));
    set1('k2', t.total.D + (level === 'senate' ? 0 : 0), delta('D'));
    const flips = races.filter((r) => r.flip).length;
    $('k3').querySelector('.lx-kpi-label').textContent = 'Seats that changed parties';
    set1('k3', year === 2026 && !races.some((r) => r.win && !r.unopposed) ? '—' : flips,
      ['R', 'D', 'I'].filter((p) => t.flipsTo[p]).map((p) => `${t.flipsTo[p]} to ${PLURAL[p]}`).join(', ') + (level === 'house' ? ` · ${S().redrawn[year].length} states with new maps not counted` : ''));
    if (level === 'house') {
      $('k4').querySelector('.lx-kpi-label').textContent = 'National House vote (R − D)';
      const R = d3.sum(races, (r) => d3.sum(r.cands.filter((c) => c.party === 'R'), (c) => c.votes)), D = d3.sum(races, (r) => d3.sum(r.cands.filter((c) => c.party === 'D'), (c) => c.votes)), T = d3.sum(races, (r) => r.total);
      set1('k4', T ? `${R >= D ? 'R' : 'D'}+${(Math.abs(R - D) / T * 100).toFixed(1)}` : '—', T ? `${fmt(R)} R · ${fmt(D)} D votes${year === 2026 ? ' counted so far' : ''}; unopposed seats add no votes` : 'not counted yet');
    } else {
      $('k4').querySelector('.lx-kpi-label').textContent = year === 2026 ? 'Races called' : 'Closest race';
      if (year === 2026) set1('k4', `${races.filter((r) => r.win).length} of ${races.length}`, `${races.filter((r) => r.status === 'counting').length} counting`);
      else { const c = races.filter((r) => r.margin != null).sort((a, b) => a.margin - b.margin)[0]; set1('k4', c ? c.short : '—', c ? `${c.win.name} by ${(c.margin * 100).toFixed(1)} points` : ''); }
    }
  }

  // ---------- legend under the map ----------
  function drawLegend(level, year) {
    const lg = $('map-legend'); lg.replaceChildren();
    const ramp = (side, label) => { const s = el('span', 'grp'); for (const c of RAMP[side]) { const sw = el('i', 'sw'); sw.style.background = c; s.append(sw); } s.append(document.createTextNode(' ' + label)); lg.append(s); };
    ramp('D', 'Democrat'); ramp('R', 'Republican');
    lg.append(el('span', null, 'light → dark: margin under 5 · 5–10 · 10–20 · 20–40 · 40+ points'));
    const sw = (color, text, dot) => { const s = el('span', 'grp'); const i = el('i', 'sw' + (dot ? ' dot' : '')); i.style.background = color; s.append(i, document.createTextNode(text)); lg.append(s); };
    if (year === 2026) sw(css('--lx-pending'), 'not counted yet');
    if (level !== 'house') sw(css('--color-bg'), 'no race');
    sw('#fff', level === 'house' ? 'seat changed parties' : 'state changed parties', true);
  }

  // ---------- main draw ----------
  function draw() {
    const p = P();
    const level = ['senate', 'house', 'governor'].includes(p.tab) ? p.tab : 'senate';
    const year = Number(p.year) === 2024 ? 2024 : 2026;
    document.querySelectorAll('.lx-tab').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === level)));
    document.querySelectorAll('[data-year]').forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.year) === year)));
    $('map-title').textContent = level === 'house' ? `${year} U.S. House results, one hexagon per district` : `${year} ${LEVEL[level]} results by state`;
    $('map').classList.toggle('lx-hexmap', level === 'house');
    if ($('race-search').value !== (p.q || '')) $('race-search').value = p.q || '';
    $('race-search').placeholder = level === 'house' ? 'Search districts or candidates' : 'Search states or candidates';
    drawLive(year);
    const md = dash.data('model');
    if (md.status !== 'ok') {
      if (md.status === 'error') ['takeaway', 'map', 'details'].forEach((id) => { $(id).classList.remove('dash-skeleton'); $(id).textContent = 'Failed to load'; });
      return;
    }
    const M = md.data[0];
    const races = M[level][year];
    const sel = p.sel && races.some((r) => r.key === p.sel) ? p.sel : null;
    const t = tally(level, year, races, M.S);
    $('takeaway').innerHTML = takeaway(level, year, races, t);
    $('takeaway').classList.remove('dash-skeleton');
    drawKpis(level, year, races, t);
    drawBalance(level, year, t);
    if (level === 'house') {
      const hx = dash.data('hex');
      if (hx.status === 'ok') drawHexMap(races, sel, Array.isArray(hx.data) ? hx.data[0] : hx.data);
    } else drawStateMap(races, sel);
    $('map').classList.remove('dash-skeleton');
    drawLegend(level, year);
    drawDetails(races.find((r) => r.key === sel) || null, races, level, year);
    drawTable(races, sel, p.q, year);
    const foot = { senate: $('foot-senate'), house: $('foot-house'), governor: $('foot-governor') };
    for (const [k, e] of Object.entries(foot)) e.hidden = k !== level;
  }
  dash.onData(draw);
})();
