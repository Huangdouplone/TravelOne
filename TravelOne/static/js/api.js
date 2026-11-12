/* Copyright (c) 2026 黄豆666/huangdouplone
 * SPDX-License-Identifier: MIT */
/* TravelOne API client: timeouts, retries, friendly errors and local caching */
(function () {
  const jsonHeaders = { 'Content-Type': 'application/json' };
  const MODE_KEY = 'travelone.mode';
  let mode = localStorage.getItem(MODE_KEY) === 'global' ? 'global' : 'cn';
  const TIMEOUT = 26000;
  const detailCache = new Map();

  function qs(params) {
    const search = new URLSearchParams();
    const merged = Object.assign({}, params || {});
    if (merged.mode === undefined) merged.mode = mode;
    Object.keys(merged).forEach((key) => {
      const value = merged[key];
      if (value === undefined || value === null || value === '') return;
      search.append(key, value);
    });
    const str = search.toString();
    return str ? '?' + str : '';
  }

  function friendlyError(err, path) {
    const isFile = location.protocol === 'file:';
    if (isFile) return new Error('Opened via file://; browsers block local API calls. Start with start.bat or python app.py.');
    if (err && err.name === 'AbortError') return new Error('Request timed out. Check that the local service is running.');
    if (err instanceof TypeError) return new Error('Cannot reach the local service (' + path + '). Start it and retry.');
    return err;
  }

  // 所有 /api 请求统一带上当前模式，避免逐个端点漏传
  function withMode(path) {
    if (typeof path !== 'string' || path.indexOf('/api/') !== 0) return path;
    if (/[?&]mode=/.test(path)) return path;
    return path + (path.indexOf('?') >= 0 ? '&' : '?') + 'mode=' + mode;
  }

  async function request(path, options, attempt) {
    const tries = attempt === undefined ? 1 : attempt;
    const opts = Object.assign({ headers: {} }, options || {});
    if (opts.body && typeof opts.body !== 'string') {
      opts.body = JSON.stringify(opts.body);
      opts.headers = Object.assign({}, jsonHeaders, opts.headers);
    }
    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    if (controller) {
      opts.signal = controller.signal;
      setTimeout(() => controller.abort(), TIMEOUT);
    }
    try {
      const resp = await fetch(withMode(path), opts);
      const text = await resp.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch (e) { data = { ok: false, message: text.slice(0, 200) }; }
      if (!resp.ok) {
        const err = new Error((data && data.message) || ('HTTP ' + resp.status));
        err.status = resp.status;
        err.payload = data;
        // Retry once on 5xx; throw 4xx immediately
        if (resp.status >= 500 && tries < 2) {
          await new Promise((r) => setTimeout(r, 600));
          return request(path, options, tries + 1);
        }
        throw err;
      }
      return data;
    } catch (err) {
      if (err && err.status) throw err;
      if (tries < 2) {
        await new Promise((r) => setTimeout(r, 600));
        return request(path, options, tries + 1);
      }
      throw friendlyError(err, path);
    }
  }

  function cacheKey(kind, id) { return kind + '|' + id; }

  // Internal: SHA-256 counter stream matching core/secure.py on the server
  async function xorStream(dataBytes, keyBytes) {
    const out = new Uint8Array(dataBytes.length);
    const counter = new Uint8Array(4);
    for (let offset = 0; offset < dataBytes.length; offset += 32) {
      const block = new Uint8Array(keyBytes.length + 4);
      block.set(keyBytes, 0);
      new DataView(counter.buffer).setUint32(0, Math.floor(offset / 32), false);
      block.set(counter, keyBytes.length);
      const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', block));
      for (let i = 0; i < 32 && offset + i < dataBytes.length; i++) out[offset + i] = dataBytes[offset + i] ^ digest[i];
    }
    return out;
  }

  function b64encode(bytes) {
    let str = '';
    bytes.forEach((b) => { str += String.fromCharCode(b); });
    return btoa(str);
  }

  function b64decode(text) {
    const raw = atob(text);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return bytes;
  }

  window.API = {
    request,
    cryptoSession: () => request('/api/crypto/session'),
    canEncrypt: () => !!(window.crypto && crypto.subtle),
    // Encrypt an object to {sid, cipher}; fall back to {plain: object} when unsupported
    encryptPayload: async (obj) => {
      if (!(window.crypto && crypto.subtle)) return { plain: obj };
      const session = await request('/api/crypto/session');
      const key = b64decode(session.key);
      const cipher = await xorStream(new TextEncoder().encode(JSON.stringify(obj)), key);
      return { sid: session.sid, cipher: b64encode(cipher) };
    },
    config: () => request('/api/config'),
    saveConfig: (body) => request('/api/config', { method: 'POST', body }),
    meta: () => request('/api/meta'),
    health: () => request('/api/health'),
    sources: () => request('/api/sources'),
    mapGuide: () => request('/api/map/guide'),
    platforms: () => request('/api/platforms'),
    search: (q, kind, page, pageSize) => request('/api/search' + qs({ q, kind, page, page_size: pageSize })),
    providers: () => request('/api/providers'),
    saveProvider: (sealed) => request('/api/providers/config', { method: 'POST', body: sealed }),
    testProvider: (name, city) => request('/api/providers/test?name=' + encodeURIComponent(name) + qs({ city })),
    liveHealth: () => request('/api/live/health'),
    liveCache: (op) => request('/api/live/cache' + qs({ op })),
    attractions: (params) => request('/api/attractions' + qs(params)),
    hotels: (params) => request('/api/hotels' + qs(params)),
    hotelsSimple: (params) => request('/api/hotels' + qs(params)),
    detail: (key) => request('/api/attractions/' + encodeURIComponent(key)),
    hotelDetail: (id) => request('/api/hotels/' + encodeURIComponent(id)),
    compare: (attrs, hotels) => request('/api/compare?attractions=' +
      (attrs || []).map(encodeURIComponent).join(',') + '&hotels=' + (hotels || []).map(encodeURIComponent).join(',')),
    metros: (city) => request('/api/metros' + qs({ city })),
    collect: (city) => request('/api/collect' + qs({ city }), { method: 'POST' }),
    collectStatus: () => request('/api/collect/status'),
    createTrip: (body) => request('/api/trips', { method: 'POST', body: body || { title: 'My trip' } }),
    getTrip: (id) => request('/api/trips/' + id),
    addItem: (id, body) => request('/api/trips/' + id + '/items', { method: 'POST', body }),
    removeItem: (id, itemId) => request('/api/trips/' + id + '/items/' + itemId, { method: 'DELETE' }),
    updateItems: (id, items) => request('/api/trips/' + id + '/items', { method: 'PUT', body: { items } }),
    plan: (id, body) => request('/api/trips/' + id + '/plan', { method: 'POST', body: body || {} }),
    transport: (params) => request('/api/transport' + qs(params)),
    fuel: (province) => request('/api/fuel' + qs({ province })),
    geocode: (q, city) => request('/api/geocode' + qs({ q, city })),
    cover: (name, city, v) => (window.offlineCover ? window.offlineCover(name, city) : '/api/cover' + qs({ name, city, v: v || 0 })),

    rememberDetail: (kind, id, data) => detailCache.set(cacheKey(kind, id), data),
    recallDetail: (kind, id) => detailCache.get(cacheKey(kind, id)) || null,

    isFileMode: () => location.protocol === 'file:',
    getMode: () => mode,
    setMode: (next) => { mode = next === 'global' ? 'global' : 'cn'; localStorage.setItem(MODE_KEY, mode); },
  };
})();