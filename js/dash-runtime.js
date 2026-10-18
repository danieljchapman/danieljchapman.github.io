/* Minimal stand-in for the Claude dashboard runtime, so the dashboard runs as a plain static site.
   Provides: dash.data, dash.calc, dash.onData, dash.params, dash.setParams, dash.resetParams, dash.setLink, dash.colors. */
(() => {
  const DATASETS = window.DASH_DATASETS || {};      // id -> { url, format }
  const DEFAULTS = Object.assign({}, window.DASH_PARAMS || {});
  const state = {};                                  // id -> { status, data, columns, message }
  const calcs = {};                                  // id -> { inputs, fn, title, description }
  const memo = {};                                   // id -> { key, result, status, message }
  const listeners = [];
  let params = Object.assign({}, DEFAULTS);
  let scheduled = false;

  // ---------- CSV ----------
  function parseCSV(text) {
    const rows = []; let row = [], field = '', q = false, i = 0;
    if (text.charCodeAt(0) === 0xfeff) i = 1;
    for (; i < text.length; i++) {
      const c = text[i];
      if (q) {
        if (c === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else q = false; }
        else field += c;
      } else if (c === '"') q = true;
      else if (c === ',') { row.push(field); field = ''; }
      else if (c === '\n' || c === '\r') {
        if (c === '\r' && text[i + 1] === '\n') i++;
        row.push(field); field = '';
        if (row.length > 1 || row[0] !== '') rows.push(row);
        row = [];
      } else field += c;
    }
    if (field !== '' || row.length) { row.push(field); rows.push(row); }
    const head = rows.shift() || [];
    const data = rows.map((r) => { const o = {}; head.forEach((h, j) => { o[h] = r[j] === undefined ? '' : r[j]; }); return o; });
    return { data, columns: head };
  }

  // ---------- loading ----------
  // refresh: keep showing the current data while reloading, and keep it if the reload fails
  function load(id, refresh, then) {
    const ds = DATASETS[id];
    if (!ds) { state[id] = { status: 'missing', data: [], message: 'Unknown data source ' + id }; return; }
    const prev = state[id];
    const keep = refresh && prev && prev.status === 'ok';
    if (!keep) state[id] = { status: 'loading', data: [] };
    const url = ds.url + (ds.live ? (ds.url.includes('?') ? '&' : '?') + 't=' + Date.now() : '');
    fetch(url, { cache: ds.live ? 'no-store' : 'default' })
      .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status + ' for ' + ds.url); return ds.format === 'json' ? r.json() : r.text(); })
      .then((body) => {
        if (ds.format === 'json') {
          const data = Array.isArray(body) ? body : (body.rows || body.data || body.results || body);
          state[id] = { status: 'ok', data, columns: Array.isArray(data) && data[0] ? Object.keys(data[0]) : [] };
        } else {
          const p = parseCSV(body);
          state[id] = { status: 'ok', data: p.data, columns: p.columns };
        }
      })
      .catch((e) => { console.error(e); if (!keep) state[id] = { status: 'error', data: [], message: String(e.message || e) }; })
      .finally(() => { schedule(); if (then) then(); });
  }

  function compute(id) {
    const c = calcs[id];
    const ins = c.inputs.map((i) => read(i));
    const bad = ins.find((x) => x.status === 'error' || x.status === 'missing');
    if (bad) return { status: 'error', data: [], message: 'An input failed to load' };
    if (ins.some((x) => x.status !== 'ok')) return { status: 'loading', data: [] };
    const key = ins.map((x) => x.data);
    const m = memo[id];
    if (m && m.key.length === key.length && m.key.every((k, i) => k === key[i])) return m.out;
    let out;
    try {
      const res = c.fn(...ins.map((x) => x.data));
      out = { status: 'ok', data: res, columns: Array.isArray(res) && res[0] ? Object.keys(res[0]) : [] };
    } catch (e) {
      console.error('Calculation ' + id + ' failed', e);
      out = { status: 'error', data: [], message: String(e.message || e) };
    }
    memo[id] = { key, out };
    return out;
  }

  function read(id) {
    if (calcs[id]) return compute(id);
    if (!state[id]) load(id);
    return state[id];
  }

  // ---------- notify ----------
  function run() {
    scheduled = false;
    for (const fn of listeners) {
      try { fn(); } catch (e) { console.error('Dashboard draw error', e); }
    }
  }
  function schedule() { if (!scheduled) { scheduled = true; requestAnimationFrame(run); } }
  let lastW = window.innerWidth;
  window.addEventListener('resize', () => { if (window.innerWidth !== lastW) { lastW = window.innerWidth; clearTimeout(run._t); run._t = setTimeout(schedule, 120); } });

  // ---------- params in the URL (so links keep the view) ----------
  const qs = new URLSearchParams(location.search);
  for (const [k, v] of qs) {
    if (!(k in DEFAULTS)) continue;
    params[k] = v === '' ? null : /^-?\d+$/.test(v) ? Number(v) : v;
  }
  function syncURL() {
    const u = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== DEFAULTS[k] && v != null) u.set(k, v);
    const s = u.toString();
    history.replaceState(null, '', location.pathname + (s ? '?' + s : '') + location.hash);
  }

  window.dash = {
    colors: ['#3b6fd4', '#d4802b', '#2a9d8f', '#9c5bd1', '#c94f7c', '#5b8c2a', '#7a6a58', '#4aa3c7'],
    data(id) { const s = read(id) || { status: 'loading', data: [] }; return Object.assign({ refreshing: false, meta: [] }, s); },
    calc(id, def) { calcs[id] = def; },
    loader() { /* not needed for static files */ },
    onData(fn) { listeners.push(fn); try { fn(); } catch (e) { console.error('Dashboard draw error', e); } },
    params() { return Object.assign({}, params); },
    setParams(p) {
      for (const [k, v] of Object.entries(p || {})) {
        if (v === null || ['string', 'number', 'boolean'].includes(typeof v)) params[k] = v;
      }
      syncURL(); schedule();
    },
    resetParams() { params = Object.assign({}, DEFAULTS); syncURL(); schedule(); },
    setLink(name) { history.replaceState(null, '', location.pathname + location.search + (name ? '#' + name : '')); },
    refresh(id) { if (DATASETS[id]) { load(id); schedule(); } },
  };

  // election night: every 2 minutes, re-check the status file until the count is final (pages opened
  // before polls close start updating on their own); reload the results whenever the status changes
  let stamp = null;
  const liveStatus = () => { const st = state.live_status; return st && st.status === 'ok' && st.data && st.data[0] ? st.data[0] : null; };
  setInterval(() => {
    const s0 = liveStatus();
    if (s0 && s0.phase === 'final') return;
    load('live_status', true, () => {
      const s1 = liveStatus();
      if (!s1 || s1.phase === 'pre-election' || s1.updated_at === stamp) return;
      stamp = s1.updated_at;
      load('live_2026', true);
    });
  }, 2 * 60 * 1000);

  // early voting: re-check the early-vote status every 10 minutes through Election Day; reload the daily counts when it changes
  let evStamp = null;
  setInterval(() => {
    if (!DATASETS.ev_status || Date.now() > Date.parse('2026-11-04T00:00:00Z')) return;
    const s0 = state.ev_status && state.ev_status.status === 'ok' && state.ev_status.data && state.ev_status.data[0];
    if (evStamp === null && s0) evStamp = s0.updated_at;
    load('ev_status', true, () => {
      const st = state.ev_status, s1 = st && st.status === 'ok' && st.data && st.data[0];
      if (!s1 || s1.updated_at === evStamp) return;
      evStamp = s1.updated_at;
      load('ev_2026', true);
    });
  }, 10 * 60 * 1000);
})();
