(() => {
  const root = document.querySelector('.lx');
  const css = (n) => getComputedStyle(root).getPropertyValue(n).trim();
  const LX = (window.LX = {});
  LX.css = css;
  LX.fmt = d3.format(',');
  LX.pct = d3.format('.1%');
  LX.enc = (s) => String(s).replace(/%/g, '%25').replace(/&/g, '%26').replace(/=/g, '%3D');
  LX.PARTY = { R: 'Republican', D: 'Democrat', L: 'Libertarian', G: 'Green', I: 'Independent', O: 'Other', W: 'Write-in' };
  LX.partyCol = (p) => css({ R: '--lx-rep', D: '--lx-dem', L: '--lx-lib', G: '--lx-grn', I: '--lx-ind' }[p] || '--cds-chart-muted');
  LX.RAMP = {
    R: ['#fcd5d0', '#f09a8f', '#da5a4c', '#b02a1f', '#73110b'],
    D: ['#d3e1fb', '#93b4ef', '#5583dc', '#2a56b4', '#0f2d70'],
    I: ['#e6dbf4', '#c3a9e6', '#9c74d3', '#7446b3', '#4a2580'],
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
  // ---------- zoomable maps with city labels (statewide frame: 678 x 645) ----------
  // same projection the county and district shapes were drawn with
  LX.projTX = (lon, lat) => [(lon + 106.7) * Math.cos(31 * Math.PI / 180) * 60, (36.6 - lat) * 60];
  // [name, lat, lon, tier]: tier 1 always shown; tier 2 from 2x zoom; tier 3 from 4x
  LX.CITIES_TX = [
    ['Houston', 29.7604, -95.3698, 1], ['San Antonio', 29.4241, -98.4936, 1], ['Dallas', 32.7767, -96.797, 1], ['Austin', 30.2672, -97.7431, 1],
    ['Fort Worth', 32.7555, -97.3308, 1], ['El Paso', 31.7619, -106.485, 1], ['Corpus Christi', 27.8006, -97.3964, 1], ['Lubbock', 33.5779, -101.8552, 1],
    ['Amarillo', 35.222, -101.8313, 1], ['Laredo', 27.5306, -99.4803, 1], ['McAllen', 26.2034, -98.23, 1], ['Midland', 31.9973, -102.0779, 1],
    ['Brownsville', 25.9017, -97.4975, 2], ['Arlington', 32.7357, -97.1081, 3], ['Plano', 33.0198, -96.6989, 2], ['Denton', 33.2148, -97.1331, 2],
    ['Waco', 31.5493, -97.1467, 2], ['Killeen', 31.1171, -97.7278, 2], ['College Station', 30.628, -96.3344, 2], ['Tyler', 32.3513, -95.3011, 2],
    ['Beaumont', 30.0802, -94.1266, 2], ['Wichita Falls', 33.9137, -98.4934, 2], ['Abilene', 32.4487, -99.7331, 2], ['San Angelo', 31.4638, -100.437, 2],
    ['Odessa', 31.8457, -102.3676, 2], ['Galveston', 29.3013, -94.7977, 2], ['Victoria', 28.8053, -97.0036, 2], ['Longview', 32.5007, -94.7405, 2],
    ['The Woodlands', 30.1658, -95.4613, 2], ['Round Rock', 30.5083, -97.6789, 2], ['New Braunfels', 29.703, -98.1245, 2], ['Texarkana', 33.4251, -94.0477, 2],
    ['Del Rio', 29.3709, -100.8959, 2], ['Harlingen', 26.1906, -97.6961, 2], ['Sugar Land', 29.6197, -95.6349, 2], ['McKinney', 33.1972, -96.6398, 2],
    ['Frisco', 33.1507, -96.8236, 3], ['Irving', 32.814, -96.9489, 3], ['Garland', 32.9126, -96.6389, 3], ['Grand Prairie', 32.7459, -96.9978, 3],
    ['Mesquite', 32.7668, -96.5992, 3], ['Carrollton', 32.9756, -96.89, 3], ['Lewisville', 33.0462, -96.9942, 3], ['Allen', 33.1032, -96.6706, 3],
    ['Richardson', 32.9483, -96.7299, 3], ['Mansfield', 32.5632, -97.1417, 3], ['Pasadena', 29.6911, -95.2091, 3], ['Pearland', 29.5636, -95.286, 3],
    ['League City', 29.5075, -95.0949, 3], ['Katy', 29.7858, -95.8245, 3], ['Baytown', 29.7355, -94.9774, 3], ['Conroe', 30.3119, -95.4561, 3],
    ['Spring', 30.0799, -95.4172, 3], ['Georgetown', 30.6333, -97.6772, 3], ['Cedar Park', 30.5052, -97.8203, 3],
    ['Pflugerville', 30.4394, -97.62, 3], ['San Marcos', 29.8833, -97.9414, 3], ['Kyle', 29.9891, -97.8772, 3], ['Temple', 31.0982, -97.3428, 3],
    ['Edinburg', 26.3017, -98.1633, 3], ['Mission', 26.2159, -98.3253, 3], ['Pharr', 26.1948, -98.1836, 3], ['Sherman', 33.6357, -96.6089, 3],
    ['Huntsville', 30.7235, -95.5508, 3], ['Lufkin', 31.3382, -94.7291, 3], ['Nacogdoches', 31.6035, -94.6555, 3], ['Weatherford', 32.7593, -97.7973, 3],
    ['Seguin', 29.5688, -97.9647, 3], ['Port Arthur', 29.885, -93.94, 3], ['Kingsville', 27.5159, -97.8561, 3], ['Eagle Pass', 28.7091, -100.4995, 3],
    ['Big Spring', 32.2504, -101.4787, 3], ['Alpine', 30.3585, -103.661, 3], ['Pecos', 31.4229, -103.4932, 3], ['Bryan', 30.6744, -96.37, 3],
  ];
  // Wraps a map's shapes in a zoom layer: pinch or Ctrl/⌘ + scroll to zoom, drag to pan once zoomed, +/−/reset buttons,
  // and city labels that stay the same size on screen. Returns { layer, zoomTo([x, y, w, h]) }.
  LX.zoomMap = (el, svg, W, H, label) => {
    if (svg.node()._zm) return svg.node()._zm;
    const layer = svg.append('g').attr('class', 'lx-zl');
    const cityG = svg.append('g').attr('class', 'lx-cities').attr('pointer-events', 'none');
    const cities = LX.CITIES_TX.map(([n, la, lo, t]) => { const [x, y] = LX.projTX(lo, la); return { n, x, y, t }; });
    const cg = cityG.selectAll('g').data(cities).join('g');
    cg.append('circle').attr('fill', 'var(--color-fg)').attr('stroke', 'var(--color-panel)');
    cg.append('text').text((d) => d.n).attr('fill', 'var(--color-fg)').attr('stroke', 'var(--color-panel)').attr('paint-order', 'stroke')
      .attr('stroke-linejoin', 'round').attr('font-family', 'var(--font-anthropic-sans)').attr('font-weight', 500);
    let k = 1, t = d3.zoomIdentity;
    const place = () => {
      layer.attr('transform', t); cityG.attr('transform', t);
      cg.attr('display', (d) => (d.t === 1 || (d.t === 2 && k >= 2) || (d.t === 3 && k >= 4)) ? null : 'none');
      cg.select('circle').attr('cx', (d) => d.x).attr('cy', (d) => d.y).attr('r', 2.6 / k).attr('stroke-width', 1 / k);
      cg.select('text').attr('x', (d) => d.x + 5 / k).attr('y', (d) => d.y + 4.5 / k).attr('font-size', (d) => (d.t === 1 ? 14 : 12.5) / k).attr('stroke-width', 3.5 / k);
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
    statewide: ['Governor', 'Senate', 'Lt. Governor', 'Attorney General', 'Comptroller', 'Land Commissioner', 'Agriculture Commissioner', 'Railroad Commissioner'],
    plans: { house: 'planh2316', senate: 'plans2168', ushouse: 'planc2333', sboe: 'plane2106' },
    fortbend: ['County Judge', 'Commissioner Pct 2', 'Commissioner Pct 4'],
  };
  LX.ELECTION_2026 = 'Tuesday, Nov. 3, 2026';
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
      : `Election Day is ${LX.ELECTION_2026}. Results will appear here as counties report after polls close at 7 p.m. Central.`;
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
  const TABS = ['statewide', 'house', 'senate', 'fortbend', 'early'];
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
