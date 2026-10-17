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
  LX.initials = (name) => { const w = String(name).split(/\s+/).filter((x) => /^[A-ZÁÉÍÓÚÑ]/.test(x)); return ((w[0] || name)[0] + (w.length > 1 ? w[w.length - 1][0] : '')).toUpperCase(); };
  LX.stateWord = (status, isFirst) => status === 'final' ? (isFirst ? 'Winner' : '') : status === 'counting' ? (isFirst ? 'Leading' : '') : '';

  // 2026 races on the ballot (shown before any results exist)
  LX.SCHEDULE_2026 = {
    statewide: ['Governor', 'Senate', 'Lt. Governor', 'Railroad Commissioner'],
    plans: { house: 'planh2316', senate: 'plans2168', ushouse: 'planc2333', sboe: 'plane2106' },
    fortbend: ['County Judge', 'Commissioner Pct 2', 'Commissioner Pct 4'],
  };
  LX.ELECTION_2026 = 'Tuesday, Nov. 3, 2026';

  // live 2026 status banner, shared by every tab
  LX.liveBanner = (el, year) => {
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
    src.textContent = s.source ? ' Source: ' + s.source + '.' : '';
    el.append(dot, t, src);
  };

  // tabs
  const TABS = ['statewide', 'house', 'senate', 'fortbend'];
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
