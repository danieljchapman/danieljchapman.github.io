(() => {
  const root = document.querySelector('.lx');
  const css = (n) => getComputedStyle(root).getPropertyValue(n).trim();
  const LX = (window.LX = {});
  LX.css = css;
  LX.fmt = d3.format(',');
  LX.pct = d3.format('.1%');
  LX.enc = (s) => String(s).replace(/%/g, '%25').replace(/&/g, '%26').replace(/=/g, '%3D');
  LX.PARTY = { R: 'Republican', D: 'Democrat', L: 'Libertarian', G: 'Green', C: 'Constitution', I: 'Independent', N: 'Nonpartisan', O: 'Other', W: 'Write-in' };
  LX.partyCol = (p) => css({ R: '--lx-rep', D: '--lx-dem', L: '--lx-lib', G: '--lx-grn', I: '--lx-ind', C: '--lx-ind', N: '--lx-ind' }[p] || '--cds-chart-muted');
  LX.RAMP = {
    R: ['#fcd5d0', '#f09a8f', '#da5a4c', '#b02a1f', '#73110b'],
    D: ['#d3e1fb', '#93b4ef', '#5583dc', '#2a56b4', '#0f2d70'],
    I: ['#e6dbf4', '#c3a9e6', '#9c74d3', '#7446b3', '#4a2580'],
    G: ['#d7efe0', '#a3d9b6', '#5fb784', '#2f8c58', '#145c33'],   // second candidate in a nonpartisan race
  };
  LX.BINS = [0.1, 0.2, 0.4, 0.6];
  LX.rampColor = (side, m) => LX.RAMP[side][d3.bisect(LX.BINS, Math.abs(m))];
  // turnout: ballots cast as a share of registered voters (one number per place and year, for every race on that ballot)
  LX.RAMP.T = ['#dcefe9', '#a6d8c8', '#62b49d', '#2e8a6f', '#0f5a45'];
  LX.TO_BINS = [0.35, 0.45, 0.55, 0.65];
  LX.TO_LEGEND = 'turnout, light → dark: <35% · 35–45 · 45–55 · 55–65 · 65%+';
  LX.turnoutColor = (t) => LX.RAMP.T[d3.bisect(LX.TO_BINS, t)];
  LX.short = (n) => n >= 1e7 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e6 ? (n / 1e6).toFixed(2) + 'M' : n >= 1e4 ? Math.round(n / 1e3) + 'K' : LX.fmt(n);
  LX.turnoutText = (o) => o ? `${LX.pct(o.turnout)} (${LX.fmt(o.ballots)} of ${LX.fmt(o.registered)})` : '—';
  // lookups: county '<year>|<fips>' (statewide is '<year>|TX'), district '<level>|<year>|<district>'; 2026 comes from the live state feed
  LX.turnout = () => {
    const tc = dash.data('turnout_county'), td = dash.data('turnout_district'), ls = dash.data('live_status');
    if (tc.status !== 'ok') return null;
    const key = [tc.data, td.status === 'ok' ? td.data : null, ls.status === 'ok' ? ls.data : null];
    if (LX._to && LX._to.key.every((k, i) => k === key[i])) return LX._to;
    const county = new Map(), district = new Map();
    const put = (m, k, r, b, extra) => { r = Number(r); b = Number(b); if (r > 0 && b >= 0) m.set(k, { registered: r, ballots: b, turnout: b / r, ...extra }); };
    const unit = (u) => { u = String(u); return /^\d+$/.test(u) ? u.padStart(5, '0') : u; };
    for (const r of tc.data) put(county, r.year + '|' + unit(r.unit), r.registered, r.ballots, { source: r.source });
    if (td.status === 'ok') for (const r of td.data) put(district, r.level + '|' + r.year + '|' + r.district, r.registered, r.ballots, { method: r.method });
    const s = ls.status === 'ok' ? (Array.isArray(ls.data) ? ls.data[0] : ls.data) || {} : {};
    const live = s.turnout && s.turnout.counties;
    if (live && s.phase !== 'pre-election') {
      let R = 0, B = 0;
      for (const [f, v] of Object.entries(live)) { put(county, '2026|' + unit(f), v[0], v[1], { live: true }); R += Number(v[0]) || 0; B += Number(v[1]) || 0; }
      if (R) put(county, '2026|TX', R, B, { live: true });
    }
    LX._to = { key, county, district };
    return LX._to;
  };
  LX.placeTip = (tip, card, event) => {
    const r = card.getBoundingClientRect();
    tip.style.display = 'block';
    let x = event.clientX - r.left + 14, y = event.clientY - r.top + 14;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    if (x + w > r.width - 4) x = event.clientX - r.left - w - 14;
    if (x < 4) x = 4;
    if (y + h > r.height - 4) y = event.clientY - r.top - h - 14;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  };
  LX.tipLine = (tip, color, name, value) => {
    const l = document.createElement('div'); l.className = 'l';
    const a = document.createElement('span');
    if (color) { const s = document.createElement('i'); s.className = 'sw'; s.style.background = color; a.append(s); }
    a.append(document.createTextNode(name));
    const b = document.createElement('span'); b.textContent = value;
    l.append(a, b); tip.append(l);
  };
  LX.failLine = (el) => {
    if (!el) return;
    el.classList.remove('dash-skeleton');
    el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;gap:6px;min-height:inherit;height:100%;font-size:var(--cds-font-size-caption);color:var(--color-fg-muted)"><span style="width:.375rem;height:.375rem;border-radius:50%;background:var(--color-bad)"></span>Failed to load</div>';
  };
  LX.initials = (name) => { const w = String(name).split(/\s+/).filter((x) => /^[A-ZÁÉÍÓÚÑ]/.test(x) && !/^(Jr|Sr|II|III|IV)\.?,?$/.test(x)); return ((w[0] || name)[0] + (w.length > 1 ? w[w.length - 1][0] : '')).toUpperCase(); };
  // candidate picture: a photo when one is on file (LX_PHOTOS: name -> url), otherwise colored initials
  LX.avatar = (name, color, text) => {
    const src = (window.LX_PHOTOS || {})[name];
    if (src) { const img = document.createElement('img'); img.className = 'lx-photo'; img.src = src; img.alt = 'Photo of ' + name; img.loading = 'lazy'; return img; }
    const ini = document.createElement('div'); ini.className = 'lx-initials'; ini.style.background = color; ini.setAttribute('aria-hidden', 'true'); ini.textContent = text || LX.initials(name); return ini;
  };
  // photo credits for the candidates shown (LX_PHOTO_CREDITS: name -> {a: author, l: license, u: license url, f: file page})
  LX.photoCredit = (el, names) => {
    if (!el) return;
    const P = window.LX_PHOTOS || {}, C = window.LX_PHOTO_CREDITS || {};
    const shown = names.filter((n) => P[n]);
    el.replaceChildren();
    if (!shown.length) { el.hidden = true; return; }
    el.hidden = false;
    el.append(document.createTextNode('Photos: '));
    shown.forEach((n, i) => {
      const c = C[n];
      if (i) el.append(document.createTextNode('; '));
      if (!c) { el.append(document.createTextNode(n + ', official U.S. Congress portrait (public domain)')); return; }
      el.append(document.createTextNode(n + ', '));
      const a = document.createElement('a'); a.href = c.f; a.target = '_blank'; a.rel = 'noopener'; a.textContent = c.a ? c.a : 'Wikimedia Commons'; el.append(a);
      el.append(document.createTextNode(', '));
      if (c.u) { const l = document.createElement('a'); l.href = c.u; l.target = '_blank'; l.rel = 'noopener'; l.textContent = c.l; el.append(l); } else el.append(document.createTextNode(c.l));
    });
    el.append(document.createTextNode(shown.some((n) => C[n]) ? '. Wikimedia Commons photos are cropped. Candidates without a freely licensed photo are shown with initials.' : '.'));
  };
  // a credit line placed right after a card container, created on first use
  LX.creditAfter = (box, id) => {
    let el = document.getElementById(id);
    if (!el) { el = document.createElement('p'); el.className = 'lx-credit lx-credit-after'; el.id = id; box.after(el); }
    return el;
  };
  // ---------- zoomable maps with city labels (statewide frame: 600 x 643) ----------
  LX.YEAR0 = 2016;   // first election year shown in charts
  LX.MAP_W = 600; LX.MAP_H = 643;
  // [name, x, y, tier] in map coordinates (same projection as the shapes; wi/tools/build_shapes.py): tier 1 always shown; tier 2 from 2x zoom; tier 3 from 4x
  LX.CITIES = [
    ["Milwaukee", 494.9, 560.1, 1], ["Madison", 344.1, 557.4, 1], ["Green Bay", 479.7, 357.6, 1], ["Eau Claire", 137.7, 316.9, 1],
    ["La Crosse", 160.6, 456.2, 1], ["Wausau", 320.5, 298.3, 1], ["Superior", 86.0, 52.8, 1], ["Appleton", 440.7, 393.0, 1],
    ["Kenosha", 504.9, 622.3, 2], ["Racine", 508.4, 602.8, 2], ["Waukesha", 462.2, 564.5, 2], ["Oshkosh", 428.7, 425.8, 2],
    ["Janesville", 383.2, 610.8, 2], ["Sheboygan", 511.8, 461.8, 2], ["Fond du Lac", 438.7, 460.2, 2], ["Stevens Point", 326.1, 358.1, 2],
    ["Manitowoc", 516.2, 415.2, 2], ["Rhinelander", 341.4, 205.0, 2], ["Ashland", 201.2, 73.0, 2], ["Hudson", 15.4, 290.9, 2],
    ["Platteville", 235.2, 603.8, 2], ["Marshfield", 267.5, 338.1, 2], ["Beloit", 382.1, 634.8, 2], ["West Bend", 465.9, 507.6, 2],
    ["Brookfield", 474.6, 557.5, 3], ["West Allis", 484.8, 563.4, 3], ["Menomonee Falls", 473.2, 541.3, 3], ["Sun Prairie", 362.9, 542.1, 3],
    ["Fitchburg", 337.3, 572.9, 3], ["Middleton", 333.7, 554.2, 3], ["De Pere", 475.3, 366.6, 3], ["Neenah", 436.3, 403.5, 3],
    ["Watertown", 411.7, 540.1, 3], ["Mequon", 486.5, 535.9, 3], ["Menomonie", 96.8, 307.1, 3], ["Chippewa Falls", 148.4, 299.8, 3],
    ["Baraboo", 309.5, 502.8, 3], ["Whitewater", 412.0, 589.8, 3], ["Wisconsin Rapids", 302.2, 377.4, 3],
  ];
  // Wraps a map's shapes in a zoom layer: pinch or Ctrl/⌘ + scroll to zoom, drag to pan once zoomed, +/−/reset buttons,
  // and city labels that stay the same size on screen. Returns { layer, zoomTo([x, y, w, h]) }.
  LX.zoomMap = (el, svg, W, H, label) => {
    if (svg.node()._zm) return svg.node()._zm;
    const layer = svg.append('g').attr('class', 'lx-zl');
    const cityG = svg.append('g').attr('class', 'lx-cities').attr('pointer-events', 'none');
    const cities = LX.CITIES.map(([n, x, y, t]) => ({ n, x, y, t }));
    const cg = cityG.selectAll('g').data(cities).join('g');
    cg.append('circle').attr('fill', 'var(--color-fg)').attr('stroke', 'var(--color-panel)');
    cg.append('text').text((d) => d.n).attr('fill', 'var(--color-fg)').attr('stroke', 'var(--color-panel)').attr('paint-order', 'stroke')
      .attr('stroke-linejoin', 'round').attr('font-family', 'var(--font-anthropic-sans)').attr('font-weight', 500);
    let k = 1, t = d3.zoomIdentity;
    const place = () => {
      layer.attr('transform', t); cityG.attr('transform', t);
      cg.attr('display', (d) => (d.t === 1 || (d.t === 2 && k >= 2) || (d.t === 3 && k >= 4)) ? null : 'none');
      cg.select('circle').attr('cx', (d) => d.x).attr('cy', (d) => d.y).attr('r', 2.6 / k).attr('stroke-width', 1 / k);
      cg.select('text').attr('text-anchor', (d) => d.x > W - 80 ? 'end' : 'start').attr('x', (d) => d.x > W - 80 ? d.x - 5 / k : d.x + 5 / k).attr('y', (d) => d.y + 4.5 / k).attr('font-size', (d) => (d.t === 1 ? 14 : 12.5) / k).attr('stroke-width', 3.5 / k);
      svg.style('touch-action', k > 1.01 ? 'none' : 'pan-y').style('cursor', k > 1.01 ? 'grab' : null);
      reset.hidden = k <= 1.01;
    };
    const hint = document.createElement('div'); hint.className = 'lx-zoomhint'; hint.textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? 'Use ⌘ + scroll to zoom the map' : 'Use Ctrl + scroll to zoom the map';
    let hintT = null;
    const zoom = d3.zoom().scaleExtent([1, 12]).extent([[0, 0], [W, H]]).translateExtent([[0, 0], [W, H]])
      .filter((e) => {
        if (e.type === 'wheel') {
          if (e.ctrlKey || e.metaKey) return true;
          hint.classList.add('on'); clearTimeout(hintT); hintT = setTimeout(() => hint.classList.remove('on'), 1200); return false;
        }
        if (e.type === 'touchstart') return e.touches.length > 1 || k > 1.01;
        return !e.button && (k > 1.01 || e.type === 'dblclick');
      })
      .on('zoom', (e) => { t = e.transform; k = t.k; place(); });
    svg.call(zoom).on('dblclick.zoom', null);
    // buttons
    el.style.position = 'relative';
    const ctl = document.createElement('div'); ctl.className = 'lx-zoomctl';
    const btn = (txt, aria, fn) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = txt; b.setAttribute('aria-label', aria); b.addEventListener('click', fn); ctl.append(b); return b; };
    btn('+', 'Zoom in', () => svg.transition().duration(250).call(zoom.scaleBy, 2));
    btn('−', 'Zoom out', () => svg.transition().duration(250).call(zoom.scaleBy, 0.5));
    const reset = btn('⟲', 'Reset zoom', () => svg.transition().duration(300).call(zoom.transform, d3.zoomIdentity));
    el.append(ctl, hint);
    const zoomTo = (box, animate = true) => {
      const tr = !box ? d3.zoomIdentity : (() => { const [x, y, w, h] = box, s = Math.min(12, 0.95 * Math.min(W / w, H / h)); return d3.zoomIdentity.translate(W / 2, H / 2).scale(s).translate(-(x + w / 2), -(y + h / 2)); })();
      (animate ? svg.transition().duration(400) : svg).call(zoom.transform, tr);
    };
    place();
    const api = { layer, zoomTo, k: () => k };
    svg.node()._zm = api;
    return api;
  };
  LX.stateWord = (status, isFirst) => status === 'final' ? (isFirst ? 'Winner' : '') : status === 'counting' ? (isFirst ? 'Leading' : '') : '';

  // 2026 races on the ballot (shown before any results exist)
  LX.SCHEDULE_2026 = {
    statewide: ['Governor', 'Attorney General', 'Secretary of State', 'Treasurer'],
    plans: { house: 'a2024', senate: 's2024' },
    fortbend: ['County Judge', 'Commissioner Pct 2', 'Commissioner Pct 4'],
  };
  LX.ELECTION_2026 = 'Tuesday, Nov. 3, 2026';
  LX.LIVE = true;       // 2026 races, filled in on election night (wi/tools/wi_live.py)
  LX.LAST_YEAR = 2024;
  // areas on the Key Local Races tab (the tab's internal id stays 'fortbend' so old links keep working)
  LX.LOCAL_AREAS = [['fortbend', 'Fort Bend County'], ['harris', 'Harris County'], ['tarrant', 'Tarrant County'], ['collin', 'Collin County'],
    ['williamson', 'Williamson County'], ['denton', 'Denton County'], ['austin', 'City of Austin'], ['dallas', 'City of Dallas']];
  LX.localArea = () => { const a = dash.params().lr_area; return LX.LOCAL_AREAS.some(([k]) => k === a) ? a : 'fortbend'; };

  // live 2026 status banner, shared by every tab
  LX.liveBanner = (el, year, source) => {
    if (!el) return;
    if (year !== 2026) { el.hidden = true; return; }
    const st = dash.data('live_status');
    const s = st.status === 'ok' ? (Array.isArray(st.data) ? st.data[0] : st.data) || {} : {};
    el.hidden = false; el.replaceChildren();
    const dot = document.createElement('span'); dot.className = 'lx-live-dot' + (s.phase === 'counting' ? ' on' : '');
    const t = document.createElement('span');
    const when = s.updated_at ? new Date(s.updated_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago', timeZoneName: 'short' }) : null;
    t.textContent = s.phase === 'counting' ? `Unofficial results, still being counted. Last updated ${when || '—'}.`
      : s.phase === 'final' ? `Election-night count complete${when ? ' (' + when + ')' : ''}. Results stay unofficial until the state canvass.`
      : `Election Day is ${LX.ELECTION_2026}. Results will appear here as counties report after polls close at 8 p.m. Central. Wisconsin has no statewide election-night results feed, so results come from CivicAPI, which collects county reports.`;
    const src = document.createElement('span'); src.className = 'lx-live-src';
    src.setAttribute('data-source', 'live_status'); src.setAttribute('data-field', 'phase');
    src.textContent = source ? ' Source: ' + source + '.' : s.source ? ' Source: ' + s.source + '.' : '';
    el.append(dot, t, src);
  };

  // ---------- dropdowns ----------
  // a <select> with an optional visible label; onChange gets the chosen value
  LX.makeSelect = (label, onChange, ariaLabel) => {
    const wrap = document.createElement('label'); wrap.className = 'lx-select';
    if (label) { const s = document.createElement('span'); s.className = 'lx-select-label'; s.textContent = label; wrap.append(s); }
    const sel = document.createElement('select'); if (ariaLabel || label) sel.setAttribute('aria-label', ariaLabel || label);
    sel.addEventListener('change', () => onChange(sel.value));
    wrap.append(sel); return { wrap, sel };
  };
  // replace options only when they change; keep the shown value in step with the page
  LX.setOptions = (sel, opts, value) => {
    const key = opts.map((o) => o[0] + '\u0001' + o[1]).join('\u0002');
    if (sel._key !== key) { sel.replaceChildren(...opts.map(([v, t]) => new Option(t, v))); sel._key = key; }
    if (document.activeElement !== sel || sel.value !== String(value)) sel.value = String(value);
  };
  // office + year pickers over a list of races: [{ race, year, group, yearLabel }]
  LX.racePicker = (box, groups, races, current, onPick) => {
    if (!box._picker) {
      box.replaceChildren();
      const office = LX.makeSelect('Office', (g) => {
        const cur = box._races.find((r) => r.race === box._current) || {};
        const list = box._races.filter((r) => r.group === g);
        const pick = list.find((r) => r.year === cur.year) || list.filter((r) => r.year < 2026).pop() || list[list.length - 1];
        if (pick) onPick(pick.race);
      });
      const year = LX.makeSelect('Year', (race) => onPick(race));
      box.append(office.wrap, year.wrap);
      box._picker = { office: office.sel, year: year.sel };
    }
    box._races = races; box._current = current;
    const cur = races.find((r) => r.race === current) || races[races.length - 1];
    LX.setOptions(box._picker.office, groups.filter(([g]) => races.some((r) => r.group === g)), cur.group);
    const list = races.filter((r) => r.group === cur.group).sort((a, b) => b.year - a.year || b.race.length - a.race.length);
    LX.setOptions(box._picker.year, list.map((r) => [r.race, r.yearLabel]), cur.race);
  };

  // tabs
  const TABS = ['statewide', 'house', 'senate'];
  LX.tab = () => { const t = dash.params().tab; return TABS.includes(t) ? t : 'statewide'; };
  LX.swView = () => { const v = dash.params().sw_view; return ['offices', 'ushouse', 'sboe'].includes(v) ? v : 'offices'; };
  document.querySelectorAll('.lx-tab').forEach((b) => b.addEventListener('click', () => {
    dash.setParams({ tab: b.dataset.tab });
    dash.setLink(b.dataset.tab === 'statewide' ? 'top' : 'tab-' + b.dataset.tab);
  }));
  document.querySelectorAll('.lx-subtab').forEach((b) => b.addEventListener('click', () => {
    dash.setParams({ sw_view: b.dataset.sub });
    dash.setLink(b.dataset.sub === 'offices' ? 'top' : 'view-' + b.dataset.sub);
  }));
  const named = location.hash.slice(1);
  if (TABS.includes(named.replace('tab-', ''))) dash.setParams({ tab: named.replace('tab-', '') });
  if (named === 'view-ushouse' || named === 'view-sboe') dash.setParams({ tab: 'statewide', sw_view: named.slice(5) });

  // mount a template the first time its section is shown
  const mounted = {};
  LX.mount = (id) => {
    if (mounted[id]) return false;
    const host = document.getElementById(id), tpl = document.getElementById('tpl-' + id);
    if (!host || !tpl) return false;
    host.append(tpl.content.cloneNode(true));
    mounted[id] = true;
    return true;
  };
  LX.isMounted = (id) => !!mounted[id];

  dash.onData(() => {
    const tab = LX.tab(), view = LX.swView();
    TABS.forEach((t) => { const s = document.getElementById('tab-' + t); if (s) s.hidden = t !== tab; });
    document.querySelectorAll('.lx-tab').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === tab)));
    ['offices', 'ushouse', 'sboe'].forEach((v) => { const s = document.getElementById('view-' + v); if (s) s.hidden = v !== view; });
    document.querySelectorAll('.lx-subtab').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.sub === view)));
  });
})();
