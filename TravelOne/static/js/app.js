/* Copyright (c) 2026 黄豆666/huangdouplone
 * SPDX-License-Identifier: MIT */
/* TravelOne front-end logic: attractions, hotels, price comparison, trip, data sources */
(function () {
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

  // 首页小标题：从素材库里随机一条，随数据刷新重新随机（文本内嵌，不依赖文件挂载）
  const HERO_TIPS = [
    ["我们总是在为了未来殚心竭虑摇摆不定，为家人，为未来，为经济——最终什么都没抓住",
     "We keep worrying and wavering about the future—family, future, money—and end up holding on to nothing."],
    ["月亮和六便士你选哪个？我选最便宜的月亮",
     "Moon or sixpence? I'll take the cheapest moon."],
    ["旅途哪有那么多约束，有约束的只是不断追求完美的我们自己",
     "Travel has few real constraints; the constraint is our endless chase for a perfect trip."],
    ["你为什么要看这里？我什么都没写", "Why are you reading this? I wrote nothing."],
    ["咕咕——咕咕咕——咕——", "Coo—coo-coo—coo."],
    ["今天是周四吗？那——疯狂星期四！v我50！不是？不是也v！",
     "Is it Thursday? Crazy Thursday! Send me 50. Not Thursday? Send it anyway."],
    ["我们一生都在旅行，离开家乡的不仅是身体，还有年龄",
     "Life is a long trip; what leaves home is not only the body but the years."],
    ["学业、编制、稳定……去他丫的！哪有那么多规矩！安偏一隅的人生还算什么人生！",
     "Degrees, stable jobs, security… forget it. A life tucked in one corner is no life at all."],
    ["你知道吗，当你看到这条，就代表着我没活了", "If you see this line, it means I ran out of lines."],
    ["原先是想做个比价的，但奈何实在拿不到平台数据。万恶的垄断（bushi）",
     "I wanted a price comparison, but the platforms won't hand over data. Monopoly, eh (kidding)."],
    ["月色真美——该吃月饼了！", "The moon is beautiful—time for mooncakes."],
    ["你知道吗，这东西其实是开源的哦？可以找到我的仓库自己魔改的哦？",
     "This thing is open source, you know. Find the repo and make it yours."],
    ["这里原先应该是很官方的一堆介绍的，但我实在不愿意看那些文字，所以改了！",
     "This spot was meant for an official blurb; I couldn't stand reading it, so I changed it."],
    ["我说ai果然就是很好用吧！", "See? AI really is handy."],
    ["这些东西写的时间是26.11.12，也就是——星期四！",
     "These lines were written on 2026-11-12—a Thursday!"],
    ["never gonna give you up", "never gonna give you up"],
    ["我实在是不知道写什么来逗你开心，也不想写一些大道理和你抱怨。所以—— >ᴗoಣ",
     "I don't know what to write to cheer you up, and I won't preach. So— >ᴗoಣ"],
    ["当你看到这条，那你就看到了这条", "If you see this one, then you saw this one."],
    ["我赌你在不断点刷新，就为了看全这里的tip",
     "I bet you keep hitting refresh just to collect all these tips."],
    ["不管你在哪，不管现在是什么时间，总之，祝你早上中午晚上好！",
     "Wherever you are, whatever the hour—good morning, good noon, good evening!"],
  ];
  let heroTipIndex = -1;

  function randomHeroTip() {
    const el = document.getElementById('heroLine');
    if (!el || !HERO_TIPS.length) return;
    let index = Math.floor(Math.random() * HERO_TIPS.length);
    if (index === heroTipIndex) index = (index + 1) % HERO_TIPS.length;
    heroTipIndex = index;
    const tip = HERO_TIPS[index];
    el.textContent = isZh() ? tip[0] : tip[1];
    el.classList.remove('tip-in');
    void el.offsetWidth;          // 触发一次重排，让淡入动画重新播放
    el.classList.add('tip-in');
  }

  const state = {
    mode: (window.API && API.getMode && API.getMode()) || 'cn',
    config: null,
    meta: null,
    keyword: '',
    city: '',
    attr: { minRating: 0, minPrice: '', maxPrice: '', level: '', tags: [], flags: new Set(), near: false, anchor: null, sort: 'recommend', page: 1, size: 12, items: [], total: 0, seq: 0 },
    nearOptions: [],
    hotel: { minPrice: '', maxPrice: '', star: 0, rating: 0, metro: 0, near: 0, nearKey: '', sort: 'price_asc', page: 1, size: 8, items: [], total: 0, seq: 0 },
    cmp: { attrs: new Set(), hotels: new Set(), data: null },
    platformRows: [],
    search: { items: [], page: 1, total: 0, q: '', kind: 'all', busy: false, seq: 0 },
    tripId: null,
    trip: null,
    plan: null,
    transport: { result: null, chosen: 'rail', busy: false },
    origin: null,
    map: null,
    mapMode: 'offline',
    detailKey: null,
    detailView: null,
  };

  /* ============================ Utilities ============================ */
  function toast(msg, kind) {
    const box = $('#toast');
    const el = document.createElement('div');
    el.className = 'toast-item' + (kind ? ' ' + kind : '');
    el.textContent = window.TravelI18n ? window.TravelI18n.t(String(msg)) : msg;
    box.appendChild(el);
    box.classList.add('on');
    setTimeout(() => { el.remove(); if (!box.children.length) box.classList.remove('on'); }, 2800);
  }
  const esc = (v) => String(v === undefined || v === null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const money = (v) => (v === null || v === undefined || v === '' ? '—' : Number(v) === 0 ? 'Free' : '¥' + Number(v).toFixed(0));
  const starsHtml = (rating) => {
    const v = Number(rating) || 0;
    let out = '<span class="stars">';
    for (let i = 1; i <= 5; i++) out += `<svg class="star${v >= i - 0.25 ? ' on' : ''}" viewBox="0 0 24 24"><path d="M12 2.6l2.9 6 6.6.9-4.8 4.6 1.2 6.5-5.9-3.2-5.9 3.2 1.2-6.5L2.5 9.5l6.6-.9z"/></svg>`;
    return out + '</span>';
  };

  // 多个评分来源并列显示（百度地图 + 去哪儿），不合并、不平均
  function ratingSourcesHtml(vm) {
    const list = Array.isArray(vm.ratings) ? vm.ratings.filter((r) => r && r.value !== null && r.value !== undefined) : [];
    if (list.length < 2) return '';
    const chips = list.map((r) => {
      const name = isZh() ? (r.source_zh || r.source) : (r.source || r.source_zh);
      const count = r.count ? `<span class="rc">${Number(r.count).toLocaleString()}</span>` : '';
      return `<span class="rating-chip">${esc(name)} <b>${Number(r.value).toFixed(1)}</b>${count}</span>`;
    }).join('');
    return `<div class="rating-sources">${chips}</div>`;
  }
  const fmtMin = (m) => {
    const v = Math.round(m || 0);
    if (v < 60) return v + ' min';
    const h = Math.floor(v / 60), r = v % 60;
    return r ? `${h} h ${r} min` : `${h} h`;
  };
  const km = (v) => (v === null || v === undefined ? '—' : v < 1 ? Math.round(v * 1000) + (isZh() ? ' 米' : ' m') : Number(v).toFixed(1) + (isZh() ? ' 公里' : ' km'));
  const isZh = () => Boolean(window.TravelI18n && window.TravelI18n.lang === 'zh');

  function cityDisplay(item) {
    if (!item) return '';
    return isZh() ? (item.city || item.city_en || '') : (item.city_en || item.city || '');
  }

  function tagDisplay(item) {
    const list = isZh() ? (item.tags || []) : (item.tags_en || item.tags || []);
    return (list || []).filter((t) => isZh() || !/[一-鿿]/.test(t));
  }

  function cityLabel(name) {
    if (!name) return '';
    const row = ((state.meta && state.meta.cities) || []).find((c) => c.city === name);
    if (!row) return name;
    return isZh() ? (row.city || name) : (row.city_en || name);
  }

  function sourceChip(data) {
    if (!data || !data.source) return '';
    const kind = data.source === 'live' ? '' : (data.source === 'cache' ? ' cache' : ' bundled');
    const label = data.source === 'live' ? 'Live crawl'
      : (data.source === 'cache' ? 'Last snapshot' : 'No data');
    const time = data.fetched_at ? String(data.fetched_at).slice(11, 16) : '';
    return `<span class="src-chip${kind}" title="${esc(data.source_label || '')}">${label}${time ? ' · ' + time : ''}</span>`;
  }

  function distanceKm(a, b) {
    if (!a || !b || !isFinite(a.lat) || !isFinite(b.lat)) return null;
    const R = 6371, toRad = (x) => (x * Math.PI) / 180;
    const dLat = toRad(b.lat - a.lat), dLng = toRad(b.lng - a.lng);
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(Math.min(1, h)));
  }

  /* ============================ Bootstrap ============================ */
  // 模式切换：国内版（百度源）/ 国际版（OSM + Wikidata），切换时声明差异
  const MODE_DIFF = {
    zh: [
      ['数据源', '国内版调用百度地图网页检索；国际版调用 OpenStreetMap（ODbL），不可达时回落到 Wikidata（CC0）。'],
['覆盖范围', '国内版按行政区持续轮扫；国际版内置 50 个城市，并支持按城市名动态解析——解析成功即按城市抓取。'],
      ['地图服务', '国内版用百度地图；国际版用 MapLibre GL JS + OpenStreetMap 瓦片（© OpenStreetMap contributors），加载失败时降级为离线示意图。'],
      ['价格与评分', '国际源通常不含门票价、房晚价与评分，相关位置显示“暂无”，不做填充。'],
      ['交通口径', '国际版机票按航距分段并乘航线/枢纽系数；同区域 1600 km 内给出铁路估算；自驾按当地油价 × 固定参考汇率计，全部标注为估算。'],
    ],
    en: [
      ['Data source', 'China mode uses Baidu Maps web search; global mode uses OpenStreetMap (ODbL), falling back to Wikidata (CC0) when unreachable.'],
      ['Coverage', 'China mode sweeps administrative areas continuously; global mode ships 50 cities and resolves any city name on demand - once resolved, it is harvested by city.'],
      ['Map service', 'China mode uses Baidu Maps; global mode uses MapLibre GL JS with OpenStreetMap tiles (© OpenStreetMap contributors), falling back to the offline schematic map on load failure.'],
      ['Price & rating', 'International sources usually carry no ticket price, room rate or rating; those fields show "n/a" instead of a value.'],
      ['Transport', 'Global mode uses distance bands with route/hub factors for flights, rail estimates within 1600 km of the same region, and local pump price x fixed FX for self-drive; all labelled as estimates.'],
    ],
  };

  function showModeNotice(modeName) {
    const rows = (isZh() ? MODE_DIFF.zh : MODE_DIFF.en)
      .map(([k, v]) => `<li><b>${esc(k)}</b><span>${esc(v)}</span></li>`).join('');
    const title = modeName === 'global'
      ? zh('Switched to global mode', '已切换到国际版')
      : zh('Switched to China mode', '已切换到国内版');
    let box = document.getElementById('modeNotice');
    if (!box) {
      box = document.createElement('div');
      box.id = 'modeNotice';
      box.className = 'mode-notice-mask';
      document.body.appendChild(box);
    }
    box.innerHTML = `<div class="mode-notice" role="dialog" aria-modal="true">
      <h3>${esc(title)}</h3>
      <p class="mn-lead">${zh('The two modes differ in data source, coverage and estimates:', '两个版本在数据来源、覆盖范围与估算口径上不同：')}</p>
      <ul>${rows}</ul>
      <button class="btn primary" id="modeNoticeOk">${zh('Got it', '知道了')}</button>
    </div>`;
    box.classList.add('open');
    const ok = document.getElementById('modeNoticeOk');
    ok.addEventListener('click', () => box.classList.remove('open'));
  }

  async function applyMode(next) {
    if (next === state.mode) return;
    API.setMode(next);
    state.mode = next;
    document.querySelectorAll('#modeSwitch button').forEach((b) => b.classList.toggle('on', b.dataset.mode === next));
    state.city = '';
    state.cmp.attrs.clear(); state.cmp.hotels.clear();
    showModeNotice(next);
    // 先重建地图，再加载数据：切换后地图应立即变成对应模式的底图
    if (state.map) {
      try { if (state.map.destroy) state.map.destroy(); } catch (e) {}
      // 换一个干净的容器节点：旧示意图实例绑在 window 上的监听不会再把 SVG 画回来
      const oldCanvas = $('#mapCanvas');
      if (oldCanvas && oldCanvas.parentNode) {
        const fresh = oldCanvas.cloneNode(false);
        fresh.innerHTML = '';
        oldCanvas.parentNode.replaceChild(fresh, oldCanvas);
      }
      state.map = null;
    }
    initMap();
    try {
      const meta = await API.meta();
      state.meta = meta;
      renderMeta(meta);
      const cities = meta.cities || [];
      const first = cities.find((c) => (c.count || 0) > 0) || cities[0];
      state.city = first ? first.city : '';
      $$('#cityChips .chip').forEach((c) => c.classList.toggle('on', c.dataset.city === state.city));
      $$('#sideCities .side-city').forEach((c) => c.classList.toggle('sc-on', c.dataset.scity === state.city));
      await Promise.all([loadAttractions(true), loadHotels(true)]);
      randomHeroTip();
      loadSources();
      if (next === 'cn' && state.config) updateMapNote(state.config);
    } catch (err) {
      toast('Mode switch failed: ' + err.message, 'err');
    }
  }

  async function init() {
    if (API.isFileMode()) {
      // When opened as file://, browsers block local fetch; show startup instructions first
      $('#fileGuard').hidden = false;
      return;
    }
    bindGlobal();
    try {
      const [config, meta] = await Promise.all([API.config(), API.meta()]);
      state.config = config; state.meta = meta;
      document.querySelectorAll('#modeSwitch button').forEach((b) => b.classList.toggle('on', b.dataset.mode === state.mode));
      renderMeta(meta);
      randomHeroTip();
      // Focus the busiest city by default to avoid cross-city lists and very long routes
      const cities = meta.cities || [];
      const firstReady = cities.find((c) => c.count > 0) || cities[0];
      if (firstReady && firstReady.city) {
        state.city = firstReady.city;
        $$('#cityChips .chip').forEach((c) => c.classList.toggle('on', c.dataset.city === state.city));
        $$('#sideCities .side-city').forEach((c) => c.classList.toggle('on', c.dataset.scity === state.city));
      }
      updateMapNote(config);
      $('#planProviderNote').innerHTML = config.server_ak_configured
        ? 'Baidu server AK detected: routes use live Baidu routing with per-leg navigation and traffic.'
        : 'No Baidu server AK: routes use local optimisation (nearest neighbour + 2-opt) and a road factor, labelled as estimates.';
    } catch (err) {
      toast('Initialization failed: ' + err.message, 'err');
    }
    await Promise.all([loadAttractions(true), loadHotels(true)]);
    loadSources();
    initMap();
    initScrollSpy();
    // 预填城际交通的出发/到达城市：默认用行程首个地点所在城市
    const tFrom = $('#transportFrom');
    const tTo = $('#transportTo');
    if (tFrom && !tFrom.value) tFrom.value = localStorage.getItem('travelone.homeCity') || '北京';
    if (tTo && !tTo.value && state.city) tTo.value = state.city;
    const saved = localStorage.getItem('travelone.tripId');
    if (saved) { state.tripId = Number(saved); refreshTrip().catch(() => { state.tripId = null; localStorage.removeItem('travelone.tripId'); }); }
    renderComparePickers();
    document.addEventListener('travelone:lang', () => {
      randomHeroTip();
      if (state.meta) renderMeta(state.meta);
      const nearAll = $('#nearAll');
      if (nearAll) {
        const full = nearAll.dataset.full === '1';
        nearAll.querySelector('span').textContent = full
          ? (isZh() ? `已加载 ${state.nearOptions.length} 个景点（点击收起）` : `Loaded ${state.nearOptions.length} attractions (click to collapse)`)
          : (isZh() ? '加载本城市全部景点' : 'Load all attractions in this city');
      }
      // 字号按钮文案随语言走（大字状态在大字模式下显示“标准”）
      applyFontMode(document.documentElement.dataset.font === 'large' ? 'large' : 'normal');
      renderAttractions();
      renderHotels();
      renderComparePickers();
      updateFilterSummary();
      updateHotelSummary();
      // 已展开的面板要跟着换语言：平台来源、比价结果、城际交通
      if (state.platformRows.length) renderPlatforms(state.platformRows);
      if (state.cmp.data) renderCompareData(state.cmp.data);
      if (state.transport.result) renderTransport();
      const srcMeta = $('#sourceMeta');
      // 语言切换后详情弹窗按新语言重渲染，避免残留另一种语言
      const view = state.detailView;
      if (view && $('#detailMask') && $('#detailMask').classList.contains('open')) {
        const modal = $('#detailModal');
        const scrollTop = modal.scrollTop;
        modal.innerHTML = view.kind === 'hotel' ? hotelDetailHtml(view.vm) : attrDetailHtml(view.vm);
        bindDetail(view.vm, view.kind);
        modal.scrollTop = scrollTop;
      }
    });
    applyDeepLink();
    // First paint uses a quick fetch; counts update silently after the background sweep
    setTimeout(async () => {
      try {
        const fresh = await API.meta();
        const before = (state.meta && state.meta.counts) || {};
        state.meta = fresh;
        renderMeta(fresh);
        if ((fresh.counts.attractions || 0) > (before.attractions || 0)) {
          toast(`Background sweep completed: ${fresh.counts.attractions} attractions · ${fresh.counts.hotels} hotels`, 'ok');
        }
      } catch (e) { /* silent */ }
    }, 30000);
  }

  // Deep links: #detail=<key> / #hotel=<id> / #map=1 / #section=<id>
  function applyDeepLink() {
    const hash = decodeURIComponent((location.hash || '').replace(/^#/, ''));
    if (!hash) return;
    const params = new URLSearchParams(hash.replace(/&/g, '&'));
    const detail = params.get('detail');
    const hotel = params.get('hotel');
    if (detail) { openAttrDetail(detail); return; }
    if (hotel) { openHotelDetail(hotel); return; }
    if (params.get('font') === 'large') applyFontMode('large');
    if (params.get('font') === 'normal') applyFontMode('normal');
    if (params.get('map') === '1') $('#mapPanel').classList.add('open');
    const section = params.get('section');
    if (section) {
      // Scroll after lists render so layout shifts do not move the anchor
      [300, 900].forEach((delay) => setTimeout(() => {
        const el = document.getElementById(section);
        if (el) el.scrollIntoView({ behavior: 'auto', block: 'start' });
      }, delay));
    }
  }

  /* Collapsible chip rows: default shows `limit`, a toggle reveals the rest. */
  function limitChips(selector, limit, moreLabel, lessLabel, itemClass) {
    const box = $(selector);
    if (!box) return;
    const cls = itemClass || 'chip';
    const oldBtn = box.parentNode && box.parentNode.querySelector('[data-chips-toggle="' + selector + '"]');
    if (oldBtn) oldBtn.remove();
    const chips = Array.from(box.children).filter((c) => c.classList.contains(cls));
    if (chips.length <= limit) {
      box.classList.remove('clamped', 'expanded');
      chips.forEach((c) => c.classList.remove('chip-extra'));
      return;
    }
    chips.forEach((c, i) => c.classList.toggle('chip-extra', i >= limit));
    box.classList.add('clamped');
    box.classList.remove('expanded');
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chips-toggle';
    btn.dataset.chipsToggle = selector;
    const label = () => moreLabel.replace('{n}', chips.length);
    btn.innerHTML = `<span>${label()}</span><i class="chev">▾</i>`;
    btn.addEventListener('click', () => {
      const on = box.classList.toggle('expanded');
      btn.classList.toggle('on', on);
      btn.querySelector('span').textContent = on ? lessLabel : label();
    });
    box.insertAdjacentElement('afterend', btn);
  }

  function applyChipLimits() {
    const zh = isZh();
    limitChips('#cityChips', 10, zh ? '展开全部 {n} 个城市' : 'Show all {n} cities', zh ? '收起城市' : 'Show fewer');
    limitChips('#tagChips', 8, zh ? '展开全部 {n} 个标签' : 'Show all {n} tags', zh ? '收起标签' : 'Show fewer');
    limitChips('#starChips', 4, zh ? '更多星级' : 'More star levels', zh ? '收起星级' : 'Fewer levels');
    limitChips('#levelChips', 4, zh ? '更多等级' : 'More A-levels', zh ? '收起等级' : 'Fewer levels');
    limitChips('#sideCities', 10, zh ? '展开全部 {n} 个城市' : 'Show all {n} cities', zh ? '收起' : 'Show fewer', 'side-city');
  }

  function renderMeta(meta) {
    const c = meta.counts || {};
    $('#statAttractions').textContent = c.attractions || 0;
    $('#statHotels').textContent = c.hotels || 0;
    $('#statMetros').textContent = (c.metros !== undefined ? c.metros : (c.metro || 0));
    $('#statCities').textContent = (meta.cities || []).length || c.cities || 0;
    $('#statInterval').textContent = Math.round((meta.interval_seconds || 300) / 60) + ' min';
    $('#sideAttractions').textContent = c.attractions || 0;
    $('#sideHotels').textContent = c.hotels || 0;
    $('#sideMetros').textContent = (c.metros !== undefined ? c.metros : (c.metro || 0));
    $('#sideInterval').textContent = Math.round((meta.interval_seconds || 300) / 60) + ' min';
    // 国际版：数据源不含价格/评分/标签，相关筛选隐藏并给出说明；百度 AK 指南同步隐藏
    const globalMode = state.mode === 'global';
    document.body.classList.toggle('mode-global', globalMode);
    const intlNote = $('#intlFilterNote');
    if (intlNote) intlNote.hidden = !globalMode;
    const intlHotelNote = $('#intlHotelFilterNote');
    if (intlHotelNote) intlHotelNote.hidden = !globalMode;

    $('#cityChips').innerHTML = `<button class="chip on" data-city="">All<small>${c.attractions || ''}</small></button>` +
      (meta.cities || []).map((x) => `<button class="chip" data-city="${esc(x.city)}">${esc(isZh() ? x.city : (x.city_en || x.city))}<small>${x.count}</small></button>`).join('');
    $('#sideCities').innerHTML = `<button class="side-city on" data-scity="">All</button>` +
      (meta.cities || []).map((x) => `<button class="side-city" data-scity="${esc(x.city)}">${esc(isZh() ? x.city : (x.city_en || x.city))}</button>`).join('');
    $('#levelChips').innerHTML = (meta.levels || []).map((l) => `<button class="chip" data-level="${esc(l)}">${esc(l)}</button>`).join('') || '<span style="font-size:12px;color:#7c9099">No A-level data</span>';
    $('#tagChips').innerHTML = (meta.tags || []).map((t) => `<button class="chip" data-tag="${esc(t)}">${esc(isZh() ? t : ((meta.tag_en || {})[t] || t))}</button>`).join('');
    applyChipLimits();

    // Price inputs follow the actual dataset range and update as items change
    const bounds = meta.bounds || {};
    const ab = bounds.attractions;
    if (ab) {
      $('#minPrice').placeholder = `Min ¥${ab.price_min}`;
      $('#maxPrice').placeholder = `Max ¥${ab.price_max}`;
      $('#minPrice').min = Math.floor(ab.price_min || 0);
      $('#maxPrice').max = Math.ceil(ab.price_max || 0);
      const note = document.querySelector('#attrFilterSummary');
      if (note) note.dataset.range = `${ab.price_min}-${ab.price_max}`;
    }
    const hb = bounds.hotels;
    if (hb) {
      $('#hotelMinPrice').placeholder = `Min ¥${hb.price_min}`;
      $('#hotelMaxPrice').placeholder = `Max ¥${hb.price_max}`;
      $('#hotelMinPrice').min = Math.floor(hb.price_min || 0);
      $('#hotelMaxPrice').max = Math.ceil(hb.price_max || 0);
    }
  }

  function updateMapNote(config) {
    if (config.map_enabled) $('#mapNote').textContent = 'Baidu Maps · live basemap and geolocation';
    else $('#mapNote').textContent = 'Offline schematic map · no AK configured';
  }

  /* ============================ Map ============================ */
  async function initMap() {
    const seq = (state.mapSeq || 0) + 1;
    state.mapSeq = seq;
    const result = await TravelMap.create($('#mapCanvas'), {
      mode: state.mode,
      ak: state.config && state.config.baidu_js_ak,
      onMarkerClick: (key) => { const [kind, id] = String(key).split('|'); kind === 'hotel' ? openHotelDetail(id) : openAttrDetail(id); },
      onMapClick: (p) => { state.origin = Object.assign({ name: 'Pick on map' }, p); toast('Origin selected'); },
    });
    if (seq !== state.mapSeq) {
      // 期间又切换过模式，这次创建的实例作废，避免两套地图互相覆盖
      try { if (result.map && result.map.destroy) result.map.destroy(); } catch (e) {}
      return;
    }
    state.map = result.map;
    state.mapMode = result.mode;
    if (result.mode === 'offline' && result.error) {
      const note = $('#mapNote');
      if (note) note.textContent = state.mode === 'global'
        ? '国际版地图：MapLibre 加载失败（' + result.error + '），已降级为离线示意图'
        : 'Baidu Maps failed to load (' + result.error + '), switched to the offline schematic map';
    } else if (result.mode === 'maplibre' && $('#mapNote')) {
      $('#mapNote').textContent = '国际版地图：MapLibre + OpenStreetMap（© OpenStreetMap contributors）';
    }
    refreshMapMarkers();
  }

  function refreshMapMarkers() {
    if (!state.map) return;
    if (state.plan) return;
    const markers = [];
    // Limit markers per view so labels do not overlap on small maps
    state.attr.items.slice(0, 10).forEach((i) => {
      if (i.lat && i.lng) markers.push({ key: 'attr|' + i.key, name: i.name, lat: i.lat, lng: i.lng, kind: 'attr' });
    });
    state.hotel.items.slice(0, 6).forEach((h) => {
      if (h.lat && h.lng) markers.push({ key: 'hotel|' + h.id, name: h.name, lat: h.lat, lng: h.lng, kind: 'hotel' });
    });
    state.map.setMarkers(markers);
    if (markers.length) state.map.fit();
  }

  /* ============================ Attractions ============================ */
  async function loadAttractions(reset) {
    if (reset) { state.attr.page = 1; state.attr.items = []; }
    if (reset) $('#grid').innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';
    const a = state.attr;
    const params = {
      keyword: state.keyword, city: state.city,
      min_rating: a.minRating || '', min_price: a.minPrice, max_price: a.maxPrice,
      tags: a.tags.join(','), level: a.level,
      free: a.flags.has('free') ? 1 : '',
      sort: a.sort === 'distance' && !state.origin && !a.anchor ? 'recommend' : a.sort,
      page: a.page, page_size: a.size,
    };
    if (a.near && state.origin) { params.lat = state.origin.lat; params.lng = state.origin.lng; params.max_distance = 30; }
    if (a.anchor) { params.lat = a.anchor.lat; params.lng = a.anchor.lng; params.max_distance = 20; }
    const seq = ++a.seq;
    try {
      const data = await API.attractions(params);
      if (seq !== a.seq) return;
      a.total = data.total;
      const filtered = data.items.filter((i) => {
        if (a.flags.has('night') && !i.night_open) return false;
        if (a.flags.has('indoor') && !i.indoor) return false;
        if (a.flags.has('nature') && !i.nature) return false;
        return true;
      });
      a.items = reset ? filtered : a.items.concat(filtered);
      renderAttractions();
      refreshMapMarkers();
      $('#attrMeta').innerHTML = `${data.total} attractions · page ${a.page} ` + sourceChip(data);
      $('#attrMore').style.display = a.items.length < data.total ? 'inline-flex' : 'none';
      updateFilterSummary();
      renderComparePickers();
      if (reset) populateNearAttractionSelect();
    } catch (err) {
      $('#grid').innerHTML = `<div class="empty"><b>Failed to load</b>${esc(err.message)}</div>`;
    }
  }

  function updateFilterSummary() {
    const a = state.attr, parts = [];
    if (state.city) parts.push(cityLabel(state.city));
    if (a.minRating) parts.push(a.minRating + '+ rating');
    if (a.minPrice || a.maxPrice) parts.push(`¥${a.minPrice || 0}-${a.maxPrice || '∞'}`);
    if (a.level) parts.push(a.level);
    if (a.tags.length) parts.push(a.tags.map((t) => ((state.meta && state.meta.tag_en) || {})[t] || t).join(' / '));
    a.flags.forEach((f) => parts.push({ night: 'Night', indoor: 'Indoor', nature: 'Nature', free: 'Free' }[f]));
    if (a.near) parts.push('Within 30 km');
    $('#attrFilterSummary').textContent = parts.length ? parts.join(' · ') : 'All attractions';
  }

  function renderAttractions() {
    const grid = $('#grid');
    if (!state.attr.items.length) {
      grid.innerHTML = `<div class="empty"><b>No attractions match</b>Try wider price or rating ranges, or clear tags</div>`;
      return;
    }
    grid.innerHTML = state.attr.items.map((i) => {
      const cover = i.cover_image || API.cover(i.name, i.city);
      const dist = state.origin ? distanceKm(state.origin, i)
        : (i.distance_km !== undefined && i.distance_km !== null ? Number(i.distance_km) : null);
      const badges = [
        i.level ? `<span class="badge level">${esc(i.level)}</span>` : '',
        i.is_free ? '<span class="badge free">Free</span>' : '',
        (i.popularity || 0) > 80 ? '<span class="badge hot">Popular</span>' : '',
      ].join('');
      const tags = tagDisplay(i).slice(0, 3).map((t) => `<span class="tag">${esc(t)}</span>`).join('');
      const offers = i.offers || [];
      const bestOffer = offers.slice().sort((x, y) => x.price - y.price)[0];
      return `<article class="card" data-attr="${esc(i.key)}">
        <div class="card-media">
          <img src="${cover}" alt="${esc(i.name)}" Loading="lazy" onerror="this.onerror=null;this.src='${API.cover(i.name, i.city)}'">
          <div class="card-badges">${badges}</div>
          <div class="card-bottom">
            <div class="price">${i.price === null || i.price === undefined ? '<span style="font-size:13px">Price pending</span>' : money(i.price) + (i.price ? '<small>from</small>' : '')}${i.original_price && i.price && i.original_price > i.price ? `<s>¥${Number(i.original_price).toFixed(0)}</s>` : ''}</div>
            <div class="score-chip">★ ${(Number(i.rating) || 0).toFixed(1)}</div>
          </div>
        </div>
        <div class="card-body">
          <div class="card-name">${esc(i.name)}</div>
          <div class="card-meta">
            <span>${esc(cityDisplay(i))}</span>
            <span class="dot">${(i.review_count || 0).toLocaleString()} reviews</span>
            ${dist !== null ? `<span class="dot">${zh(km(dist) + ' away', '距此 ' + km(dist))}</span>` : ''}
          </div>
          <div class="card-tags">${tags}</div>
          <div class="mini-facts">
            ${offers.length ? `<span class="fact">${offers.length} ${offers.length === 1 ? 'quote' : 'quotes'} · lowest <b>${money(bestOffer ? bestOffer.price : i.price)}</b></span>` : ''}
            ${i.night_open ? '<span class="fact">Night tours</span>' : ''}
            ${i.indoor ? '<span class="fact">Indoor</span>' : ''}
          </div>
        </div>
        <div class="card-actions">
          <button class="btn sm" data-attr-detail="${esc(i.key)}">Details</button>
          <button class="btn sm primary" data-attr-add="${esc(i.key)}">Add to trip</button>
        </div>
      </article>`;
    }).join('');
  }

  /* ============================ Hotels ============================ */
  async function loadHotels(reset) {
    if (reset) { state.hotel.page = 1; state.hotel.items = []; }
    if (reset) $('#hotelGrid').innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';
    const h = state.hotel;
    const params = {
      keyword: state.keyword, city: state.city,
      min_price: h.minPrice, max_price: h.maxPrice,
      min_star: h.star || '', min_rating: h.rating || '',
      max_metro: h.metro || '', near: h.nearKey,
      max_distance: h.near ? h.near : '',
      sort: h.sort, page: h.page, page_size: h.size,
    };
    const seq = ++h.seq;
    try {
      const data = await API.hotels(params);
      if (seq !== h.seq) return;
      h.total = data.total;
      h.items = reset ? data.items : h.items.concat(data.items);
      renderHotels();
      refreshMapMarkers();
      $('#hotelMeta').innerHTML = `${data.total} hotels` + (data.near ? ` · near ${data.near.name}` : '') + ' ' + sourceChip(data);
      $('#hotelMore').style.display = h.items.length < data.total ? 'inline-flex' : 'none';
      updateHotelSummary();
      renderComparePickers();
    } catch (err) {
      $('#hotelGrid').innerHTML = `<div class="empty"><b>Failed to load hotels</b>${esc(err.message)}</div>`;
    }
  }

  function updateHotelSummary() {
    const h = state.hotel, parts = [];
    if (state.city) parts.push(cityLabel(state.city));
    if (h.minPrice || h.maxPrice) parts.push(`¥${h.minPrice || 0}-${h.maxPrice || '∞'}`);
    if (h.star) parts.push(zh(h.star + ' stars and up', h.star + ' 星及以上'));
    if (h.rating) parts.push(h.rating + '+ rating');
    if (h.metro) parts.push(`Metro within ${h.metro} m`);
    if (h.near) parts.push(`Within ${h.near} km`);
    $('#hotelFilterSummary').textContent = parts.length ? parts.join(' · ') : 'All hotels';
  }

  function renderHotels() {
    const grid = $('#hotelGrid');
    if (!state.hotel.items.length) {
      grid.innerHTML = `<div class="empty"><b>No hotels match</b>Try wider price, star or distance ranges</div>`;
      return;
    }
    grid.innerHTML = state.hotel.items.map((h) => {
      const photo = (h.photos && h.photos.length ? h.photos[0] : (h.images && h.images.length ? h.images[0] : ''));
      const cover = photo || h.cover_image || API.cover(h.name, h.city, 5);
      const offers = h.offers || [];
      const best = offers.slice().sort((x, y) => x.price - y.price)[0];
      const tags = tagDisplay(h).slice(0, 3).map((t) => `<span class="tag hotel">${esc(t)}</span>`).join('');
      return `<article class="card hotel" data-hotel="${esc(h.id)}">
        <div class="card-media">
          <img src="${cover}" alt="${esc(h.name)}" Loading="lazy" onerror="this.onerror=null;this.src='${API.cover(h.name, h.city, 5)}'">
          <div class="card-badges"><span class="badge star">${h.star}-star</span></div>
          <div class="card-bottom">
            <div class="price">${h.price === null || h.price === undefined ? '<span style="font-size:13px">Rate pending</span>' : money(h.price) + '<small>/night from</small>'}${h.original_price > h.price ? `<s>¥${Number(h.original_price).toFixed(0)}</s>` : ''}</div>
            <div class="score-chip hotel">★ ${(Number(h.rating) || 0).toFixed(1)}</div>
          </div>
        </div>
        <div class="card-body">
          <div class="card-name">${esc(h.name)}</div>
          <div class="card-meta">
            <span>${esc(cityDisplay(h))}</span>
            <span class="dot">${(h.review_count || 0).toLocaleString()} reviews</span>
          </div>
          <div class="card-tags">${tags}</div>
          <div class="mini-facts">
            ${h.distance_to_attraction_km !== undefined ? `<span class="fact">To reference attraction <b>${km(h.distance_to_attraction_km)}</b></span>` : ''}
            ${h.metro_station ? `<span class="fact metro">🚇 ${esc(h.metro_station)} · ${h.metro_distance_m || '—'} m walk</span>` : '<span class="fact">🚇 No nearby metro</span>'}
            ${offers.length ? `<span class="fact">${offers.length} ${offers.length === 1 ? 'quote' : 'quotes'} · lowest <b>${money(best ? best.price : h.price)}</b></span>` : ''}
            ${h.price && h.price_source ? `<span class="fact src">${zh('Price from ', '报价来源 ')}${esc(isZh() ? (h.price_source_zh || h.price_source) : (h.price_source_en || h.price_source))}</span>` : ''}
          </div>
        </div>
        <div class="card-actions">
          <button class="btn sm" data-hotel-detail="${esc(h.id)}">Details</button>
          <button class="btn sm gold" data-hotel-add="${esc(h.id)}">Add as stay</button>
        </div>
      </article>`;
    }).join('');
  }

  function fillNearOptions(rows) {
    const select = $('#nearAttraction');
    if (!select) return;
    const current = select.value || state.hotel.nearKey;
    select.innerHTML = '<option value="">Reference attraction (auto)</option>' +
      rows.map((i) => `<option value="${esc(i.key || '')}">${esc(i.name)}${i.city ? ' (' + esc(i.city) + ')' : ''}</option>`).join('');
    if (current && rows.some((i) => (i.key || '') === current)) select.value = current;
  }

  function populateNearAttractionSelect() {
    const select = $('#nearAttraction');
    if (!select) return;
    const items = state.attr.items.slice(0, 30);
    state.nearOptions = items.slice();
    fillNearOptions(items);
    const known = items.some((i) => (i.key || '') === state.hotel.nearKey);
    if (!known && items.length) {
      state.hotel.nearKey = items[0].key;
      select.value = state.hotel.nearKey;
      loadHotels(true);
    } else if (known) {
      select.value = state.hotel.nearKey;
    }
    const btn = $('#nearAll');
    if (btn) btn.dataset.full = '';
  }

  async function loadAllNearAttractions() {
    const btn = $('#nearAll');
    if (!btn) return;
    if (btn.dataset.full === '1') {
      // toggle back to the first page of options
      state.nearOptions = state.attr.items.slice(0, 30);
      fillNearOptions(state.nearOptions);
      btn.dataset.full = '';
      btn.querySelector('span').textContent = isZh() ? '加载本城市全部景点' : 'Load all attractions in this city';
      return;
    }
    const original = btn.querySelector('span').textContent;
    btn.querySelector('span').textContent = isZh() ? '正在加载…' : 'Loading…';
    try {
      const collected = [];
      const seen = new Set();
      for (let page = 1; page <= 4; page += 1) {
        const data = await API.attractions({ city: state.city, page, page_size: 60, sort: 'recommend' });
        (data.items || []).forEach((it) => {
          const key = it.key || it.name;
          if (!key || seen.has(key)) return;
          seen.add(key);
          collected.push(it);
        });
        if (collected.length >= (data.total || 0) || (data.items || []).length < 60) break;
      }
      if (!collected.length) { btn.querySelector('span').textContent = original; toast('No attractions for this city yet', 'err'); return; }
      state.nearOptions = collected;
      fillNearOptions(collected);
      btn.dataset.full = '1';
      btn.querySelector('span').textContent = isZh() ? `已加载 ${collected.length} 个景点（点击收起）` : `Loaded ${collected.length} attractions (click to collapse)`;
      toast(`${collected.length} reference attractions available`, 'ok');
    } catch (err) {
      btn.querySelector('span').textContent = original;
      toast('Could not load attractions: ' + err.message, 'err');
    }
  }

/* ============================ Detail templates ============================ */
  // Shared template idea: normalise every record to a defaulted structure, then render that structure,
  // so price swings, added items and rating changes never require page code changes.
  function priceStats(offers, base) {
    const prices = (offers || []).map((o) => Number(o.price)).filter((v) => isFinite(v) && v >= 0);
    if (!(offers || []).length && isFinite(Number(base)) && Number(base) > 0) prices.push(Number(base));
    if (!prices.length) return { count: 0, min: null, max: null, spread: 0, avg: null, volatility_pct: 0, best_platform: '' };
    const min = Math.min.apply(null, prices);
    const max = Math.max.apply(null, prices);
    const best = (offers || []).find((o) => Number(o.price) === min) || {};
    return {
      count: prices.length, min: min, max: max, spread: Number((max - min).toFixed(2)),
      avg: Number((prices.reduce((a, b) => a + b, 0) / prices.length).toFixed(2)),
      volatility_pct: min ? Number(((max - min) / min * 100).toFixed(1)) : 0,
      best_platform: best.platform || '',
    };
  }

  function normalizeAttr(item) {
    const vm = Object.assign({}, item);
    vm.kind = 'attraction';
    vm.gallery = (item.gallery || item.photos || (item.cover_image ? [item.cover_image] : [])).filter(Boolean);
    if (!vm.gallery.length) vm.gallery = [API.cover(item.name, item.city)];
    vm.offers = item.offers || [];
    vm.ticket_types = item.ticket_types || [];
    vm.tags = tagDisplay(item);
    vm.price = item.price === undefined ? null : item.price;
    vm.rating = item.rating === undefined ? null : Number(item.rating);
    vm.review_count = Number(item.review_count || 0);
    const policy = item.policy || {};
    vm.policy = {
      free: policy.free || 'Subject to the venue notice on the day',
      discount: policy.discount || 'Subject to the venue notice on the day',
      booking: policy.booking || 'Advance real-name booking on official channels is recommended',
      refund: policy.refund || 'Subject to the venue refund policy',
    };
    // 中文政策：优先用接口返回的中文原文，其次用本地中文默认值，
    // 保证详情还没拉到时（本地列表先行渲染）也不会露出英文。
    vm.policy_zh = Object.assign({
      free: '免票政策以景区当日公告为准',
      discount: '优惠条件以景区当日公告为准',
      booking: '建议通过官方渠道提前实名预约',
      refund: '退改以景区规定为准',
    }, item.policy_zh || {});
    vm.priceStats = item.price_stats || priceStats(vm.offers, vm.price);
    vm.nearbyHotels = item.nearby_hotels || [];
    vm.similar = item.similar || [];
    vm.has = Object.assign({
      gallery: vm.gallery.length > 0, offers: vm.offers.length > 0, tickets: vm.ticket_types.length > 0,
      metro: !!item.nearest_metro, hotels: vm.nearbyHotels.length > 0, similar: vm.similar.length > 0,
    }, item.has || {});
    return vm;
  }

  function normalizeHotel(item) {
    const vm = Object.assign({}, item);
    vm.kind = 'hotel';
    vm.gallery = (item.gallery || (item.cover_image ? [item.cover_image] : [])).filter(Boolean);
    if (!vm.gallery.length) vm.gallery = [API.cover(item.name, item.city, 5)];
    vm.offers = item.offers || [];
    vm.tags = tagDisplay(item);
    vm.star = Number(item.star || 3);
    vm.rating = item.rating === undefined ? null : Number(item.rating);
    vm.review_count = Number(item.review_count || 0);
    vm.price = item.price === undefined ? null : item.price;
    const policy = item.policy || {};
    vm.policy = {
      checkin: policy.checkin || 'Check-in after 14:00, check-out before 12:00 next day',
      cancel: policy.cancel || 'Subject to the booking platform policy',
      child: policy.child || 'Child policy: confirm with the hotel front desk',
    };
    vm.policy_zh = Object.assign({
      checkin: '14:00 后入住，次日 12:00 前退房',
      cancel: '以预订平台退改规则为准',
      child: '儿童政策请与酒店前台确认',
    }, item.policy_zh || {});
    vm.priceStats = item.price_stats || priceStats(vm.offers, vm.price);
    vm.platform_ratings = item.platform_ratings || [];
    vm.nearbyAttractions = item.nearby_attractions || [];
    vm.has = Object.assign({
      gallery: vm.gallery.length > 0, offers: vm.offers.length > 0,
      metro: item.metro_distance_m !== undefined && item.metro_distance_m !== null,
      nearby: vm.nearbyAttractions.length > 0,
    }, item.has || {});
    return vm;
  }

  function emptyBlock(text) {
    return `<div class="tpl-empty">${esc(text)}</div>`;
  }

  // Detail-page bilingual helpers: pick the Chinese field when the UI is Chinese,
  // falling back to the English one so a missing translation never blanks a field.
  const zh = (en, cn) => (isZh() ? (cn || en) : en);
  function policyText(vm, key, kind) {
    const zhPolicy = (vm && vm.policy_zh) || {};
    const enPolicy = (vm && vm.policy) || {};
    if (isZh()) return zhPolicy[key] || enPolicy[key] || '';
    return enPolicy[key] || zhPolicy[key] || '';
  }
  function factsHtml(rows) {
    return `<div class="detail-facts">${rows.filter((r) => r && r[1] !== undefined)
      .map(([label, value]) => `<div><span>${esc(label)}</span><b>${esc(value)}</b></div>`).join('')}</div>`;
  }

  function introText(vm) {
    if (!isZh()) {
      const en = vm.intro || '';
      // 英文模式下若简介里还混着中文（旧快照/上游中文标签），用英文城市与标签重建
      if (en && !/[一-鿿]/.test(en)) return en;
      const parts = [vm.city_en || vm.city, (vm.tags_en || []).slice(0, 2).join(', '), vm.address].filter(Boolean);
      return parts.length ? parts.join(' · ') : (vm.intro_zh || en);
    }
    if (vm.intro_zh) return vm.intro_zh;
    // 本地列表数据可能还没有中文简介：用中文城市/标签/地址临时拼一句
    const parts = [vm.city || vm.city_en, (vm.tags || []).slice(0, 2).join('、'), vm.address].filter(Boolean);
    return parts.length ? parts.join(' · ') : (vm.intro || '');
  }

  function sourceLabel(vm) {
    const raw = String((vm && (vm.source_label || '')) || '');
    if (!isZh() || !raw) return raw;
    if (vm.source === 'cache') {
      const at = raw.replace(/^Cached · last fetch\s*/, '');
      return at ? '上次抓取 · ' + at : '上次抓取存档';
    }
    return raw.replace(/^Live · /, '实时 · ');
  }

  function priceRangeHtml(stats) {
    if (!stats || stats.min === null) return emptyBlock('No price yet for this item; quotes appear here as soon as a source provides them.');
    const lowest = zh(`Lowest ${money(stats.min)}`, `最低 ${money(stats.min)}`);
    const highest = zh(`Highest ${money(stats.max)}`, `最高 ${money(stats.max)}`);
    const quotes = zh(`${stats.count} ${stats.count === 1 ? 'quote' : 'quotes'}`,
      `${stats.count} 个报价`);
    const spread = zh(`Spread ${money(stats.spread)}`, `价差 ${money(stats.spread)}`);
    const vol = zh(`Volatility ${stats.volatility_pct}%`, `波动 ${stats.volatility_pct}%`);
    return `<div class="price-range-bar">
      <span>${lowest}</span>
      <div class="bar"><i style="left:0"></i></div>
      <span>${highest}</span>
      <span class="badge-soft">${quotes}</span>
      ${stats.spread ? `<span class="badge-soft">${spread}</span>` : ''}
      ${stats.volatility_pct ? `<span class="badge-soft">${vol}</span>` : ''}
    </div>`;
  }

  function offersHtml(offers, best, specLabel, specLabelZh) {
    if (!offers || !offers.length) {
      return emptyBlock(zh('No channel quotes yet. They fill in automatically once a source returns a price.',
        '暂无渠道报价，来源返回价格后会自动补上。'));
    }
    return `<div class="offer-list">${offers.map((o, idx) => {
      const specs = Array.isArray(o.specs) ? o.specs : [];
      const label = isZh() ? (o.spec_label_zh || specLabelZh || '选项') : (o.spec_label || specLabel || 'Options');
      const specRows = specs.length
        ? specs.map((sp) => `<div class="spec-row">
            <span class="spec-name">${esc((isZh() ? (sp.name_zh || sp.name) : (sp.name || sp.name_zh)) || zh('Option', '选项'))}</span>
            <span class="spec-note">${esc((isZh() ? (sp.note_zh || sp.note) : (sp.note || sp.note_zh)) || '')}</span>
            <span class="spec-price">${money(sp.price)}</span>
          </div>`).join('')
        : emptyBlock(zh(`No ${label} details from this channel yet; they appear when a source provides them.`,
          `该渠道暂无${label}明细，获取到后会自动显示。`));
      const note = isZh() ? (o.note_zh || o.note || '') : (o.note || o.note_zh || '');
      const cancel = o.cancel ? ' · ' + esc(o.cancel) : '';
      const refTag = o.is_reference ? zh(' · list price', ' · 门市价') : '';
      const lowestTag = Number(o.price) === Number(best) ? zh(' · lowest', ' · 最低') : '';
      const listPrice = o.original_price ? zh('List ¥' + Number(o.original_price).toFixed(0), '门市 ¥' + Number(o.original_price).toFixed(0)) : '';
      return `<details class="offer${Number(o.price) === Number(best) ? ' best' : ''}" data-offer="${idx}">
        <summary class="offer-head">
          <div class="offer-main">
            <div class="o-name">${esc((isZh() ? (o.platform_zh || o.platform) : (o.platform || o.platform_zh)) || zh('Channel', '渠道'))}${lowestTag}</div>
            <div class="o-meta">${esc(o.breakfast || note)}${cancel}${refTag}${specs.length ? ' · ' + specs.length + ' ' + esc(label) : ''}</div>
          </div>
          <div class="offer-price">
            <div class="o-price">${money(o.price)}<small>${listPrice ? ' ' + listPrice : ''}</small></div>
            <span class="chev">▾</span>
          </div>
        </summary>
        <div class="offer-specs">
          <div class="spec-head"><span>${esc(label)}</span><span>${zh('Notes', '说明')}</span><span>${zh('Channel price', '渠道价')}</span></div>
          ${specRows}
        </div>
      </details>`;
    }).join('')}</div>`;
  }

  // 详情标题与外部地图链接随模式切换：国际版没有百度坐标，改用 OSM 页面
  function detailTitle(vm) {
    return isZh() ? (vm.name || vm.name_en) : (vm.name_en || vm.name);
  }
  function detailMapLink(vm) {
    if (state.mode === 'global') {
      return `https://www.openstreetmap.org/?mlat=${vm.lat}&mlon=${vm.lng}#map=16/${vm.lat}/${vm.lng}`;
    }
    return `https://api.map.baidu.com/marker?location=${vm.lat},${vm.lng}&title=${encodeURIComponent(vm.name)}&content=${encodeURIComponent(vm.address || '')}&output=html&src=travelone`;
  }
  function detailMapLabel() {
    return state.mode === 'global' ? zh('Open in OpenStreetMap', '在 OpenStreetMap 中打开') : zh('Open in Baidu Maps', '在百度地图中打开');
  }

  function galleryHtml(vm) {
    return `<div class="detail-gallery">
      <img class="main-img" id="galleryMain" src="${vm.gallery[0]}" alt="${esc(vm.name)}"
           onerror="this.onerror=null;this.src='${API.cover(vm.name, vm.city, 1)}'">
      ${vm.gallery.length > 1 ? `<div class="thumbs">${vm.gallery.slice(0, 5).map((g, i) => `<img src="${g}" data-thumb="${i}" class="${i === 0 ? 'on' : ''}" alt="Photo ${i + 1}">`).join('')}</div>` : ''}
    </div>`;
  }

  function attrDetailHtml(vm) {
    const tickets = vm.ticket_types.map((t) => `<tr><td>${esc((isZh() ? (t.name_zh || t.name) : (t.name || t.name_zh)) || zh('Ticket type', '票种'))}</td><td style="color:#7c9099">${esc(isZh() ? (t.note_zh || t.note) : (t.note || t.note_zh) || '')}</td><td class="p">${money(t.price)}</td></tr>`).join('');
    const metro = vm.nearest_metro;
    const hotels = vm.nearbyHotels.map((h) => `
      <button class="nearby" data-near-hotel="${esc(h.id || h.source_id || '')}">
        <img src="${h.cover_image || API.cover(h.name, h.city, 5)}" alt="${esc(h.name)}" Loading="lazy">
        <div class="nb-main">
          <b>${esc(h.name)}</b>
          <span>${zh(Number(h.star || 3) + ' stars', Number(h.star || 3) + ' 星')} · ★ ${(Number(h.rating) || 0).toFixed(1)}</span>
          <span class="nb-price">${money(h.price)}${zh('/night', '/晚')} · ${zh(km(h.distance_to_attraction_km) + ' away', '距此 ' + km(h.distance_to_attraction_km))}</span>
        </div>
      </button>`).join('');
    const similar = vm.similar.map((s) => `
      <button class="nearby" data-similar="${esc(s.key)}">
        <img src="${s.cover_image || API.cover(s.name, s.city)}" alt="${esc(s.name)}" Loading="lazy">
        <div class="nb-main"><b>${esc(s.name)}</b><span>★ ${(Number(s.rating) || 0).toFixed(1)} · ${money(s.price)}</span></div>
      </button>`).join('');
    return `
      <button class="modal-close" data-close aria-label="Close">✕</button>
      <div class="detail-head">
        ${galleryHtml(vm)}
        <div class="detail-info">
          <h2 class="detail-name">${esc(detailTitle(vm))}${vm.heritage ? `<span class="badge heritage" title="${esc(vm.heritage.license || 'CC0')}">${zh('UNESCO World Heritage', '世界遗产')}</span>` : ''}</h2>
          ${vm.name_en_official ? `<div class="detail-alias">${isZh() ? '英文名 ' : ''}${esc(vm.name_en_official)}</div>` : ''}
          <div class="detail-sub"><span>${esc(cityDisplay(vm))} ${esc(vm.level || '')}</span><span>${esc(vm.address || zh('Address pending', '地址待补'))}</span>${vm.source_label ? `<span class="src-chip${vm.source === 'cache' ? ' cache' : ''}">${esc(sourceLabel(vm))}</span>` : ''}</div>
          <div class="detail-score">${starsHtml(vm.rating)}<span class="score-num">${vm.rating === null ? '—' : vm.rating.toFixed(1)}<small> / 5</small></span><span style="font-size:12px;color:#7c9099">${vm.has.rating ? zh(vm.review_count.toLocaleString() + ' reviews', vm.review_count.toLocaleString() + ' 条点评') : zh('No rating yet', '暂无评分')}</span></div>
          ${ratingSourcesHtml(vm)}
          <div class="detail-price"><b>${money(vm.price)}</b>${vm.original_price > vm.price ? `<s>¥${Number(vm.original_price).toFixed(0)}</s>` : ''}<span>${vm.has.offers ? zh(vm.priceStats.count + ' quotes · lowest ' + money(vm.priceStats.min), vm.priceStats.count + ' 个报价 · 最低 ' + money(vm.priceStats.min)) : zh('No quotes', '暂无报价')}</span></div>
          <div class="detail-actions">
            <button class="btn primary" data-attr-add="${esc(vm.key)}">${zh('Add to trip', '加入行程')}</button>
            <button class="btn" data-set-origin="${vm.lat},${vm.lng},${esc(vm.name)}">${zh('Set as origin', '设为出发点')}</button>
            <a class="btn" href="${detailMapLink(vm)}" target="_blank" rel="noopener">${detailMapLabel()}</a>
          </div>
          ${factsHtml([
            [zh('Ticket', '门票'), money(vm.price)],
            [zh('Rating', '评分'), vm.rating === null ? '—' : vm.rating.toFixed(1) + ' / 5'],
            [zh('Reviews', '点评'), vm.review_count ? vm.review_count.toLocaleString() : '—'],
            [zh('Quotes', '报价'), vm.priceStats.count ? vm.priceStats.count + zh('', ' 个') : '—'],
          ])}
        </div>
      </div>
      <div class="detail-body">
        <div><div class="block-title">${zh('About this attraction', '景点介绍')}</div><p class="detail-intro">${esc(introText(vm) || zh('No description yet; it appears when the source provides one.', '暂无简介，来源提供后会显示。'))}</p></div>
        <div>
          <div class="block-title">${zh('Price range', '价格与波动')}</div>
          ${priceRangeHtml(vm.priceStats)}
          <div style="margin-top:8px">${offersHtml(vm.offers, vm.priceStats.min, 'Ticket type', '票种')}</div>
        </div>
        <div>
          <div class="block-title">${zh('Ticket policy', '门票政策')}</div>
          <div class="policy-grid">
            <div><em>${zh('Free entry', '免票')}</em>${esc(policyText(vm, 'free'))}</div>
            <div><em>${zh('Discount', '优惠')}</em>${esc(policyText(vm, 'discount'))}</div>
            <div><em>${zh('Booking', '预约')}</em>${esc(policyText(vm, 'booking'))}</div>
            <div><em>${zh('Refunds', '退改')}</em>${esc(policyText(vm, 'refund'))}</div>
          </div>
        </div>
        <div><div class="block-title">${zh('Ticket types', '票种与价格')}</div>
          ${vm.ticket_types.length ? `<table class="tickets"><thead><tr><th>${zh('Type', '票种')}</th><th>${zh('Notes', '说明')}</th><th style="text-align:right">${zh('Price', '价格')}</th></tr></thead><tbody>${tickets}</tbody></table>` : emptyBlock(zh('No ticket-type breakdown; see the channel quotes above.', '暂无票种明细，可参考上方渠道报价。'))}
        </div>
        <div>
          <div class="block-title">${zh('Location & transport', '位置与交通')}</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:6px">
            ${metro ? `<span class="transit-line">🚇 ${esc(metro.name)}${metro.line ? ' (' + esc(metro.line) + ')' : ''} · ${km(metro.distance_km)} · ${zh('about ' + metro.walk_min + ' min walk', '步行约 ' + metro.walk_min + ' 分钟')}</span>` : `<span class="badge-soft">${zh('No metro data', '暂无地铁数据')}</span>`}
            <span style="font-size:12px;color:#7c9099">${zh('Coordinates', '坐标')} ${Number(vm.lat).toFixed(4)}, ${Number(vm.lng).toFixed(4)} (GCJ02)</span>
          </div>
          <div style="font-size:12.5px;color:#3d5a63">${zh('Opening hours: ', '营业时间：')}${esc((() => {
            const raw = isZh() ? (vm.open_time_zh || vm.open_time) : (vm.open_time || vm.open_time_zh);
            if (!raw) return zh('see venue notice', '以景区公告为准');
            // 英文模式下若营业时间里仍有中文（上游原文），不硬翻，直接指向公告
            if (!isZh() && /[一-鿿]/.test(raw)) return zh('see venue notice', '以景区公告为准');
            return raw;
          })())}</div>
          ${vm.tags.length ? `<div class="card-tags" style="margin-top:8px">${vm.tags.map((t) => `<span class="tag">${esc(t)}</span>`).join('')}</div>` : ''}
        </div>
        <div><div class="block-title">${zh('Nearby hotels', '周边酒店')} <span style="font-weight:500;letter-spacing:0;text-transform:none;color:#7c9099">${zh('Sorted by distance', '按距离排序')}</span></div>
          ${vm.has.hotels ? `<div class="nearby-grid">${hotels}</div>` : emptyBlock(zh('No nearby hotels matched yet; they appear here as hotel data arrives.', '暂未匹配到周边酒店，数据到位后会自动显示。'))}
        </div>
        ${vm.has.similar ? `<div><div class="block-title">${zh('More in this city', '同城更多')}</div><div class="nearby-grid">${similar}</div></div>` : ''}
      </div>`;
  }

  function hotelDetailHtml(vm) {
    const metro = vm.nearest_metro;
    const nearby = vm.nearbyAttractions.map((a) => `
      <button class="nearby" data-similar="${esc(a.key)}">
        <img src="${a.cover_image || API.cover(a.name, a.city)}" alt="${esc(a.name)}" Loading="lazy">
        <div class="nb-main"><b>${esc(a.name)}</b><span>★ ${(Number(a.rating) || 0).toFixed(1)} · ${money(a.price)}</span><span class="nb-price">${zh(km(a.distance_km) + ' from hotel', '距酒店 ' + km(a.distance_km))}</span></div>
      </button>`).join('');
    return `
      <button class="modal-close" data-close aria-label="Close">✕</button>
      <div class="detail-head">
        ${galleryHtml(vm)}
        <div class="detail-info">
          <h2 class="detail-name">${esc(vm.name)}</h2>
          <div class="detail-sub"><span>${zh(vm.star + ' stars hotel', vm.star + ' 星级酒店')}</span><span>${esc(vm.address || 'Address pending')}</span>${vm.source_label ? `<span class="src-chip${vm.source === 'cache' ? ' cache' : ''}">${esc(sourceLabel(vm))}</span>` : ''}</div>
          <div class="detail-score">${starsHtml(vm.rating)}<span class="score-num">${vm.rating === null ? '—' : vm.rating.toFixed(1)}<small> / 5</small></span><span style="font-size:12px;color:#7c9099">${vm.has.rating ? zh(vm.review_count.toLocaleString() + ' reviews', vm.review_count.toLocaleString() + ' 条点评') : zh('No rating yet', '暂无评分')}</span></div>
          ${ratingSourcesHtml(vm)}
          <div class="detail-price"><b>${money(vm.price)}</b>${vm.original_price > vm.price ? `<s>¥${Number(vm.original_price).toFixed(0)}</s>` : ''}<span>${zh('/night from · lowest ' + money(vm.priceStats.min), '/晚起 · 最低 ' + money(vm.priceStats.min))}</span></div>
          ${vm.price_basis && vm.price_basis.source ? `<div class="price-basis">${zh('Rate basis', '房价口径')}：${esc(isZh() ? (vm.price_basis.source_zh || vm.price_basis.source) : (vm.price_basis.source || vm.price_basis.source_zh))} · ${zh('per night from', '每晚起价')}${vm.price_basis.fetched_at ? ' · ' + esc(vm.price_basis.fetched_at) : ''}<br>${esc(isZh() ? (vm.price_basis.formula_zh || vm.price_basis.formula) : (vm.price_basis.formula || vm.price_basis.formula_zh))}；${esc(isZh() ? (vm.price_basis.tax_note_zh || vm.price_basis.tax_note) : (vm.price_basis.tax_note || vm.price_basis.tax_note_zh))}</div>` : ''}
          <div class="detail-actions">
            <button class="btn gold" data-hotel-add="${esc(vm.id || vm.source_id)}">${zh('Add as stay', '加入住宿')}</button>
            <button class="btn" data-set-origin="${vm.lat},${vm.lng},${esc(vm.name)}">${zh('Set as origin', '设为出发点')}</button>
            <a class="btn" href="${detailMapLink(vm)}" target="_blank" rel="noopener">${detailMapLabel()}</a>
          </div>
          ${factsHtml([
            [zh('Rate', '房价'), money(vm.price) + zh('/night', '/晚')],
            [zh('Stars', '星级'), vm.star + zh('', ' 星')],
            [zh('Rating', '评分'), vm.rating === null ? '—' : vm.rating.toFixed(1) + ' / 5'],
            [zh('Reviews', '点评'), vm.review_count ? vm.review_count.toLocaleString() : '—'],
          ])}
        </div>
      </div>
      <div class="detail-body">
        <div>
          <div class="block-title">${zh('Transport & location', '交通与位置')}</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
            ${vm.has.metro ? `<span class="transit-line">🚇 ${esc(vm.metro_station || zh('Nearest metro', '最近地铁'))} · ${zh(vm.metro_distance_m + ' m walk', '步行 ' + vm.metro_distance_m + ' 米')}</span>` : `<span class="badge-soft">${zh('No metro distance', '暂无地铁距离')}</span>`}
            ${metro ? `<span style="font-size:12px;color:#7c9099">${zh('Nearest station', '最近车站')} ${esc(metro.name)} (${esc(metro.line)})${km(metro.distance_km)} ${zh('straight line', '直线距离')}</span>` : ''}
          </div>
          <div class="detail-addr">${esc(vm.address || zh('Address pending', '地址待补'))}</div>
          <div class="detail-coord">${zh('Coordinates', '坐标')} ${Number(vm.lat).toFixed(4)}, ${Number(vm.lng).toFixed(4)} (GCJ02)</div>
        </div>
        <div>
          <div class="block-title">Price range</div>
          ${priceRangeHtml(vm.priceStats)}
          <div style="margin-top:8px">${offersHtml(vm.offers, vm.priceStats.min, 'Room type', '房型')}</div>
          <div class="block-title" style="margin-top:14px">${zh('Platform ratings', '平台评分')}</div>
          ${(vm.platform_ratings || []).length ? `<div class="platform-list">${vm.platform_ratings.map((p) => `
            <div class="platform-row">
              <b>${esc(isZh() ? (p.platform_zh || p.platform) : p.platform)}</b>
              <span>${p.rating != null ? `★ ${Number(p.rating).toFixed(1)}` : '—'}</span>
              <span class="pl-muted">${p.reviews ? zh(Number(p.reviews).toLocaleString() + ' reviews', Number(p.reviews).toLocaleString() + ' 条点评') : ''}</span>
              ${p.price != null ? `<span class="pl-price">${money(p.price)}</span>` : `<span class="pl-muted">${zh('price needs platform session', '价格需平台登录态')}</span>`}
              ${p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">${zh('Open', '打开')}</a>` : ''}
            </div>`).join('')}</div>` : emptyBlock(zh('No platform ratings matched yet.', '暂未匹配到平台评分。'))}
          <div class="platform-note">${zh('Prices appear only when a platform actually returns one; Ctrip scores come from its public pages.', '只有平台真实返回价格时才显示报价；携程评分来自其公开页面。')}</div>
        </div>
        <div><div class="block-title">${zh('Stay policy', '入住政策')}</div>
          <div class="policy-grid">
            <div><em>${zh('Check-in', '入住')}</em>${esc(policyText(vm, 'checkin'))}</div>
            <div><em>${zh('Cancellation', '取消')}</em>${esc(policyText(vm, 'cancel'))}</div>
            <div><em>${zh('Children', '儿童')}</em>${esc(policyText(vm, 'child'))}</div>
          </div>
        </div>
        <div><div class="block-title">${zh('Nearby attractions', '周边景点')}</div>
          ${vm.has.nearby ? `<div class="nearby-grid">${nearby}</div>` : emptyBlock(zh('No nearby attractions matched for this hotel yet.', '该酒店暂未匹配到周边景点。'))}
        </div>
      </div>`;
  }

  function detailLoading(kind, name) {
    const what = kind === 'hotel' ? zh('hotel', '酒店') : zh('attraction', '景点');
    return `<div style="padding:52px;text-align:center;color:#7c9099">${zh('Loading ' + what + ' details', '正在加载' + what + '详情')}${name ? ': ' + esc(name) : ''}…</div>`;
  }

  function detailError(message, canRetry, kind, id) {
    return `<div style="padding:44px 26px;text-align:center">
      <div style="font-size:15px;font-weight:700;color:#b04237;margin-bottom:8px">${zh('Failed to load details', '详情加载失败')}</div>
      <div style="font-size:13px;color:#3d5a63;line-height:1.8;max-width:460px;margin:0 auto 14px">${esc(message)}</div>
      <div style="font-size:12px;color:#7c9099;line-height:1.8">${zh('Start the service with start.bat or python app.py, then open http://127.0.0.1:8848', '先用 start.bat 或 python app.py 启动服务，再打开 http://127.0.0.1:8848')}</div>
      ${canRetry ? `<button class="btn primary" data-retry="${esc(kind)}|${esc(id)}" style="margin-top:14px">${zh('Reload', '重新加载')}</button>` : ''}
    </div>`;
  }

  function openAttrDetail(key) {
    closeDetail();
    state.detailKey = key;
    const modal = $('#detailModal');
    $('#detailMask').classList.add('open');
    const local = state.attr.items.find((i) => i.key === key) || API.recallDetail('attr', key);
    if (local) {
      // Render from list data first so a failed second request never breaks the page
      const vm = normalizeAttr(local);
      state.detailView = { kind: 'attr', vm };
      modal.innerHTML = attrDetailHtml(vm);
      bindDetail(vm, 'attr');
      if (state.map && local.lat) state.map.focus(local.lat, local.lng);
    } else {
      modal.innerHTML = detailLoading('attr');
    }
    API.detail(key).then((d) => {
      if (!d || d.ok === false) throw new Error(d && d.message ? d.message : 'Details not found');
      const vm = normalizeAttr(d);
      API.rememberDetail('attr', key, d);
      state.detailView = { kind: 'attr', vm };
      modal.innerHTML = attrDetailHtml(vm);
      bindDetail(vm, 'attr');
      if (state.map && d.lat) state.map.focus(d.lat, d.lng);
    }).catch((err) => {
      if (!local) {
        modal.innerHTML = detailError(err.message, true, 'attr', key);
        bindDetail({}, 'attr');
      } else {
        toast('Details shown from local data: ' + err.message, 'err');
      }
    });
  }

  function openHotelDetail(id) {
    closeDetail();
    const modal = $('#detailModal');
    $('#detailMask').classList.add('open');
    const localHotel = state.hotel.items.find((h) => (h.id || h.source_id) === id) || API.recallDetail('hotel', id);
    if (localHotel) {
      const vm = normalizeHotel(localHotel);
      state.detailView = { kind: 'hotel', vm };
      modal.innerHTML = hotelDetailHtml(vm);
      bindDetail(vm, 'hotel');
      if (state.map && localHotel.lat) state.map.focus(localHotel.lat, localHotel.lng);
    } else {
      modal.innerHTML = detailLoading('hotel');
    }
    API.hotelDetail(id).then((h) => {
      if (!h || h.ok === false) throw new Error(h && h.message ? h.message : 'Hotel not found');
      const vm = normalizeHotel(h);
      API.rememberDetail('hotel', id, h);
      state.detailView = { kind: 'hotel', vm };
      modal.innerHTML = hotelDetailHtml(vm);
      bindDetail(vm, 'hotel');
      if (state.map && h.lat) state.map.focus(h.lat, h.lng);
    }).catch((err) => {
      if (!localHotel) {
        modal.innerHTML = detailError(err.message, true, 'hotel', id);
        bindDetail({}, 'hotel');
      } else {
        toast('Hotel details shown from local data: ' + err.message, 'err');
      }
    });
  }

  function bindDetail(vm, type) {
    const modal = $('#detailModal');
    modal.querySelectorAll('[data-thumb]').forEach((img) => img.addEventListener('click', () => {
      const list = vm.gallery || [];
      if (list[Number(img.dataset.thumb)]) $('#galleryMain').src = list[Number(img.dataset.thumb)];
      modal.querySelectorAll('[data-thumb]').forEach((n) => n.classList.remove('on'));
      img.classList.add('on');
    }));
    modal.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', closeDetail));
    modal.querySelectorAll('[data-attr-add]').forEach((b) => b.addEventListener('click', () => addToTrip(b.dataset.attrAdd, 'attraction')));
    modal.querySelectorAll('[data-hotel-add]').forEach((b) => b.addEventListener('click', () => addToTrip(b.dataset.hotelAdd, 'hotel')));
    modal.querySelectorAll('[data-set-origin]').forEach((b) => b.addEventListener('click', () => {
      const [lat, lng, name] = b.dataset.setOrigin.split(',');
      state.origin = { lat: Number(lat), lng: Number(lng), name: name };
      toast('Set as origin: ' + name, 'ok');
    }));
    modal.querySelectorAll('[data-near-hotel]').forEach((b) => b.addEventListener('click', () => openHotelDetail(b.dataset.nearHotel)));
    modal.querySelectorAll('[data-similar]').forEach((b) => b.addEventListener('click', () => openAttrDetail(b.dataset.similar)));
    // Deep link expand=1 opens every channel quote for demos and screenshots
    if (new URLSearchParams((location.hash || '').replace(/^#/, '')).get('expand') === '1') {
      modal.querySelectorAll('details.offer').forEach((d) => { d.open = true; });
    }
    modal.querySelectorAll('[data-retry]').forEach((b) => b.addEventListener('click', () => {
      const [kind, id] = b.dataset.retry.split('|');
      if (kind === 'hotel') openHotelDetail(id); else openAttrDetail(id);
    }));
  }

  function closeDetail() {
    state.detailView = null; $('#detailMask').classList.remove('open'); }

  /* ============================ Price comparison ============================ */
  function renderComparePickers() {
    const attrList = $('#cmpAttrList');
    const hotelList = $('#cmpHotelList');
    attrList.innerHTML = state.attr.items.map((i) => `<button class="chip${state.cmp.attrs.has(i.key) ? ' on' : ''}" data-cmp-attr="${esc(i.key)}">${esc(i.name)}</button>`).join('') || '<span style="font-size:12px;color:#7c9099">No attractions available</span>';
    hotelList.innerHTML = state.hotel.items.map((h) => `<button class="chip hotel${state.cmp.hotels.has(h.id) ? ' on' : ''}" data-cmp-hotel="${esc(h.id)}">${esc(h.name)}</button>`).join('') || '<span style="font-size:12px;color:#7c9099">No hotels available</span>';
  }

  async function runCompare() {
    const attrs = Array.from(state.cmp.attrs).slice(0, 6);
    const hotels = Array.from(state.cmp.hotels).slice(0, 8);
    if (!attrs.length && !hotels.length) { toast('Pick attractions or hotels to compare first'); return; }
    try {
      const data = await API.compare(attrs, hotels);
      state.cmp.data = data;
      renderCompareData(data);
      toast('Comparison ready', 'ok');
    } catch (err) {
      toast('Comparison failed: ' + err.message, 'err');
    }
  }

  function renderCompareData(data) {
    try {
      const platformZh = { 'Qunar': '去哪儿', 'Ctrip': '携程', 'Meituan': '美团', 'Tongcheng': '同程', 'Elong': '艺龙',
        'List price': '门市原价', 'Live fetch': '实时抓取', 'Baidu Maps': '百度地图',
        'Baidu Maps · ticket': '百度地图 · 景区票价', 'Qunar (via Baidu Maps)': '去哪儿（经百度地图）' };
      const platforms = (data.platforms && data.platforms.length ? data.platforms : ['Live fetch']).slice(0, 4);
      const headCells = platforms.map((p) => `<th>${esc(isZh() ? (platformZh[p] || p) : p)}</th>`).join('');
      const attrRows = (data.attractions || []).map((a) => {
        const map = {}; (a.offers || []).forEach((o) => { map[o.platform] = o.price; });
        const prices = (a.offers || []).map((o) => o.price);
        const spread = prices.length > 1 ? (Math.max.apply(null, prices) - Math.min.apply(null, prices)).toFixed(1) : '0';
        const min = Math.min.apply(null, prices.concat([a.price]));
        return `<tr>
          <td><b>${esc(a.name)}</b><div class="spread">${esc(isZh() ? (a.city || a.city_en) : (a.city_en || a.city))} · ★ ${(Number(a.rating) || 0).toFixed(1)}</div></td>
          ${platforms.map((p) => `<td class="num${map[p] === min ? ' best' : ''}">${map[p] === undefined ? '—' : money(map[p])}</td>`).join('')}
          <td>${money(min)}<div class="spread">${zh('Spread', '价差')} ¥${spread}</div></td>
        </tr>`;
      }).join('');
      const hotelRows = (data.hotels || []).map((h) => {
        const map = {}; (h.offers || []).forEach((o) => { map[o.platform] = o; });
        const prices = (h.offers || []).map((o) => o.price);
        const min = prices.length ? Math.min.apply(null, prices) : h.price;
        const bestOffer = (h.offers || []).find((o) => o.price === min) || {};
        return `<tr>
          <td><b>${esc(h.name)}</b><div class="spread">${zh(h.star + ' stars', h.star + ' 星')} · ★ ${(Number(h.rating) || 0).toFixed(1)}${(() => { const c = (h.platform_ratings || []).find((p) => p.platform === 'Ctrip'); return c && c.rating != null ? ` · ${zh('Ctrip', '携程')} ★ ${Number(c.rating).toFixed(1)}` : ''; })()}</div></td>
          ${platforms.map((p) => `<td class="hotel-price${map[p] && map[p].price === min ? ' best' : ''}">${map[p] ? money(map[p].price) : '—'}</td>`).join('')}
          <td>${esc(bestOffer.breakfast || '—')}<div class="spread">${esc(bestOffer.cancel || '')}</div></td>
          <td>${esc(h.metro_station || '—')}<div class="spread">${zh(h.metro_distance_m + ' m walk', '步行 ' + h.metro_distance_m + ' 米')}</div></td>
        </tr>`;
      }).join('');

      $('#cmpResult').innerHTML = `
        ${attrRows ? `<div class="panel" style="margin-bottom:14px"><div class="panel-head"><span>Attraction ticket comparison</span></div>
          <div class="panel-body"><div class="table-wrap"><table class="cmp">
            <thead><tr><th>Attraction</th>${headCells}<th>Lowest</th></tr></thead>
            <tbody>${attrRows}</tbody></table></div></div></div>` : ''}
        ${hotelRows ? `<div class="panel"><div class="panel-head"><span>Hotel rate comparison</span></div>
          <div class="panel-body"><div class="table-wrap"><table class="cmp">
            <thead><tr><th>Hotel</th>${headCells}<th>Breakfast / cancellation</th><th>Nearest metro</th></tr></thead>
            <tbody>${hotelRows}</tbody></table></div></div></div>` : ''}
        <div class="warn-box" style="margin-top:12px">Quotes are online and list prices aggregated by Baidu Maps, each with a fetch time. Channels without a price show —; estimates are never presented as live rates.</div>`;
    } catch (err) {
      toast('Comparison failed: ' + err.message, 'err');
    }
  }

  /* ============================ Trip ============================ */
  async function ensureTrip() {
    if (state.tripId) {
      try { const d = await API.getTrip(state.tripId); state.trip = d.trip; return state.tripId; }
      catch (e) { state.tripId = null; localStorage.removeItem('travelone.tripId'); }
    }
    const created = await API.createTrip({ title: 'My trip', city: state.city || '' });
    state.tripId = created.trip.id;
    state.trip = created.trip;
    localStorage.setItem('travelone.tripId', String(state.tripId));
    return state.tripId;
  }

  async function addToTrip(key, kind) {
    try {
      const id = await ensureTrip();
      const res = await API.addItem(id, { key, kind: kind || 'attraction', day: 1, visit_minutes: kind === 'hotel' ? 0 : 120 });
      await refreshTrip();
      toast(res && res.already ? 'Already in trip' : (kind === 'hotel' ? 'Added as stay' : 'Added to trip'), res && res.already ? '' : 'ok');
      renderComparePickers();
    } catch (err) { toast('Add failed: ' + err.message, 'err'); }
  }

  async function refreshTrip() {
    if (!state.tripId) return;
    const data = await API.getTrip(state.tripId);
    state.trip = data.trip;
    renderTrip();
  }

const TRIP_FILE_FORMAT = 'travelone.trip';
  const TRIP_FILE_VERSION = 1;
  const TRIP_ITEM_FIELDS = ['key', 'key_type', 'name', 'attraction_name', 'city', 'city_en',
    'address', 'lat', 'lng', 'rating', 'price', 'kind', 'cover_image', 'tags',
    'day', 'seq', 'visit_minutes'];

  // 导出文件：只带跨设备还原所需的字段，id 与本地时间戳留给接收端重新分配
  function tripFilePayload(trip) {
    const items = (trip.items || []).map((item) => {
      const out = {};
      TRIP_ITEM_FIELDS.forEach((field) => {
        const value = item[field];
        if (value !== undefined && value !== null && value !== '') out[field] = value;
      });
      out.name = item.name || item.attraction_name || '';
      out.kind = item.kind === 'hotel' ? 'hotel' : 'attraction';
      out.day = Math.max(1, Number(item.day) || 1);
      out.seq = Math.max(0, Number(item.seq) || 0);
      out.visit_minutes = Math.max(0, Number(item.visit_minutes) || 0);
      return out;
    });
    return {
      format: TRIP_FILE_FORMAT,
      version: TRIP_FILE_VERSION,
      app: 'TravelOne',
      exported_at: new Date().toISOString(),
      trip: {
        title: trip.title || 'My trip',
        city: trip.city || '',
        start_date: trip.start_date || '',
        created_at: trip.created_at || '',
        items,
      },
    };
  }

  function downloadTripFile(payload) {
    const slug = String(payload.trip.title || 'trip').trim()
      .replace(/[\\/:*?"<>|\s]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60) || 'trip';
    const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    const name = 'travelone-' + slug + '-' + stamp + '.json';
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return name;
  }

  async function exportTrip() {
    try {
      if (state.tripId) await refreshTrip();
      const count = state.trip && state.trip.items ? state.trip.items.length : 0;
      if (!count) { toast(zh('Add at least one place before exporting', '请先加入至少一个地点再导出'), 'err'); return; }
      const payload = tripFilePayload(state.trip);
      const name = downloadTripFile(payload);
      toast(zh('Exported ' + count + ' places to ' + name, '已导出 ' + count + ' 个地点到 ' + name), 'ok');
    } catch (err) { toast(zh('Export failed: ' + err.message, '导出失败：' + err.message), 'err'); }
  }

  // 接受本应用导出的 {format, version, trip} 文件，也接受裸行程对象
  function parseTripFile(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('JSON root is not an object');
    if (raw.format && raw.format !== TRIP_FILE_FORMAT) throw new Error('Not a TravelOne trip file');
    if (raw.version && Number(raw.version) > TRIP_FILE_VERSION) throw new Error('File version is newer than this app');
    const source = raw.trip && typeof raw.trip === 'object' ? raw.trip : raw;
    const items = (Array.isArray(source.items) ? source.items : [])
      .filter((item) => item && typeof item === 'object' && (item.name || item.attraction_name));
    if (!items.length) throw new Error('No usable places in this file');
    return {
      title: String(source.title || 'Imported trip').slice(0, 120),
      city: source.city || '',
      start_date: source.start_date || '',
      items,
    };
  }

  async function importTripFile(file) {
    try {
      const text = await file.text();
      let raw;
      try { raw = JSON.parse(text); } catch (e) { throw new Error('File is not valid JSON'); }
      const tripData = parseTripFile(raw);
      const payload = tripFilePayload(tripData);
      const res = await API.importTrip(payload);
      state.tripId = res.trip.id;
      state.trip = res.trip;
      localStorage.setItem('travelone.tripId', String(state.tripId));
      state.plan = null;
      if (state.map) { state.map.setMarkers([]); state.map.setRoute({ days: [] }); }
      const planBox = document.getElementById('planResult');
      if (planBox) planBox.innerHTML = '';
      await refreshTrip();
      renderComparePickers();
      toast(zh('Imported ' + res.trip.items.length + ' places as "' + res.trip.title + '"',
        '已导入 ' + res.trip.items.length + ' 个地点，行程「' + res.trip.title + '」'), 'ok');
      document.getElementById('trip').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) { toast(zh('Import failed: ' + err.message, '导入失败：' + err.message), 'err'); }
  }

  function tripDays() {
    const items = state.trip ? state.trip.items : [];
    return Math.max(1, items.reduce((m, i) => Math.max(m, i.day || 1), 1));
  }

  function renderTrip() {
    const box = $('#tripDays');
    const trip = state.trip;
    const count = trip && trip.items ? trip.items.length : 0;
    $('#tripCount').textContent = count;
    $('#tripBadge').textContent = count;
    $('#tripBadge').classList.toggle('on', count > 0);
    $('#planBtn').disabled = count === 0;
    $('#tripExport').disabled = count === 0;
    if (!count) {
      $('#tripMeta').textContent = 'Add places or hotels, then plan in one click';
      box.innerHTML = `<div class="empty"><b>Your trip is empty</b>Use Add to trip on an attraction card, or Add as stay on a hotel card</div>`;
      return;
    }
    const days = tripDays();
    $('#tripMeta').textContent = `${count} places · ${days} days · tickets and stays from about ¥${trip.items.reduce((s, i) => s + (Number(i.price) || 0), 0)}`;
    let html = '';
    for (let day = 1; day <= days; day++) {
      const items = trip.items.filter((i) => (i.day || 1) === day);
      html += `<div class="day-card" style="margin-bottom:12px">
        <div class="day-head"><b>Day ${day}</b><span>${items.length} places · about ¥${items.reduce((s, i) => s + (Number(i.price) || 0), 0)}</span></div>
        <div class="day-items">
          ${items.length ? items.map((item, idx) => `
            <div class="trip-item${item.kind === 'hotel' ? ' is-hotel' : ''}">
              <div class="idx">${idx + 1}</div>
              <div class="ti-main">
<div class="ti-name">${item.kind === 'hotel' ? '🏨 ' : ''}${esc(item.attraction_name || item.name || '')}</div>
                <div class="ti-meta">${item.kind === 'hotel' ? 'Stay' : 'Attraction'} · ★ ${(Number(item.rating) || 0).toFixed(1)} · ${money(item.price)}${item.kind === 'hotel' ? (item.address ? ' · ' + esc(item.address) : '') : ''}</div>
              </div>
              <select data-move="${item.id}">${Array.from({ length: Math.max(7, days) }, (_, k) => k + 1).map((d) => `<option value="${d}" ${d === day ? 'selected' : ''}>D${d}</option>`).join('')}</select>
              <button class="del" data-del="${item.id}" title="Remove">✕</button>
            </div>`).join('') : '<div style="font-size:12px;color:#7c9099;padding:6px 2px">Nothing planned for this day</div>'}
        </div>
      </div>`;
    }
    box.innerHTML = html;
    box.querySelectorAll('[data-del]').forEach((b) => b.addEventListener('click', async () => {
      try { await API.removeItem(state.tripId, Number(b.dataset.del)); await refreshTrip(); toast('Removed'); }
      catch (err) { toast('Remove failed: ' + err.message, 'err'); }
    }));
    box.querySelectorAll('[data-move]').forEach((sel) => sel.addEventListener('change', async () => {
      const items = state.trip.items.map((i) => ({ id: i.id, day: i.id === Number(sel.dataset.move) ? Number(sel.value) : (i.day || 1), seq: i.seq || 0, visit_minutes: i.visit_minutes || 0 }));
      try { await API.updateItems(state.tripId, items); await refreshTrip(); }
      catch (err) { toast('Update failed: ' + err.message, 'err'); }
    }));
  }

  /* ============================ Intercity transport ============================ */
  function transportModeLabel(opt) {
    if (isZh()) return opt.label_zh || opt.label || opt.mode;
    return opt.label || opt.label_zh || opt.mode;
  }

  function transportSourceChip(opt) {
    const live = opt.source === '12306';
    const label = isZh() ? (opt.source_label_zh || opt.source_label || opt.source)
      : (opt.source_label || opt.source_label_zh || opt.source);
    return `<span class="src-chip${live ? '' : ' cache'}" title="${esc(label)}">${esc(label)}</span>`;
  }

  // 交通费用口径：把参数、来源链接与数据时间摊开，便于逐项核对
  function calcFootnote(data) {
    const p = data.params || {};
    const srcs = (data.sources || []).map((s) => {
      const link = s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)}</a>` : esc(s.name || '');
      const status = s.status ? ` (${esc(s.status)}${s.detail ? ' · ' + esc(s.detail) : ''})` : '';
      return link + status;
    }).join(' · ');
let paramLine;
    if (p.flight_bands) {
      // 国际版口径：航距分段 × 航线/枢纽系数；区域铁路；当地油价 × 固定参考汇率
      const bands = p.flight_bands.map(([km, lo, hi]) => `≤${km} km ${lo}–${hi}`).join(' / ');
      const rf = p.route_factor || {};
      const rail = p.rail || {};
      const band = (rail.band || []).join('–');
      paramLine = isZh()
        ? `机票：航距分段（${bands} 元）再乘航线系数（国内 ${rf.domestic}、同区域 ${rf.region}、洲际 ${rf.inter}）与枢纽系数；铁路：${rail.base} 元基础价 + 区域每公里费率，区间 ×${band}；自驾：${p.fuel_per_100km} L/100km，公路系数 ${p.road_factor}（跨境 ${p.road_factor_cross_border}）；油价按当地挂牌价 × 固定参考汇率（非实时行情）`
        : `Flights: distance bands (${bands} CNY) x route factor (domestic ${rf.domestic}, same region ${rf.region}, intercontinental ${rf.inter}) x hub factor; rail: CNY${rail.base} base + regional per-km rate, band x${band}; drive: ${p.fuel_per_100km} L/100km, road factor ${p.road_factor} (cross-border ${p.road_factor_cross_border}); fuel = local pump price x fixed reference FX (${p.fx_note})`;
    } else {
      paramLine = isZh()
        ? `系数：直线→公路 ${p.road_factor}、直线→铁路 ${p.rail_factor}；油耗 ${p.fuel_per_100km} L/100km；通行费 ${p.toll_per_km} 元/km；高铁 ${p.rail_speed_kmh} km/h、二等座 ${(p.rail_rate || {}).second} 元/km、一等座 ${(p.rail_rate || {}).first} 元/km；机票 ${p.flight_base} 元 + ${p.flight_per_km} 元/km`
        : `Assumptions: road ${p.road_factor}x and rail ${p.rail_factor}x straight-line; ${p.fuel_per_100km} L/100km; toll CNY${p.toll_per_km}/km; rail ${p.rail_speed_kmh} km/h, CNY${(p.rail_rate || {}).second}/km second class, CNY${(p.rail_rate || {}).first}/km first class; air CNY${p.flight_base} + CNY${p.flight_per_km}/km`;
    }
    return `<details class="calc-note"><summary>${zh('How these numbers are calculated', '这些数字怎么来的')}</summary>
      <div>${esc(paramLine)}</div>
      <div style="margin-top:4px">${zh('Sources', '来源')}：${srcs || '—'}</div>
      <div style="margin-top:4px">${zh('Data time', '数据时间')}：${esc(data.as_of || data.fetched_at || '—')}</div>
    </details>`;
  }

  function renderTransport() {
    const box = $('#transportResult');
    if (!box) return;
    const data = state.transport.result;
    if (!data) { box.innerHTML = ''; return; }
    if (!data.ok) {
      box.innerHTML = `<div class="empty"><b>${zh('Could not compare', '无法比对')}</b>${esc(data.message || '')}</div>`;
      return;
    }
const options = data.options || [];
    // 国际版不一定有铁路；默认选中的方式若不存在，退回第一条可用的
    if (!options.some((o) => o.mode === state.transport.chosen)) {
      state.transport.chosen = (options[0] || {}).mode;
    }
    const rows = options.map((opt) => {
      const duration = opt.duration_min ? fmtMin(opt.duration_min) : (opt.duration_text || '—');
      const price = opt.price_from === null || opt.price_from === undefined
        ? zh('n/a (no parameter)', '暂无（无参数）')
        : `${money(opt.price_from)} – ${money(opt.price_to)}`;
      const chosen = state.transport.chosen === opt.mode;
      const stops = opt.mode === 'flight' && opt.stops
        ? `<div class="train-line">${zh('1 stop estimated', '预计 1 次中转')}</div>`
        : '';
      const trains = opt.train_count
        ? `<div class="train-line">${zh(`Timetable trains: ${opt.train_count}`, `时刻表车次：${opt.train_count} 趟`)}${opt.trains && opt.trains.length ? ' · ' + esc(opt.trains.slice(0, 6).join(' / ')) : ''}</div>`
        : '';
      const calc = opt.breakdown_label
        ? `<div class="calc-line">${esc(isZh() ? (opt.breakdown_label_zh || opt.breakdown_label) : (opt.breakdown_label || opt.breakdown_label_zh))}</div>`
        : '';
      return `<tr>
        <td><b>${esc(transportModeLabel(opt))}</b>${trains}</td>
        <td>${esc(duration)}</td>
        <td>${esc(price)}${calc}</td>
        <td>${transportSourceChip(opt)}</td>
        <td style="text-align:right"><button class="btn sm${chosen ? ' primary' : ''}" data-transport-pick="${esc(opt.mode)}">${chosen ? zh('Selected', '已选') : zh('Use', '选用')}</button></td>
      </tr>`;
    }).join('');
const fuel = data.fuel || {};
    const prices = fuel.prices || {};
    const fuelLabel = fuel.label || zh('92# petrol', '92# 汽油');
    const fuelLine = prices.p92
      ? (prices.p0
          ? `${fuelLabel} ¥${Number(prices.p92).toFixed(2)}/L · ${zh('0# diesel', '0# 柴油')} ¥${Number(prices.p0).toFixed(2)}/L`
          : `${fuelLabel} ¥${Number(prices.p92).toFixed(2)}/L`)
      : zh('Fuel price unavailable right now', '暂时取不到油价');
    const chosenOpt = (data.options || []).find((o) => o.mode === state.transport.chosen) || {};
    const tickets = Number((state.trip && state.trip.ticket_total)
      || (state.trip && (state.trip.items || []).reduce((sum, i) => sum + (Number(i.price) || 0), 0)) || 0);
    const total = tickets + Number(chosenOpt.price_from || 0);
    box.innerHTML = `
      <div class="transport-head">
        <b>${esc(isZh() ? data.from.name : (data.from.name_en || data.from.name))} → ${esc(isZh() ? data.to.name : (data.to.name_en || data.to.name))}</b>
        <span>${zh('Straight-line', '直线距离')} ${data.distance_km} km</span>
        <span>${fuelLine}</span>
      </div>
      <div class="table-wrap"><table class="cmp transport-table">
        <thead><tr><th>${zh('Mode', '方式')}</th><th>${zh('Time', '耗时')}</th><th>${zh('Price range', '价格区间')}</th><th>${zh('Source', '来源')}</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table></div>
      <div class="transport-total">${zh('Estimated trip total', '预估行程总价')}：<b>${money(total)}</b>
        <span>${zh('tickets / stays', '门票住宿')} ¥${Number(tickets).toFixed(0)} + ${zh(transportModeLabel(chosenOpt), transportModeLabel(chosenOpt))} ¥${Number(chosenOpt.price_from || 0).toFixed(0)}</span>
      </div>
      ${calcFootnote(data)}
      <div class="platform-note">${zh(data.note_zh || '', data.note_zh || data.note || '')}</div>`;
    const source = $('#transportSource');
    if (source) {
      const anyLive = (data.options || []).some((o) => o.source === '12306');
      const hasTimetable = (data.options || []).some((o) => o.train_count);
      source.textContent = anyLive
        ? zh('Live train data · estimated fares', '车次实时 · 票价估算')
        : hasTimetable
          ? zh('Real trains · estimated fares', '真实车次 · 票价估算')
          : zh('Estimated (no anonymous fare feed)', '估算（无匿名报价源）');
    }
  }

  async function runTransport() {
    const from = ($('#transportFrom').value || '').trim();
    const to = ($('#transportTo').value || '').trim();
    if (!from || !to) { toast(zh('Enter both cities', '请先填写两个城市'), 'err'); return; }
    const btn = $('#transportGo');
    btn.disabled = true;
    const label = btn.textContent;
    btn.textContent = zh('Comparing…', '正在比对…');
    try {
      const data = await API.transport({ from, to, date: $('#transportDate').value || '', province: from });
      state.transport.result = data;
      renderTransport();
      if (!data.ok) toast(data.message || 'Compare failed', 'err');
    } catch (err) {
      toast('Compare failed: ' + err.message, 'err');
    } finally {
      btn.disabled = false;
      btn.textContent = label;
    }
  }

  async function runPlan() {
    if (!state.tripId) return;
    const btn = $('#planBtn');
    btn.disabled = true;
    const label = btn.textContent;
    btn.textContent = 'Calculating…';
    try {
      const originChoice = $('#planOrigin').value;
      const body = {
        mode: $('#planMode').value,
        start_time: $('#planStart').value || '09:00',
        optimize: $('#planOptimize').value === '1',
        daily_limit_hours: Number($('#planLimit').value || 10),
        origin: originChoice === 'me' && state.origin ? { lat: state.origin.lat, lng: state.origin.lng, name: state.origin.name || 'My location' } : null,
      };
      // 有出发/到达城市时顺手比一轮城际交通，结果并入价格预估
      const tFrom = ($('#transportFrom') && $('#transportFrom').value || '').trim();
      const tTo = ($('#transportTo') && $('#transportTo').value || '').trim();
      if (tFrom && tTo && !state.transport.result) {
        API.transport({ from: tFrom, to: tTo, date: $('#transportDate') && $('#transportDate').value || '', province: tFrom })
          .then((data) => { state.transport.result = data; renderTransport(); })
          .catch(() => {});
      }
      const result = await API.plan(state.tripId, body);
      if (!result.ok) throw new Error(result.message || 'Planning failed');
      state.plan = result;
      renderPlan(result);
      drawPlanOnMap(result);
      refinePlanWithClientRoutes(result);
      $('#mapPanel').classList.add('open');
      toast(`Route ready: ${result.summary.stops} stops / ${result.summary.distance_km} km`, 'ok');
      document.getElementById('trip').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) {
      toast('Planning failed: ' + err.message, 'err');
    } finally {
      btn.disabled = false; btn.textContent = label;
    }
  }

  // 用浏览器端百度路线服务校正每一段：并行度受限，失败保留服务端/本地估算
  async function refinePlanWithClientRoutes(plan) {
    if (!window.TravelMap || !window.TravelMap.routeLeg) return;
    if (!(state.config && state.config.ak_configured)) return;
    if (!window.BMapGL) {
      // 地图面板没打开时 SDK 还没加载，这里主动拉一次再算路线
      await window.TravelMap.ensureSdk(state.config.baidu_js_ak);
      if (!window.BMapGL) return;
    }
    const tasks = [];
    (plan.days || []).forEach((day) => {
      (day.legs || []).forEach((leg, idx) => {
        if (!leg || leg.source === 'baidu-js') return;
        const from = idx === 0 ? day.origin : day.stops[idx - 1];
        const to = day.stops[idx];
        if (!from || !to || from.lat == null || to.lat == null) return;
        tasks.push({ leg, from, to });
      });
    });
    if (!tasks.length) return;
    let done = 0, changed = false;
    const queue = tasks.slice(0, 24);
    const worker = async () => {
      while (queue.length) {
        const task = queue.shift();
        const res = await window.TravelMap.routeLeg(task.from, task.to, plan.mode || 'driving');
        done += 1;
        if (res && res.distance_km) {
          task.leg.distance_km = res.distance_km;
          task.leg.duration_min = res.duration_min;
          task.leg.source = 'baidu-js';
          changed = true;
        }
      }
    };
    try {
      await Promise.all([worker(), worker(), worker()]);
      if (!changed) return;
      // 重算每天与整体汇总，再重绘
      (plan.days || []).forEach((day) => {
        let km = 0, minutes = 0;
        (day.legs || []).forEach((leg) => { km += Number(leg.distance_km || 0); minutes += Number(leg.duration_min || 0); });
        day.total_distance_km = Number(km.toFixed(1));
        day.travel_min = minutes;
        // 按新的路段耗时重排时间轴
        const pad = (n) => String(n).padStart(2, '0');
        let clock = (() => {
          const [h, m] = String(day.start_time || '09:00').split(':').map(Number);
          return (isFinite(h) ? h : 9) * 60 + (isFinite(m) ? m : 0);
        })();
        (day.stops || []).forEach((stop, idx) => {
          const leg = (day.legs || [])[idx] || {};
          clock += Number(leg.duration_min || 0);
          stop.arrive = pad(Math.floor(clock / 60) % 24) + ':' + pad(clock % 60);
          clock += Number(stop.visit_minutes || 0);
          stop.leave = pad(Math.floor(clock / 60) % 24) + ':' + pad(clock % 60);
        });
        day.end_time = pad(Math.floor(clock / 60) % 24) + ':' + pad(clock % 60);
      });
      let totalKm = 0, totalMin = 0;
      (plan.days || []).forEach((day) => {
        totalKm += Number(day.total_distance_km || 0);
        totalMin += Number(day.travel_min || 0);
      });
      plan.summary.distance_km = Number(totalKm.toFixed(1));
      plan.summary.travel_min = totalMin;
      plan.source = 'baidu';
      plan.source_label = isZh() ? '百度地图实时路线（浏览器）' : 'Live Baidu Maps route (browser)';
      renderPlan(plan);
      drawPlanOnMap(plan);
    } catch (e) { /* 保持原估算 */ }
  }

  function renderPlan(plan) {
    const s = plan.summary;
    const warnings = (plan.warnings || []).length ? `<div class="warn-box">${plan.warnings.map(esc).join('<br>')}</div>` : '';
    // 城际段（飞机/高铁/自驾）单独一行，叠加到行程总价预估
    const tRes = state.transport.result;
    const tOpt = tRes && tRes.ok ? (tRes.options || []).find((o) => o.mode === state.transport.chosen) : null;
    const intercityLine = tOpt ? `<div class="transport-inline">
        <span>${zh('Intercity', '城际交通')}：${esc(isZh() ? (tOpt.label_zh || tOpt.label) : tOpt.label)} ${tOpt.duration_min ? fmtMin(tOpt.duration_min) : ''}</span>
        <b>${money(tOpt.price_from)}${tOpt.price_to && tOpt.price_to !== tOpt.price_from ? ' – ' + money(tOpt.price_to) : ''}</b>
        <span>${esc(isZh() ? (tOpt.source_label_zh || tOpt.source_label) : (tOpt.source_label || tOpt.source_label_zh))}</span>
      </div>` : '';
    const days = (plan.days || []).map((day) => `
      <div class="day-card" style="margin-bottom:12px">
        <div class="day-head"><b>Day ${day.day}</b><span>Depart ${day.start_time} · finish ${day.end_time} · ${day.total_distance_km} km</span></div>
        <div class="day-items">
          <div class="timeline">
            <div class="tl-stop"><div class="tl-time">Origin</div><div class="tl-name">${esc(day.origin.name)}</div></div>
            ${day.stops.map((stop, idx) => {
              const leg = day.legs[idx] || {};
              return `<div class="tl-stop${stop.key && stop.key.indexOf('hotel') === 0 ? ' hotel' : ''}">
                <div class="tl-time">Arrive ${stop.arrive} · leave ${stop.leave}</div>
                <div class="tl-name">${stop.seq}. ${esc(stop.name)}</div>
                <div style="font-size:11.5px;color:#3d5a63">${stop.visit_minutes ? 'Suggested visit ' + fmtMin(stop.visit_minutes) : 'Stay'} · ${money(stop.ticket)}</div>
                <div class="tl-leg">${esc(leg.from || '')} → ${esc(leg.to || '')}: <b>${leg.distance_km || 0} km / ${fmtMin(leg.duration_min)}</b>
                  <div class="src">${(leg.source === 'baidu' || leg.source === 'baidu-js') ? zh('Live Baidu Maps route', '百度地图实时路线') : zh('Local road-factor estimate', '本地路网估算')}</div>
                </div>
              </div>`;
            }).join('')}
          </div>
        </div>
      </div>`).join('');
    $('#planResult').innerHTML = `
      ${intercityLine}
      <div class="panel" style="margin-bottom:14px">
        <div class="panel-head"><span>${zh('Plan result', '行程结果')}</span><span class="pill ${plan.source === 'baidu' ? 'ok' : 'warn'}">${esc(plan.source === 'baidu' && isZh() ? '百度地图实时路线' : plan.source_label)}</span></div>
        <div class="panel-body">
          <div class="plan-summary">
            <div class="item"><b>${s.distance_km}</b><span>Total km</span></div>
            <div class="item"><b>${fmtMin(s.travel_min)}</b><span>Travel time</span></div>
            <div class="item gold"><b>¥${Number(s.ticket_cost || 0).toFixed(0)}</b><span>${zh('Tickets', '门票')}</span></div>
            <div class="item gold"><b>¥${Number(s.stay_cost || 0).toFixed(0)}</b><span>${zh('Stays · ' + (s.nights || 0) + ' night(s)', '住宿 · ' + (s.nights || 0) + ' 晚')}</span></div>
            <div class="item"><b>¥${Number(s.total_cost || 0).toFixed(0)}</b><span>${zh('Total', '合计')}</span></div>
            <div class="item"><b>${s.days}</b><span>Days</span></div>
            <div class="item"><b>${s.stops}</b><span>Stops</span></div>
          </div>
          <div style="font-size:12.2px;color:#3d5a63;margin-bottom:12px">About ${fmtMin(s.visit_min)} visiting and staying; ${s.total_hours} h in total (${esc(plan.mode_label)})</div>
          ${days}
          ${warnings}
        </div>
      </div>`;
  }

  function drawPlanOnMap(plan) {
    if (!state.map) return;
    const markers = [];
    (plan.days || []).forEach((day) => (day.stops || []).forEach((stop) => {
      markers.push({ key: 'stop|' + (stop.key || stop.name), name: 'D' + day.day + '-' + stop.name, lat: stop.lat, lng: stop.lng, seq: stop.seq, kind: (stop.key || '').indexOf('hotel') === 0 ? 'hotel' : 'attr' });
    }));
    state.map.setMarkers(markers);
    state.map.setRoute({ days: plan.days });
    state.map.fit();
  }

  /* ============================ Data sources ============================ */
  // 启动预热进度：服务一开就在后台抓，这里显示当前城市与累计新增
  function warmupLine(w) {
    if (!w || !w.running) return '';
    const total = w.total || 0, index = w.index || 0;
    const pct = total ? Math.min(100, Math.round((index / total) * 100)) : 0;
    return `<div class="warmup-line">
      <span class="wl-dot"></span>${zh('Startup warm-up', '启动预热')}
      ${zh(`round ${w.round || 1} · ${index}/${total} cities`, `第 ${w.round || 1} 轮 · ${index}/${total} 城`)}
      · ${esc(w.city || '')} · ${zh(`+${w.added || 0} new rows`, `累计新增 ${w.added || 0} 条`)}
      <span class="wl-bar"><i style="width:${pct}%"></i></span>
    </div>`;
  }

  async function loadSources() {
    try {
      const [status, pool, guide, plats] = await Promise.all([API.collectStatus(), API.sources(), API.mapGuide(), API.platforms()]);
      const st = status.state || {};
      const src = pool.builtin || {};
      const cov = src.coverage || (status.coverage || {});
      const cstats = src.cache || {};
      const cache = cstats.by_kind || {};
      const runs = status.runs || [];
      const statusLabel = { ok: 'Healthy', warming: 'Warming up', degraded: 'Degraded' };
      const citySet = new Set();
      runs.forEach((r) => (r.cities || []).forEach((c) => citySet.add(c)));
      const builtinCard = `<div class="source-card wide">
        <div class="sc-head"><b>${esc(src.label || 'Baidu Maps web search (built-in)')}</b>
          <span class="pill ${src.status === 'ok' ? 'ok' : 'warn'}">${esc(statusLabel[src.status] || 'Running')}</span></div>
        <p>${esc(src.note || '')}</p>
        ${warmupLine(pool.warmup)}
        <div class="mini-facts">
          <span class="fact">Attractions <b>${cache.attraction || 0}</b></span>
          <span class="fact">Hotels <b>${cache.hotel || 0}</b></span>
          <span class="fact">Metro <b>${cache.metro || 0}</b></span>
          <span class="fact">Areas <b>${cov.places_scanned || 0}</b> / ${cov.places_discovered || 0}</span>
          <span class="fact">Coverage <b>${Math.round((cov.progress || 0) * 100)}%</b></span>
          <span class="fact">Sweeps <b>${cov.sweeps || 0}</b></span>
        </div>
        <div class="src-fields">${(src.fields || []).map((f) => `<span class="field-tag">${esc(f)}</span>`).join('')}</div>
        <p class="src-note">Source ${esc(src.source_url || '')} · no key · no crawler configuration</p>
      </div>`;
      const mapCards = (pool.optional || []).map((p) => `<div class="source-card">
        <div class="sc-head"><b>${esc(p.label)}</b>
          <span class="pill ${p.configured ? 'ok' : 'idle'}">${p.configured ? 'Configured' : 'Optional'}</span></div>
        <p>Use: ${esc(p.usage)}. Optional: without it the map falls back to the schematic view and routes to local estimates.</p>
        <div class="src-actions">
          <button class="btn sm primary" data-open-config>Configure AK</button>
          <button class="btn sm ghost" data-open-guide>View guide</button>
        </div>
      </div>`).join('');
      const ref = (pool.reference && pool.reference.wikidata) || {};
      const refState = ref.count ? (ref.stale ? 'Snapshot' : 'Live') : 'Warming';
      const refCard = (ref.count || ref.error) ? `<div class="source-card">
        <div class="sc-head"><b>${esc(ref.label || 'Wikidata (official labels)')}</b>
          <span class="pill ${refState === 'Live' ? 'ok' : (refState === 'Snapshot' ? 'warn' : 'idle')}">${refState}</span></div>
        <p>${esc(ref.note || '')}</p>
        <div class="mini-facts">
          <span class="fact">Sites <b>${ref.count || 0}</b></span>
          <span class="fact">License <b>${esc(ref.license || 'CC0 1.0')}</b></span>
          <span class="fact">Updated <b>${esc(String(ref.fetched_at || '').slice(0, 10) || '—')}</b></span>
        </div>
        <p class="src-note">Source ${esc(ref.source_url || 'https://www.wikidata.org/')} · no key · labels only</p>
      </div>` : '';
      const tk = pool.tickets || {};
      const tkState = (tk.cached || 0) > 0 ? 'Live' : 'Warming';
      const ticketCard = tk.name ? `<div class="source-card">
        <div class="sc-head"><b>${esc(tk.label || 'Qunar tickets (direct)')}</b>
          <span class="pill ${tkState === 'Live' ? 'ok' : 'idle'}">${tkState}</span></div>
        <p>${esc(tk.note || '')}</p>
        <div class="mini-facts">
          <span class="fact">Cached <b>${tk.cached || 0}</b></span>
          <span class="fact">With price <b>${tk.with_price || 0}</b></span>
          <span class="fact">With score <b>${tk.with_score || 0}</b></span>
        </div>
        <p class="src-note">Source ${esc(tk.source_url || 'https://piao.qunar.com/')} · no key · ticket price + score</p>
      </div>` : '';
      $('#sourceGrid').innerHTML = builtinCard + refCard + ticketCard + mapCards;
      renderGuide(guide || {});
      renderPlatforms((plats && plats.platforms) || []);
      bindSourcePanel();
      $('#runTable').querySelector('tbody').innerHTML = runs.slice(0, 8).map((r) => {
        const cities = (r.cities || []).join('、') || '—';
        return `<tr><td>${esc(String(r.started_at || '').replace('T', ' ').slice(0, 19))}</td>
          <td>${esc(r.trigger || '')}</td>
          <td>${esc(cities)}</td>
          <td><span class="pill ${r.status === 'ok' ? 'ok' : 'warn'}">${esc(r.status || '')}</span></td>
          <td>${r.items_seen || 0}</td><td>${r.items_new || 0}</td></tr>`;
      }).join('') || '<tr><td colspan="6" style="color:#7c9099">No crawl runs yet; the first sweep starts when the service starts</td></tr>';
      $('#sourceMeta').textContent = `Dynamic national sweep · ${cov.places_discovered || 0} areas discovered · ${cov.places_scanned || 0} scanned · progress ${Math.round((cov.progress || 0) * 100)}%`;
    } catch (err) {
      toast('Could not read data source status: ' + err.message, 'err');
    }
  }

  function renderPlatforms(rows) {
    const box = $('#platformGrid');
    if (!box) return;
    state.platformRows = rows || [];
    box.innerHTML = rows.map((p) => {
      const stateText = p.price ? 'Live price' : (p.rating ? 'Ratings only' : 'Blocked');
      const cls = p.price ? 'ok' : (p.rating ? 'warn' : 'idle');
      return `<div class="platform-card">
        <div class="sc-head"><b>${esc(p.label)}</b><span class="pill ${cls}">${stateText}</span></div>
        <p>${esc(isZh() ? (p.note_zh || p.note) : (p.note || p.note_zh) || p.mode || '')}</p>
      </div>`;
    }).join('') || '<p class="platform-note">Platform status unavailable.</p>';
  }

  function renderGuide(guide) {
    const box = $('#mapGuide');
    if (!box) return;
    const steps = (guide.steps || []).map((s, i) => `<div class="guide-step"><b>${i + 1}</b><div><strong>${esc(s.title)}</strong><p>${esc(s.detail)}</p></div></div>`).join('');
    const errors = (guide.errors || []).map((e) => `<tr><td><code>${esc(e.code)}</code></td><td>${esc(e.reason)}</td><td>${esc(e.fix)}</td></tr>`).join('');
    const links = (guide.links || []).map((l) => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)}</a>`).join('');
    const verify = (guide.verification || []).map((v) => `<li>${esc(v)}</li>`).join('');
    const notes = (guide.notes || []).map((n) => `<li>${esc(n)}</li>`).join('');
    const flow = ['Register & verify', 'Create browser app', 'Enable JS API', 'Whitelist *', 'Copy AK', 'Paste & test'];
    const flowHtml = flow.map((f, i) => `<span>${esc(f)}</span>${i < flow.length - 1 ? '<i>→</i>' : ''}`).join('');
    box.innerHTML = `<p class="guide-intro">${esc(guide.intro || '')}</p>
      <div class="guide-flow">${flowHtml}</div>
      <div class="guide-links">${links}</div>
      <div class="guide-steps">${steps}</div>
      <div class="guide-block"><h5>How to verify</h5><ol>${verify}</ol></div>
      <div class="table-wrap"><table class="cmp guide-errors">
        <thead><tr><th>Error</th><th>Cause</th><th>Fix</th></tr></thead><tbody>${errors}</tbody></table></div>
      <div class="guide-block"><h5>Notes</h5><ul>${notes}</ul></div>`;
  }

  function bindSourcePanel() {
    const grid = $('#sourceGrid');
    grid.querySelectorAll('[data-open-config]').forEach((btn) => btn.addEventListener('click', () => openConfigGuide()));
    grid.querySelectorAll('[data-open-guide]').forEach((btn) => btn.addEventListener('click', () => {
      const head = document.querySelector('[data-panel="guide"]');
      if (head) {
        head.closest('.panel').classList.remove('collapsed');
        head.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }));
    const clearBtn = $('#clearCacheBtn');
    if (clearBtn && !clearBtn.dataset.bound) {
      clearBtn.dataset.bound = '1';
      clearBtn.addEventListener('click', async () => {
        if (!window.confirm('Clear all crawl snapshots under data/cache? They will be re-fetched from the network.')) return;
        try {
          const res = await API.liveCache('clear');
          toast(`Cleared ${res.removed} area snapshots`, 'ok');
          await loadSources();
        } catch (err) { toast('Clear failed: ' + err.message, 'err'); }
      });
    }
  }

  async function testBaiduAk() {
    const btn = $('#cfgTest');
    const hint = $('#cfgHint');
    const ak = ($('#cfgJsAk').value || '').trim();
    if (!ak) { hint.textContent = 'Paste the browser-side AK first'; hint.className = 'cfg-hint err'; return; }
    btn.disabled = true; btn.textContent = 'Testing…';
    hint.textContent = 'Loading the Baidu Maps JS API for real…'; hint.className = 'cfg-hint';
    const started = Date.now();
    const result = await new Promise((resolve) => {
      const cb = '__travelAkProbe' + Date.now();
      let done = false;
      const timer = setTimeout(() => { if (!done) { done = true; cleanup(); resolve({ ok: false, message: 'Load timed out (15 s)' }); } }, 15000);
      function cleanup() { clearTimeout(timer); try { delete window[cb]; } catch (e) { /* ignore */ } }
      window[cb] = () => { if (!done) { done = true; cleanup(); resolve({ ok: true }); } };
      const script = document.createElement('script');
      script.src = 'https://api.map.baidu.com/api?v=3.0&type=webgl&ak=' + encodeURIComponent(ak) + '&callback=' + cb;
      script.onerror = () => { if (!done) { done = true; cleanup(); resolve({ ok: false, message: 'Script failed to load (network or invalid AK)' }); } };
      document.head.appendChild(script);
    });
    btn.disabled = false; btn.textContent = 'Test AK';
    if (result.ok && (window.BMapGL || window.BMap)) {
      hint.textContent = `AK works: Baidu Maps JS API loaded in ${Date.now() - started} ms. Save, then reload to enable the real basemap`;
      hint.className = 'cfg-hint ok';
    } else {
      hint.textContent = 'Verification failed: ' + (result.message || 'Invalid AK or service not enabled') + '. Check the error table below.';
      hint.className = 'cfg-hint err';
    }
  }

  async function waitCollect(prevFinished, timeoutMs) {
    const limit = timeoutMs || 60000;
    const started = Date.now();
    while (Date.now() - started < limit) {
      await new Promise((r) => setTimeout(r, 1500));
      try {
        const st = await API.collectStatus();
        const state2 = st.state || {};
        if (!state2.running && state2.last_finished_at && state2.last_finished_at !== prevFinished) return state2;
      } catch (e) { /* keep waiting */ }
    }
    return null;
  }

  async function collectNow() {
    const btn = $('#collectNow');
    btn.disabled = true; btn.textContent = 'Fetching…';
    try {
      let prev = '';
      try { prev = (await API.collectStatus()).state.last_finished_at || ''; } catch (e) { /* ignore */ }
      const res = await API.collect(state.city || '');
      toast(res.status === 'running' ? 'A fetch is already running; the page refreshes when it finishes' : 'Fetch started; refreshing when it finishes…', 'ok');
      const state2 = await waitCollect(prev);
      const fresh = await API.meta();
      state.meta = fresh; renderMeta(fresh);
      await Promise.all([loadAttractions(true), loadHotels(true)]);
      await loadSources();
      if (state2) {
        toast(`Fetch finished: ${(state2.last_cities || []).join(', ') || 'current city'}, ${(state2.last_counts || {}).seen || 0} records processed`, 'ok');
      } else {
        toast('Fetch still running; click Refresh later to see results', 'warn');
      }
    } catch (err) {
      toast('Fetch failed: ' + err.message, 'err');
    } finally {
      btn.disabled = false; btn.textContent = 'Fetch this city now';
    }
  }

  /* ============================ Geolocation ============================ */
  function locate() {
    const done = (point, sourceLabel) => {
      if (!point) { toast('Locate failed: permission denied or unsupported', 'err'); return; }
      state.origin = Object.assign({ name: 'My location' }, point);
      if (state.map) { state.map.setLocate(point); state.map.focus(point.lat, point.lng); }
      $('#mapPanel').classList.add('open');
      const nearest = state.attr.items.slice().sort((x, y) => (distanceKm(point, x) || 9e9) - (distanceKm(point, y) || 9e9))[0];
      toast(`Located via ${sourceLabel}` + (nearest ? `, nearest attraction: ${nearest.name}` : ''), 'ok');
      renderAttractions();
      loadHotels(true);
    };
    if (state.mapMode === 'baidu' && state.map && state.map.locate) {
      state.map.locate((p) => (p ? done(p, 'Baidu Maps location') : browserLocate(done)));
    } else {
      browserLocate(done);
    }
  }
  function browserLocate(done) {
    if (!navigator.geolocation) return done(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => done(TravelMap.wgs84ToGcj02(pos.coords.latitude, pos.coords.longitude)),
      () => done(null), { timeout: 8000, maximumAge: 60000 });
  }

  /* ============================ Event bindings ============================ */
  function openSettings() {
    const drawer = $('#settingsDrawer');
    const mask = $('#settingsMask');
    if (!drawer) return;
    drawer.classList.add('open');
    if (mask) mask.classList.add('on');
    drawer.setAttribute('aria-hidden', 'false');
    loadSources();
  }

  function closeSettings() {
    const drawer = $('#settingsDrawer');
    const mask = $('#settingsMask');
    if (!drawer) return;
    drawer.classList.remove('open');
    if (mask) mask.classList.remove('on');
    drawer.setAttribute('aria-hidden', 'true');
  }

  function openSearch(prefill) {
    const mask = $('#searchMask');
    if (!mask) return;
    mask.classList.add('open');
    const field = $('#searchField');
    if (prefill) field.value = prefill;
    setTimeout(() => field.focus(), 30);
    if (field.value.trim()) runSearch(true);
  }

  function closeSearch() {
    const mask = $('#searchMask');
    if (mask) mask.classList.remove('open');
  }

  function highlightText(text, query) {
    const source = String(text || '');
    const raw = String(query || '').trim();
    if (!raw) return esc(source);
    const index = source.toLowerCase().indexOf(raw.toLowerCase());
    if (index < 0) return esc(source);
    return esc(source.slice(0, index)) + '<mark>' + esc(source.slice(index, index + raw.length))
      + '</mark>' + esc(source.slice(index + raw.length));
  }

  async function runSearch(reset) {
    const field = $('#searchField');
    const q = (field.value || '').trim();
    const stateSearch = state.search;
    if (!q) {
      $('#searchResults').innerHTML = '';
      $('#searchMeta').textContent = 'Type at least two characters; results span every tracked city.';
      $('#searchMore').style.display = 'none';
      stateSearch.items = []; stateSearch.total = 0;
      return;
    }
    if (reset) { stateSearch.page = 1; stateSearch.items = []; }
    const seq = ++stateSearch.seq;
    stateSearch.busy = true;
    $('#searchMeta').textContent = 'Searching…';
    try {
      const data = await API.search(q, stateSearch.kind, stateSearch.page, 20);
      if (seq !== stateSearch.seq) return;
      stateSearch.total = data.total || 0;
      stateSearch.q = q;
      stateSearch.items = reset ? (data.items || []) : stateSearch.items.concat(data.items || []);
      renderSearchResults(q);
      const scope = stateSearch.kind === 'hotel' ? 'hotels' : (stateSearch.kind === 'attraction' ? 'attractions' : 'attractions and hotels');
      const shown = stateSearch.items.length;
      $('#searchMeta').textContent = `${data.total || 0} ${scope} across ${data.cities || 0} cities`
        + (shown < (data.total || 0) ? ` · showing ${shown}` : '')
        + (data.source === 'live' ? ' · live crawl' : ' · last snapshot');
      $('#searchMore').style.display = shown < stateSearch.total ? 'inline-flex' : 'none';
    } catch (err) {
      if (seq !== stateSearch.seq) return;
      $('#searchResults').innerHTML = `<div class="search-empty"><b>Search failed</b>${esc(err.message)}</div>`;
      $('#searchMeta').textContent = 'Search failed';
    } finally {
      stateSearch.busy = false;
    }
  }

  function renderSearchResults(q) {
    const rows = state.search.items || [];
    const box = $('#searchResults');
    if (!rows.length) {
      box.innerHTML = `<div class="search-empty"><b>No matches</b>Try a shorter name, a brand, or a landmark such as "Disney" / "故宫".</div>`;
      return;
    }
    box.innerHTML = rows.map((item) => {
      const isHotel = item.kind === 'hotel' || Boolean(item.star);
      const price = item.price === null || item.price === undefined
        ? (isHotel ? 'Rate pending' : 'Price pending')
        : money(item.price) + (isHotel ? '/night' : '');
      const score = item.rating == null ? '—' : `★ ${Number(item.rating).toFixed(1)}`;
      const city = isZh() ? (item.city || item.city_en || '') : (item.city_en || item.city || '');
      const key = isHotel ? (item.id || '') : (item.key || '');
      const source = item.price
        ? (isZh() ? (item.price_source_zh || item.price_source || '') : (item.price_source_en || item.price_source || ''))
        : '';
      const transit = item.transit_stop ? '<i class="sr-transit">Transit stop</i>' : '';
      return `<div class="sr-item">
        <div class="sr-kind ${isHotel ? 'hotel' : ''}">${isHotel ? 'Hotel' : 'Attraction'}</div>
        <div class="sr-main">
          <b>${highlightText(item.name || '', q)}${transit}</b>
          <span>${city ? esc(city) + ' · ' : ''}${score} · ${price}${source ? ' · ' + esc(source) : ''}</span>
          ${tagDisplay(item).length ? `<span class="sr-tags">${tagDisplay(item).slice(0, 3).map((t) => `<i>${esc(t)}</i>`).join('')}</span>` : ''}
        </div>
        <div class="sr-actions">
          <button class="btn sm" data-search-detail="${esc(key)}" data-kind="${isHotel ? 'hotel' : 'attraction'}">Details</button>
          ${isHotel
            ? `<button class="btn sm" data-search-near-hotel="${esc(key)}">Attractions nearby</button>`
            : `<button class="btn sm primary" data-search-near="${esc(key)}">Hotels nearby</button>`}
        </div>
      </div>`;
    }).join('');
  }

  function showHotelsNear(key) {
    const item = (state.search.items || []).find((row) => (row.key || row.id) === key);
    if (!item) return;
    closeSearch();
    if (item.city && item.city !== state.city) {
      state.city = item.city;
      $$('#cityChips .chip').forEach((c) => c.classList.toggle('on', c.dataset.city === item.city));
      $$('#sideCities .side-city').forEach((c) => c.classList.toggle('on', c.dataset.scity === item.city));
    }
    state.hotel.nearKey = item.key || '';
    state.hotel.near = 0;
    state.hotel.sort = 'distance';
    // 接口用 distance 排序，界面高亮「Closest to attraction」这一档
    $$('#hotelSort button').forEach((b) => b.classList.toggle('on', b.dataset.sort === 'near'));
    const select = $('#nearAttraction');
    if (select) {
      const option = document.createElement('option');
      option.value = item.key || '';
      option.textContent = `${item.name} (${item.city || ''})`;
      if (!Array.from(select.options).some((o) => o.value === option.value)) select.appendChild(option);
      select.value = option.value;
    }
    updateHotelSummary();
    loadHotels(true);
    document.getElementById('hotels').scrollIntoView({ behavior: 'smooth', block: 'start' });
    toast(`Nearby hotels around ${item.name}`, 'ok');
  }

  function showAttractionsNear(hotelId) {
    const item = (state.search.items || []).find((row) => row.id === hotelId || row.key === hotelId);
    if (!item) return;
    closeSearch();
    const city = item.city || state.city;
    if (item.lat == null || item.lng == null) { toast('No coordinates for this hotel', 'err'); return; }
    state.city = city;
    state.keyword = '';
    state.attr.anchor = { lat: item.lat, lng: item.lng, name: item.name };
    state.attr.near = false;
    state.attr.sort = 'distance';
    $$('#attrSort button').forEach((b) => b.classList.toggle('on', b.dataset.sort === 'distance'));
    $$('#cityChips .chip').forEach((c) => c.classList.toggle('on', c.dataset.city === city));
    $$('#sideCities .side-city').forEach((c) => c.classList.toggle('on', c.dataset.scity === city));
    loadAttractions(true).then(() => {
      document.getElementById('attractions').scrollIntoView({ behavior: 'smooth', block: 'start' });
      toast(`Attractions near ${item.name}`, 'ok');
    });
  }

  function bindGlobal() {
    // Sidebar navigation
    $('#sideNav').addEventListener('click', (ev) => {
      const drawerBtn = ev.target.closest('[data-drawer]');
      if (drawerBtn) { openSettings(); closeSidebar(); return; }
      const btn = ev.target.closest('[data-target]');
      if (!btn) return;
      const target = document.getElementById(btn.dataset.target);
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      closeSidebar();
    });
    $('#hamburger').addEventListener('click', () => { $('#sidebar').classList.add('open'); $('#sidebarBackdrop').classList.add('on'); });
    $('#sideClose').addEventListener('click', closeSidebar);
    $('#sidebarBackdrop').addEventListener('click', closeSidebar);

    // Collapse panels
    document.addEventListener('click', (ev) => {
      const head = ev.target.closest('[data-panel]');
      if (head) {
        const panel = head.closest('.panel');
        panel.classList.toggle('collapsed');
        return;
      }
      const groupBtn = ev.target.closest('[data-toggle-group]');
      if (groupBtn) {
        const group = groupBtn.closest('.filter-group');
        const body = group.querySelector('.chips, .range-row');
        const hidden = body.style.display === 'none';
        group.querySelectorAll('.chips, .range-row').forEach((n) => { n.style.display = hidden ? '' : 'none'; });
        groupBtn.textContent = hidden ? 'Collapse' : 'Expand';
      }
    });
    $('#attrFilterToggle').addEventListener('click', () => {
      const panel = $('#attrFilterPanel');
      panel.classList.toggle('collapsed');
      $('#attrFilterToggle').textContent = panel.classList.contains('collapsed') ? 'Show filters' : 'Hide filters';
    });

    // Search
    let timer = null;
    $('#searchInput').addEventListener('input', (ev) => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        state.keyword = ev.target.value.trim();
        loadAttractions(true); loadHotels(true); renderComparePickers();
      }, 360);
    });

    // Any city / nationwide query
    const cityGo = $('#cityGo');
    const cityInput = $('#cityInput');
    const applyCityInput = () => {
      const value = (cityInput && cityInput.value || '').trim();
      state.city = value;
      $$('#cityChips .chip').forEach((c) => c.classList.toggle('on', c.dataset.city === value));
      $$('#sideCities .side-city').forEach((c) => c.classList.toggle('on', c.dataset.scity === value));
      state.hotel.nearKey = '';
      loadAttractions(true); loadHotels(true); renderComparePickers();
      if (state.mode === 'global' && value) {
        API.meta().then((m) => { state.meta = m; renderMeta(m); }).catch(() => {});
      }
      toast(value ? `Switched to ${value}; live data` : 'Switched to nationwide coverage', 'ok');
    };
    if (cityGo) cityGo.addEventListener('click', applyCityInput);
    if (cityInput) cityInput.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') applyCityInput(); });

    // City (sidebar + filters)
    document.addEventListener('click', (ev) => {
      const cityBtn = ev.target.closest('[data-city], [data-scity]');
      if (!cityBtn) return;
      const city = cityBtn.dataset.city !== undefined ? cityBtn.dataset.city : cityBtn.dataset.scity;
      state.city = city;
      $$('#cityChips .chip').forEach((c) => c.classList.toggle('on', c.dataset.city === city));
      $$('#sideCities .side-city').forEach((c) => c.classList.toggle('on', c.dataset.scity === city));
      state.hotel.nearKey = '';
      loadAttractions(true); loadHotels(true); renderComparePickers();
    });

    // Rating
    $('#ratingChips').addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-rating]'); if (!b) return;
      $$('#ratingChips .chip').forEach((c) => c.classList.remove('on')); b.classList.add('on');
      state.attr.minRating = Number(b.dataset.rating) || 0; loadAttractions(true);
    });
    // Price presets
    $('#priceQuick').addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-price]'); if (!b) return;
      const [lo, hi] = b.dataset.price.split(',');
      state.attr.minPrice = lo; state.attr.maxPrice = hi;
      $('#minPrice').value = lo; $('#maxPrice').value = hi;
      $$('#priceQuick .chip').forEach((c) => c.classList.remove('on')); b.classList.add('on');
      loadAttractions(true);
    });
    $('#minPrice').addEventListener('change', (e) => { state.attr.minPrice = e.target.value; loadAttractions(true); });
    $('#maxPrice').addEventListener('change', (e) => { state.attr.maxPrice = e.target.value; loadAttractions(true); });

    // A-level, tags, features
    $('#levelChips').addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-level]'); if (!b) return;
      const on = b.classList.contains('on');
      $$('#levelChips .chip').forEach((c) => c.classList.remove('on'));
      if (!on) b.classList.add('on');
      state.attr.level = on ? '' : b.dataset.level; loadAttractions(true);
    });
    $('#tagChips').addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-tag]'); if (!b) return;
      const tag = b.dataset.tag, idx = state.attr.tags.indexOf(tag);
      if (idx >= 0) { state.attr.tags.splice(idx, 1); b.classList.remove('on'); } else { state.attr.tags.push(tag); b.classList.add('on'); }
      loadAttractions(true);
    });
    document.addEventListener('click', (ev) => {
      if (ev.target.closest('[data-clear-tags]')) {
        state.attr.tags = []; $$('#tagChips .chip').forEach((c) => c.classList.remove('on')); loadAttractions(true);
      }
    });
    document.querySelectorAll('[data-flag]').forEach((b) => b.addEventListener('click', () => {
      const f = b.dataset.flag;
      if (state.attr.flags.has(f)) { state.attr.flags.delete(f); b.classList.remove('on'); } else { state.attr.flags.add(f); b.classList.add('on'); }
      loadAttractions(true);
    }));
    $('#nearSwitch').addEventListener('click', () => {
      if (!state.origin) { toast('Click Locate to get your current position'); return; }
      state.attr.near = !state.attr.near;
      $('#nearSwitch').classList.toggle('on', state.attr.near);
      loadAttractions(true);
    });

    // Sorting
    $('#attrSort').addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-sort]'); if (!b) return;
      if (b.dataset.sort === 'distance' && !state.origin) { toast('Locate first to sort by distance'); return; }
      $$('#attrSort button').forEach((x) => x.classList.remove('on')); b.classList.add('on');
      state.attr.sort = b.dataset.sort; loadAttractions(true);
    });
    $('#hotelSort').addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-sort]'); if (!b) return;
      $$('#hotelSort button').forEach((x) => x.classList.remove('on')); b.classList.add('on');
      state.hotel.sort = b.dataset.sort === 'near' ? 'distance' : b.dataset.sort;
      loadHotels(true);
    });

    // Hotel filters
    const hotelChipGroup = (selector, dataKey, field, cast) => {
      $(selector).addEventListener('click', (ev) => {
        const b = ev.target.closest('[data-' + dataKey + ']'); if (!b) return;
        $$(selector + ' .chip').forEach((c) => c.classList.remove('on')); b.classList.add('on');
        state.hotel[field] = cast ? Number(b.dataset[dataKey]) : b.dataset[dataKey];
        loadHotels(true);
      });
    };
    hotelChipGroup('#starChips', 'star', 'star', true);
    hotelChipGroup('#hotelRatingChips', 'hrating', 'rating', true);
    hotelChipGroup('#metroChips', 'metro', 'metro', true);
    hotelChipGroup('#hotelNearChips', 'near', 'near', true);
    $('#hotelPriceQuick').addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-price]'); if (!b) return;
      const [lo, hi] = b.dataset.price.split(',');
      state.hotel.minPrice = lo; state.hotel.maxPrice = hi;
      $('#hotelMinPrice').value = lo; $('#hotelMaxPrice').value = hi;
      $$('#hotelPriceQuick .chip').forEach((c) => c.classList.remove('on')); b.classList.add('on');
      loadHotels(true);
    });
    $('#hotelMinPrice').addEventListener('change', (e) => { state.hotel.minPrice = e.target.value; loadHotels(true); });
    $('#hotelMaxPrice').addEventListener('change', (e) => { state.hotel.maxPrice = e.target.value; loadHotels(true); });
    $('#nearAttraction').addEventListener('change', (e) => { state.hotel.nearKey = e.target.value; loadHotels(true); });
    const nearAllBtn = $('#nearAll');
    if (nearAllBtn) nearAllBtn.addEventListener('click', loadAllNearAttractions);
    const nearFilter = $('#nearFilter');
    if (nearFilter) {
      nearFilter.addEventListener('input', () => {
        const q = nearFilter.value.trim().toLowerCase();
        const base = state.nearOptions.length ? state.nearOptions : state.attr.items;
        const rows = q ? base.filter((i) => String(i.name || '').toLowerCase().includes(q)) : base;
        fillNearOptions(rows.slice(0, 400));
      });
    }

    // Card interactions
    document.addEventListener('click', (ev) => {
      const addAttr = ev.target.closest('[data-attr-add]');
      if (addAttr) { addToTrip(addAttr.dataset.attrAdd, 'attraction'); return; }
      const addHotel = ev.target.closest('[data-hotel-add]');
      if (addHotel) { addToTrip(addHotel.dataset.hotelAdd, 'hotel'); return; }
      const dAttr = ev.target.closest('[data-attr-detail]');
      if (dAttr) { openAttrDetail(dAttr.dataset.attrDetail); return; }
      const dHotel = ev.target.closest('[data-hotel-detail]');
      if (dHotel) { openHotelDetail(dHotel.dataset.hotelDetail); return; }
      const cardAttr = ev.target.closest('[data-attr]');
      if (cardAttr) { openAttrDetail(cardAttr.dataset.attr); return; }
      const cardHotel = ev.target.closest('[data-hotel]');
      if (cardHotel) { openHotelDetail(cardHotel.dataset.hotel); return; }
      const cmpAttr = ev.target.closest('[data-cmp-attr]');
      if (cmpAttr) {
        const k = cmpAttr.dataset.cmpAttr;
        if (state.cmp.attrs.has(k)) state.cmp.attrs.delete(k); else { if (state.cmp.attrs.size >= 6) return toast('Up to 6 attractions'); state.cmp.attrs.add(k); }
        cmpAttr.classList.toggle('on'); return;
      }
      const cmpHotel = ev.target.closest('[data-cmp-hotel]');
      if (cmpHotel) {
        const k = cmpHotel.dataset.cmpHotel;
        if (state.cmp.hotels.has(k)) state.cmp.hotels.delete(k); else { if (state.cmp.hotels.size >= 8) return toast('Up to 8 hotels'); state.cmp.hotels.add(k); }
        cmpHotel.classList.toggle('on'); return;
      }
    });

    // Pagination
    $('#attrMore').addEventListener('click', () => { state.attr.page += 1; loadAttractions(false); });
    $('#hotelMore').addEventListener('click', () => { state.hotel.page += 1; loadHotels(false); });

    // Price comparison
    $('#cmpRun').addEventListener('click', runCompare);
    $('#cmpClear').addEventListener('click', () => {
      state.cmp.attrs.clear(); state.cmp.hotels.clear();
      $$('#cmpAttrList .chip, #cmpHotelList .chip').forEach((c) => c.classList.remove('on'));
      $('#cmpResult').innerHTML = '';
    });

    // Trip
    $('#tripJump').addEventListener('click', () => document.getElementById('trip').scrollIntoView({ behavior: 'smooth' }));
$('#planBtn').addEventListener('click', runPlan);
    $('#tripExport').addEventListener('click', exportTrip);
    $('#tripImport').addEventListener('click', () => $('#tripFileInput').click());
    $('#tripFileInput').addEventListener('change', async (ev) => {
      const file = ev.target.files && ev.target.files[0];
      ev.target.value = '';
      if (file) await importTripFile(file);
    });
    $('#tripNewDay').addEventListener('click', async () => {
      if (!state.trip || !state.trip.items.length) return toast('Add at least one place first');
      const items = state.trip.items.map((i) => ({ id: i.id, day: i.day || 1, seq: i.seq || 0, visit_minutes: i.visit_minutes || 0 }));
      items[items.length - 1].day = (items[items.length - 1].day || 1) + 1;
      try { await API.updateItems(state.tripId, items); await refreshTrip(); toast('Day added'); }
      catch (err) { toast('Action failed: ' + err.message, 'err'); }
    });

    // Data sources
    $('#collectNow').addEventListener('click', collectNow);

    // Map
    $('#mapToggle').addEventListener('click', () => $('#mapPanel').classList.toggle('open'));
    $('#mapFab').addEventListener('click', () => $('#mapPanel').classList.toggle('open'));
    $('#closeMap').addEventListener('click', () => $('#mapPanel').classList.remove('open'));
    $('#locateBtn').addEventListener('click', locate);
    const transportGo = $('#transportGo');
    if (transportGo) transportGo.addEventListener('click', runTransport);
    const transportResult = $('#transportResult');
    if (transportResult) {
      transportResult.addEventListener('click', (ev) => {
        const pick = ev.target.closest('[data-transport-pick]');
        if (!pick) return;
        state.transport.chosen = pick.dataset.transportPick;
        renderTransport();
      });
    }
    const refreshBtn = $('#refreshBtn');
    if (refreshBtn) refreshBtn.addEventListener('click', refreshNow);
    const fontBtn = $('#fontBtn');
    if (fontBtn) fontBtn.addEventListener('click', toggleFontMode);
    const fontDrawer = $('#fontBtnDrawer');
    if (fontDrawer) fontDrawer.addEventListener('click', toggleFontMode);
    applyFontMode(localStorage.getItem('travelone.font') || 'normal');
    const cfgBtn = $('#mapConfigBtn');
    if (cfgBtn) cfgBtn.addEventListener('click', openConfigGuide);
    const cfgSaveBtn = $('#cfgSave');
    if (cfgSaveBtn) cfgSaveBtn.addEventListener('click', saveMapConfig);
    const cfgLaterBtn = $('#cfgLater');
    if (cfgLaterBtn) cfgLaterBtn.addEventListener('click', () => $('#configMask').classList.remove('open'));
    const cfgMask = $('#configMask');
    if (cfgMask) cfgMask.addEventListener('click', (ev) => { if (ev.target.id === 'configMask') cfgMask.classList.remove('open'); });
    document.addEventListener('click', (ev) => {
      const closeBtn = ev.target.closest('[data-close="config"]');
      if (closeBtn) $('#configMask').classList.remove('open');
    });
    $('#zoomIn').addEventListener('click', () => state.map && state.map.zoomIn());
    $('#zoomOut').addEventListener('click', () => state.map && state.map.zoomOut());
    $('#fitAll').addEventListener('click', () => state.map && state.map.fit());

    // Back to top
    $('#toTop').addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
    window.addEventListener('scroll', () => {
      $('#toTop').classList.toggle('on', window.scrollY > 420);
    }, { passive: true });

    // Global search
    const searchOpen = $('#searchOpen');
    if (searchOpen) searchOpen.addEventListener('click', () => openSearch(''));
    const modeSwitch = $('#modeSwitch');
    if (modeSwitch) {
      modeSwitch.addEventListener('click', (ev) => {
        const btn = ev.target.closest('[data-mode]');
        if (btn) applyMode(btn.dataset.mode);
      });
    }
    const topSearch = $('#topSearch');
    if (topSearch) topSearch.addEventListener('click', () => openSearch(''));
    const searchKinds = $('#searchKinds');
    if (searchKinds) {
      searchKinds.addEventListener('click', (ev) => {
        const btn = ev.target.closest('[data-skind]');
        if (!btn) return;
        state.search.kind = btn.dataset.skind;
        $$('#searchKinds button').forEach((b) => b.classList.toggle('on', b === btn));
        if (($('#searchField').value || '').trim()) runSearch(true);
      });
    }
    const searchClose = $('#searchClose');
    if (searchClose) searchClose.addEventListener('click', closeSearch);
    const searchMask = $('#searchMask');
    if (searchMask) searchMask.addEventListener('click', (ev) => { if (ev.target.id === 'searchMask') closeSearch(); });
    const searchField = $('#searchField');
    if (searchField) {
      let timer = null;
      searchField.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => runSearch(true), 320);
      });
      searchField.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter') { ev.preventDefault(); runSearch(true); }
      });
    }
    const searchMore = $('#searchMore');
    if (searchMore) searchMore.addEventListener('click', () => { state.search.page += 1; runSearch(false); });
    const searchResults = $('#searchResults');
    if (searchResults) {
      searchResults.addEventListener('click', (ev) => {
        const detailBtn = ev.target.closest('[data-search-detail]');
        if (detailBtn) {
          closeSearch();
          if (detailBtn.dataset.kind === 'hotel') openHotelDetail(detailBtn.dataset.searchDetail);
          else openAttrDetail(detailBtn.dataset.searchDetail);
          return;
        }
        const nearBtn = ev.target.closest('[data-search-near]');
        if (nearBtn) { showHotelsNear(nearBtn.dataset.searchNear); return; }
        const nearHotelBtn = ev.target.closest('[data-search-near-hotel]');
        if (nearHotelBtn) { showAttractionsNear(nearHotelBtn.dataset.searchNearHotel); return; }
      });
    }
    document.addEventListener('keydown', (ev) => {
      if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'k') {
        ev.preventDefault();
        openSearch('');
      }
      if (ev.key === 'Escape') closeSearch();
    });

    // Settings drawer
    const settingsBtn = $('#settingsBtn');
    if (settingsBtn) settingsBtn.addEventListener('click', openSettings);
    const drawerClose = $('#drawerClose');
    if (drawerClose) drawerClose.addEventListener('click', closeSettings);
    const settingsMask = $('#settingsMask');
    if (settingsMask) settingsMask.addEventListener('click', closeSettings);

    // Modals
    $('#detailMask').addEventListener('click', (ev) => { if (ev.target.id === 'detailMask') closeDetail(); });
    document.addEventListener('keydown', (ev) => {
      if (ev.key !== 'Escape') return;
      closeDetail();
      closeSettings();
    });
  }

  function updateAkStatus(cfg) {
    const el = $('#akStatus');
    if (!el) return;
    if (cfg && cfg.ak_configured) {
      el.textContent = 'Browser-side AK configured: ' + (cfg.ak_masked || '••••••••') + ' (saved encrypted)';
      el.className = 'ak-status ok';
    } else {
      el.textContent = 'No AK configured; using the offline schematic map';
      el.className = 'ak-status';
    }
  }

  // AK field: paste only; block copy, cut, context menu, drag and selection
  function bindSecureInput(input) {
    if (!input) return;
    const navKeys = ['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'Home', 'End', 'Tab', 'Enter'];
    input.addEventListener('keydown', (ev) => {
      const key = (ev.key || '').toLowerCase();
      if ((ev.ctrlKey || ev.metaKey) && key === 'v') return;             // allow paste
      if ((ev.ctrlKey || ev.metaKey) && ['c', 'x', 'a', 'insert'].includes(key)) {
        ev.preventDefault(); toast('Copy and select-all are disabled in the AK field', 'err'); return;
      }
      if (navKeys.includes(ev.key)) return;
      ev.preventDefault();
      toast('AK field accepts paste only (Ctrl+V / Cmd+V)', 'err');
    });
    ['copy', 'cut', 'contextmenu', 'dragstart', 'selectstart'].forEach((name) => {
      input.addEventListener(name, (ev) => { ev.preventDefault(); });
    });
    input.addEventListener('paste', () => setTimeout(() => {
      const len = input.value.trim().length;
      const hint = $('#cfgHint');
      if (hint) {
        hint.textContent = len
          ? `Pasted ${len} characters, shown masked. Encrypted locally before saving; only ciphertext is stored.`
          : 'Paste an AK before saving.';
        hint.className = 'cfg-hint';
      }
    }, 30));
  }

  function openConfigGuide() {
    const cfg = state.config || {};
    const js = $('#cfgJsAk');
    const srv = $('#cfgServerAk');
    if (js) js.value = cfg.baidu_js_ak || '';
    if (srv) srv.value = '';
    updateAkStatus(cfg);
    $('#cfgHint').textContent = cfg.ak_configured
      ? 'To replace it, paste a new value; it applies immediately after saving.'
      : 'AKs are stored only on this machine in data/runtime_config.json (encrypted) and never uploaded.';
    $('#cfgHint').className = 'cfg-hint';
    bindSecureInput(js);
    bindSecureInput(srv);
    const testBtn = $('#cfgTest');
    if (testBtn && !testBtn.dataset.bound) {
      testBtn.dataset.bound = '1';
      testBtn.addEventListener('click', testBaiduAk);
    }
    $('#configMask').classList.add('open');
  }

  async function saveMapConfig() {
    const jsAk = $('#cfgJsAk').value.trim();
    const serverAk = $('#cfgServerAk').value.trim();
    if (!jsAk && !serverAk) {
      $('#cfgHint').textContent = 'Enter a browser-side AK first';
      $('#cfgHint').className = 'cfg-hint err';
      return;
    }
    const hint = $('#cfgHint');
    hint.textContent = 'Saving…';
    hint.className = 'cfg-hint';
    try {
      const sealed = await API.encryptPayload({ baidu_js_ak: jsAk, baidu_server_ak: serverAk });
      const res = await API.saveConfig(sealed);
      hint.textContent = res.message || 'Saved';
      hint.className = 'cfg-hint ok';
      state.config = await API.config();
      updateMapNote(state.config);
      updateAkStatus(state.config);
      $('#cfgJsAk').value = state.config.baidu_js_ak || '';
      $('#cfgServerAk').value = '';
      toast(jsAk ? 'AK saved. Reload the page to enable the real basemap.' : 'Server AK saved. Routes now use live Baidu routing.', 'ok');
    } catch (err) {
      hint.textContent = 'Save failed: ' + err.message;
      hint.className = 'cfg-hint err';
    }
  }

  function applyFontMode(mode) {
    const large = mode === 'large';
    document.documentElement.dataset.font = large ? 'large' : 'normal';
    const label = $('#fontLabel');
    // 按钮显示的是「点一下会发生什么」，两种语言下都要走翻译，
    // 否则大字→小字时会被写回英文（用户实际遇到的缺陷）。
    if (label) label.textContent = window.TravelI18n ? window.TravelI18n.t(large ? 'Standard' : 'Larger text') : (large ? 'Standard' : 'Larger text');
    localStorage.setItem('travelone.font', large ? 'large' : 'normal');
  }

  function toggleFontMode() {
    const next = document.documentElement.dataset.font === 'large' ? 'normal' : 'large';
    applyFontMode(next);
    toast(window.TravelI18n ? window.TravelI18n.t(next === 'large' ? 'Larger text on' : 'Standard text on') : (next === 'large' ? 'Larger text on' : 'Standard text on'), 'ok');
  }

  async function refreshNow() {
    const btn = $('#refreshBtn');
    const label = $('#refreshLabel');
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    randomHeroTip();          // 刷新一开始就换一条，不必等抓取跑完
    const original = label ? label.textContent : 'Refresh';
    if (label) label.textContent = 'Refreshing…';
    try {
      let prev = '';
      try { prev = (await API.collectStatus()).state.last_finished_at || ''; } catch (e) { /* ignore */ }
      const res = await API.collect(state.city || '');
      toast(res.status === 'running' ? 'A fetch is already running; waiting for it…' : 'Started fetching this city…', 'ok');
      const state2 = await waitCollect(prev);
      const fresh = await API.meta();
      state.meta = fresh;
      renderMeta(fresh);
      await Promise.all([loadAttractions(true), loadHotels(true)]);
      await loadSources();
      randomHeroTip();
      const stamp = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
      toast(state2
        ? `Refreshed: ${(state2.last_counts || {}).seen || 0} records processed (${stamp})`
        : 'Fetch still running; it will update automatically', state2 ? 'ok' : 'warn');
      btn.title = `Last refreshed ${stamp}`;
    } catch (err) {
      toast('Refresh failed: ' + err.message, 'err');
    } finally {
      btn.disabled = false;
      if (label) label.textContent = original || 'Refresh';
    }
  }

  function closeSidebar() {
    $('#sidebar').classList.remove('open');
    $('#sidebarBackdrop').classList.remove('on');
  }

  function initScrollSpy() {
    const ids = ['overview', 'attractions', 'hotels', 'compare', 'trip'];
    const labels = { overview: 'Overview', attractions: 'Attractions', hotels: 'Hotels', compare: 'Price comparison', trip: 'Trip & route' };
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const id = entry.target.id;
        $$('#sideNav .nav-item').forEach((b) => b.classList.toggle('active', b.dataset.target === id));
        $('#crumbNow').textContent = labels[id] || '';
      });
    }, { rootMargin: '-45% 0px -50% 0px', threshold: 0 });
    ids.forEach((id) => { const el = document.getElementById(id); if (el) observer.observe(el); });
  }

  document.addEventListener('DOMContentLoaded', init);
})();