/* Copyright (c) 2026 黄豆666/huangdouplone
 * SPDX-License-Identifier: MIT */
/* TravelOne map: Baidu Maps when an AK is configured, with an offline schematic fallback */
(function () {
  const X_PI = Math.PI * 3000 / 180;
  const EE = 0.00669342162296594323;
  const AXIS = 6378245.0;

  /* ------------------------------ Coordinate conversion ------------------------------ */
  function gcj02ToBd09(lat, lng) {
    const z = Math.sqrt(lng * lng + lat * lat) + 0.00002 * Math.sin(lat * X_PI);
    const theta = Math.atan2(lat, lng) + 0.000003 * Math.cos(lng * X_PI);
    return { lat: z * Math.sin(theta) + 0.006, lng: z * Math.cos(theta) + 0.0065 };
  }
  function bd09ToGcj02(lat, lng) {
    const x = lng - 0.0065, y = lat - 0.006;
    const z = Math.sqrt(x * x + y * y) - 0.00002 * Math.sin(y * X_PI);
    const theta = Math.atan2(y, x) - 0.000003 * Math.cos(x * X_PI);
    return { lat: z * Math.sin(theta), lng: z * Math.cos(theta) };
  }
  function transformLat(x, y) {
    let ret = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
    ret += (20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2 / 3;
    ret += (20 * Math.sin(y * Math.PI) + 40 * Math.sin(y / 3 * Math.PI)) * 2 / 3;
    ret += (160 * Math.sin(y / 12 * Math.PI) + 320 * Math.sin(y * Math.PI / 30)) * 2 / 3;
    return ret;
  }
  function transformLng(x, y) {
    let ret = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
    ret += (20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2 / 3;
    ret += (20 * Math.sin(x * Math.PI) + 40 * Math.sin(x / 3 * Math.PI)) * 2 / 3;
    ret += (150 * Math.sin(x / 12 * Math.PI) + 300 * Math.sin(x / 30 * Math.PI)) * 2 / 3;
    return ret;
  }
  function wgs84ToGcj02(lat, lng) {
    if (lng < 73 || lng > 135 || lat < 18 || lat > 54) return { lat, lng };
    let dLat = transformLat(lng - 105, lat - 35);
    let dLng = transformLng(lng - 105, lat - 35);
    const radLat = lat / 180 * Math.PI;
    let magic = Math.sin(radLat);
    magic = 1 - EE * magic * magic;
    const sqrtMagic = Math.sqrt(magic);
    dLat = (dLat * 180) / ((AXIS * (1 - EE)) / (magic * sqrtMagic) * Math.PI);
    dLng = (dLng * 180) / (AXIS / sqrtMagic * Math.cos(radLat) * Math.PI);
    return { lat: lat + dLat, lng: lng + dLng };
  }

  /* ------------------------------ Offline schematic map ------------------------------ */
  const DAY_COLORS = ['#0d5c52', '#c8843a', '#5b6bb0', '#9d4f38', '#3f7f3f'];

  class OfflineMap {
    constructor(container, options) {
      this.el = container;
      this.options = options || {};
      this.markers = [];
      this.route = null;
      this.locatePoint = null;
      this.zoom = 1;
      this.center = null;
      this.view = { scale: 1, ox: 0, oy: 0 };
      this._bind();
      this.render();
    }

    _bind() {
      this.el.addEventListener('click', (ev) => {
        const node = ev.target.closest('[data-key]');
        if (node && this.options.onMarkerClick) {
          this.options.onMarkerClick(node.getAttribute('data-key'));
        }
      });
      if (typeof ResizeObserver !== 'undefined') {
        this._ro = new ResizeObserver(() => this.render());
        this._ro.observe(this.el);
      } else {
        window.addEventListener('resize', () => this.render());
      }
    }

    setMarkers(markers) { this.markers = markers || []; this.render(); }
    setRoute(route) { this.route = route; this.render(); }
    setLocate(point) { this.locatePoint = point; this.render(); }
    zoomIn() { this.zoom = Math.min(this.zoom * 1.35, 6); this.render(); }
    zoomOut() { this.zoom = Math.max(this.zoom / 1.35, 0.7); this.render(); }
    fit() { this.zoom = 1; this.render(); }

    focus(lat, lng) {
      this.center = { lat, lng };
      this.render();
    }

    _project(lat, lng) {
      const x = lng * Math.PI / 180;
      const y = Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI / 180) / 2));
      return { x, y };
    }

    render() {
      const w = this.el.clientWidth || 360;
      const h = this.el.clientHeight || 480;
      const pts = [];
      this.markers.forEach((m) => { if (isFinite(m.lat) && isFinite(m.lng)) pts.push([m.lat, m.lng]); });
      if (this.route && this.route.days) {
        this.route.days.forEach((day) => (day.legs || []).forEach((leg) => {
          (leg.polyline || []).forEach((p) => {
            const lat = Array.isArray(p) ? p[0] : p.lat;
            const lng = Array.isArray(p) ? p[1] : p.lng;
            if (isFinite(lat) && isFinite(lng)) pts.push([lat, lng]);
          });
        }));
      }
      if (this.locatePoint) pts.push([this.locatePoint.lat, this.locatePoint.lng]);

      let b = null;
      pts.forEach(([lat, lng]) => {
        const p = this._project(lat, lng);
        b = b ? {
          minX: Math.min(b.minX, p.x), maxX: Math.max(b.maxX, p.x),
          minY: Math.min(b.minY, p.y), maxY: Math.max(b.maxY, p.y),
        } : { minX: p.x, maxX: p.x, minY: p.y, maxY: p.y };
      });
      if (!b || (b.maxX - b.minX < 1e-6 && b.maxY - b.minY < 1e-6)) {
        const base = b || this._project(39.915, 116.404);
        b = { minX: base.minX - 0.02, maxX: base.maxX + 0.02, minY: base.minY - 0.015, maxY: base.maxY + 0.015 };
      }
      const padX = (b.maxX - b.minX) * 0.16 || 0.01;
      const padY = (b.maxY - b.minY) * 0.16 || 0.01;
      const minX = b.minX - padX, maxX = b.maxX + padX, minY = b.minY - padY, maxY = b.maxY + padY;
      const spanX = maxX - minX, spanY = maxY - minY;
      const scale = Math.min(w / spanX, h / spanY);
      const px = (x) => (x - (minX + maxX) / 2) * scale + w / 2;
      const py = (y) => h / 2 - (y - (minY + maxY) / 2) * scale;
      this.view = { scale, px, py, w, h };

      const zx = this.center ? px(this._project(this.center.lat, this.center.lng).x) : w / 2;
      const zy = this.center ? py(this._project(this.center.lat, this.center.lng).y) : h / 2;

      const grid = [];
      for (let i = 1; i <= 5; i++) {
        grid.push(`<line x1="0" y1="${(h / 6 * i).toFixed(1)}" x2="${w}" y2="${(h / 6 * i).toFixed(1)}" stroke="#ffffff" stroke-width="1" opacity="0.55"/>`);
        grid.push(`<line x1="${(w / 6 * i).toFixed(1)}" y1="0" x2="${(w / 6 * i).toFixed(1)}" y2="${h}" stroke="#ffffff" stroke-width="1" opacity="0.55"/>`);
      }

      const routeSvg = [];
      if (this.route && this.route.days) {
        this.route.days.forEach((day, di) => {
          const color = DAY_COLORS[di % DAY_COLORS.length];
          (day.legs || []).forEach((leg) => {
            const line = (leg.polyline || []).map((p, idx) => {
              const lat = Array.isArray(p) ? p[0] : p.lat;
              const lng = Array.isArray(p) ? p[1] : p.lng;
              const q = this._project(lat, lng);
              return `${idx === 0 ? 'M' : 'L'}${px(q.x).toFixed(1)},${py(q.y).toFixed(1)}`;
            }).join(' ');
            if (line) {
              routeSvg.push(`<path d="${line}" fill="none" stroke="rgba(255,255,255,.85)" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>`);
              routeSvg.push(`<path d="${line}" fill="none" stroke="${color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>`);
            }
          });
        });
      }

      // Small offsets for very close markers so numbers and labels do not overlap
      const placed = [];
      const dedupe = (x, y) => {
        let nx = x, ny = y, guard = 0;
        while (placed.some((p) => Math.hypot(p.x - nx, p.y - ny) < 17) && guard < 12) {
          const angle = guard * (Math.PI / 3);
          nx = x + Math.cos(angle) * 15;
          ny = y + Math.sin(angle) * 15;
          guard += 1;
        }
        placed.push({ x: nx, y: ny });
        return { x: nx, y: ny };
      };
      const markerSvg = this.markers.map((m, idx) => {
        if (!isFinite(m.lat) || !isFinite(m.lng)) return '';
        const q = this._project(m.lat, m.lng);
        const raw = { x: px(q.x), y: py(q.y) };
        const spot = dedupe(raw.x, raw.y);
        const x = spot.x, y = spot.y;
        const isRouteStop = m.seq !== undefined && m.seq !== null;
        const color = isRouteStop ? '#c8843a' : (m.kind === 'hotel' ? '#9d4f38' : '#0d5c52');
        const label = isRouteStop ? String(m.seq) : String(idx + 1);
        const showLabel = this.markers.length <= 10;
        const name = (m.name || '').slice(0, 9);
        const labelY = y - (idx % 2 === 0 ? 16 : -24);
        return `<g data-key="${encodeURIComponent(m.key || m.name)}" style="cursor:pointer">
          <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="14" fill="${color}" opacity="0.16"/>
          <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="9" fill="${color}" stroke="#fff" stroke-width="2"/>
          <text x="${x.toFixed(1)}" y="${(y + 3.4).toFixed(1)}" text-anchor="middle" font-size="9.5" font-weight="700" fill="#fff">${label}</text>
          ${showLabel ? `<text x="${x.toFixed(1)}" y="${labelY.toFixed(1)}" text-anchor="middle" class="marker-label">${escapeXml(name)}</text>` : ''}
        </g>`;
      }).join('');

      let locateSvg = '';
      if (this.locatePoint) {
        const q = this._project(this.locatePoint.lat, this.locatePoint.lng);
        const x = px(q.x), y = py(q.y);
        locateSvg = `<g><circle cx="${x}" cy="${y}" r="16" fill="#2f7fe0" opacity="0.18"/>
          <circle cx="${x}" cy="${y}" r="6" fill="#2f7fe0" stroke="#fff" stroke-width="2"/></g>`;
      }

      this.el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" width="100%" height="100%" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="land" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#eef5f1"/><stop offset="55%" stop-color="#e7f0ec"/><stop offset="100%" stop-color="#f3eee2"/>
          </linearGradient>
        </defs>
        <rect width="${w}" height="${h}" fill="url(#land)"/>
        ${grid.join('')}
        <path d="M0 ${(h * 0.72).toFixed(0)} C ${(w * 0.3).toFixed(0)} ${(h * 0.62).toFixed(0)}, ${(w * 0.6).toFixed(0)} ${(h * 0.9).toFixed(0)}, ${w} ${(h * 0.7).toFixed(0)}"
              fill="none" stroke="#bcd8e6" stroke-width="16" opacity="0.5" stroke-linecap="round"/>
        <g transform="translate(${zx.toFixed(1)},${zy.toFixed(1)}) scale(${this.zoom.toFixed(3)}) translate(${(-zx).toFixed(1)},${(-zy).toFixed(1)})">
          ${routeSvg.join('')}
          ${markerSvg}
          ${locateSvg}
        </g>
      </svg>`;
    }
  }

  function escapeXml(text) {
    return String(text).replace(/[<>&"']/g, (ch) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' }[ch]));
  }

  /* ------------------------------ Baidu Maps ------------------------------ */
  class BaiduMap {
    constructor(container, options) {
      this.el = container;
      this.options = options || {};
      this.markers = [];
      this.overlays = [];
      this.routeOverlays = [];
      this.map = null;
      this.ready = false;
    }

    static loadSdk(ak) {
      if (window.BMapGL) return Promise.resolve(window.BMapGL);
      return new Promise((resolve, reject) => {
        const cbName = '__travelOneBmapReady';
        window[cbName] = () => resolve(window.BMapGL);
        const script = document.createElement('script');
        script.src = `https://api.map.baidu.com/api?type=webgl&v=3.0&ak=${encodeURIComponent(ak)}&callback=${cbName}`;
        script.onerror = () => reject(new Error('Baidu Maps JS API failed to load'));
        document.head.appendChild(script);
        setTimeout(() => { if (!window.BMapGL) reject(new Error('Baidu Maps JS API timed out')); }, 9000);
      });
    }

    async init(ak) {
      await BaiduMap.loadSdk(ak);
      const BMapGL = window.BMapGL;
      this.map = new BMapGL.Map(this.el, { enableBizAuthLogo: false });
      const center = this.options.center || { lat: 39.915, lng: 116.404 };
      const bd = gcj02ToBd09(center.lat, center.lng);
      this.map.centerAndZoom(new BMapGL.Point(bd.lng, bd.lat), this.options.zoom || 12);
      this.map.enableScrollWheelZoom(true);
      this.map.addEventListener('click', (ev) => {
        if (!this.options.onMapClick) return;
        const gcj = bd09ToGcj02(ev.latlng.lat, ev.latlng.lng);
        this.options.onMapClick(gcj);
      });
      this.ready = true;
      this.setMarkers(this.markers);
    }

    setMarkers(markers) {
      this.markers = markers || [];
      if (!this.ready) return;
      const BMapGL = window.BMapGL;
      this.overlays.forEach((ov) => this.map.removeOverlay(ov));
      this.overlays = [];
      this.markers.forEach((m) => {
        if (!isFinite(m.lat) || !isFinite(m.lng)) return;
        const bd = gcj02ToBd09(m.lat, m.lng);
        const point = new BMapGL.Point(bd.lng, bd.lat);
        const isStop = m.seq !== undefined && m.seq !== null;
        const cls = isStop ? ' route' : (m.kind === 'hotel' ? ' hotel' : '');
        const label = new BMapGL.Label(
          `<div class="bd-marker-pin${cls}"><span>${isStop ? m.seq : (m.kind === 'hotel' ? 'H' : 'A')}</span></div>`,
          { position: point, offset: new BMapGL.Size(-13, -13) }
        );
        label.setTitle(m.name || '');
        label.addEventListener('click', () => {
          if (this.options.onMarkerClick) this.options.onMarkerClick(m.key || m.name);
        });
        this.map.addOverlay(label);
        this.overlays.push(label);
      });
    }

    setRoute(route) {
      if (!this.ready) { this._pendingRoute = route; return; }
      const BMapGL = window.BMapGL;
      this.routeOverlays.forEach((ov) => this.map.removeOverlay(ov));
      this.routeOverlays = [];
      if (!route || !route.days) return;
      route.days.forEach((day, di) => {
        const color = DAY_COLORS[di % DAY_COLORS.length];
        (day.legs || []).forEach((leg) => {
          const points = (leg.polyline || []).map((p) => {
            const lat = Array.isArray(p) ? p[0] : p.lat;
            const lng = Array.isArray(p) ? p[1] : p.lng;
            const bd = gcj02ToBd09(lat, lng);
            return new BMapGL.Point(bd.lng, bd.lat);
          });
          if (points.length < 2) return;
          const line = new BMapGL.Polyline(points, { strokeColor: color, strokeWeight: 5, strokeOpacity: 0.88 });
          this.map.addOverlay(line);
          this.routeOverlays.push(line);
        });
      });
      this.fit();
    }

    setLocate(point) {
      if (!this.ready || !point) return;
      const BMapGL = window.BMapGL;
      const bd = gcj02ToBd09(point.lat, point.lng);
      if (this._locateOverlay) this.map.removeOverlay(this._locateOverlay);
      const label = new BMapGL.Label(
        `<div style="width:16px;height:16px;border-radius:50%;background:#2f7fe0;border:3px solid #fff;box-shadow:0 0 0 6px rgba(47,127,224,.22)"></div>`,
        { position: new BMapGL.Point(bd.lng, bd.lat), offset: new BMapGL.Size(-11, -11) }
      );
      this.map.addOverlay(label);
      this._locateOverlay = label;
    }

    focus(lat, lng) {
      if (!this.ready) return;
      const bd = gcj02ToBd09(lat, lng);
      this.map.centerAndZoom(new window.BMapGL.Point(bd.lng, bd.lat), 15);
    }

    zoomIn() { if (this.ready) this.map.zoomIn(); }
    zoomOut() { if (this.ready) this.map.zoomOut(); }

    fit() {
      if (!this.ready) return;
      const pts = [];
      this.markers.forEach((m) => {
        if (!isFinite(m.lat)) return;
        const bd = gcj02ToBd09(m.lat, m.lng);
        pts.push(new window.BMapGL.Point(bd.lng, bd.lat));
      });
      if (this.route && this.route.days) {
        this.route.days.forEach((day) => (day.legs || []).forEach((leg) => {
          (leg.polyline || []).forEach((p) => {
            const lat = Array.isArray(p) ? p[0] : p.lat;
            const lng = Array.isArray(p) ? p[1] : p.lng;
            const bd = gcj02ToBd09(lat, lng);
            pts.push(new window.BMapGL.Point(bd.lng, bd.lat));
          });
        }));
      }
      if (pts.length === 1) {
        this.map.centerAndZoom(pts[0], 15);
      } else if (pts.length > 1) {
        this.map.setViewport(pts);
      }
    }

    locate(callback) {
      if (!this.ready) return callback && callback(null);
      const geo = new window.BMapGL.Geolocation();
      geo.getCurrentPosition((res) => {
        if (this.map && geo.getStatus && geo.getStatus() === BMAP_STATUS_SUCCESS) {
          const gcj = bd09ToGcj02(res.point.lat, res.point.lng);
          if (callback) callback(gcj);
        } else if (callback) {
          callback(null);
        }
      });
    }
  }

  /* ------------------------------ Client-side routing ------------------------------ */
  // 浏览器端路线：直接使用百度 WebGL SDK 的路线服务（依赖 JS AK），
  // 这样即使服务端未配置 Web 服务 AK，也能拿到真实里程与耗时。
  const ROUTE_CLASS = { driving: 'DrivingRoute', walking: 'WalkingRoute', riding: 'RidingRoute', transit: 'TransitRoute' };

  let routeHost = null;
  function hiddenRouteMap() {
    if (routeHost && routeHost.map) return routeHost.map;
    const host = document.createElement('div');
    host.style.cssText = 'position:absolute;width:1px;height:1px;left:-9999px;top:-9999px;overflow:hidden';
    document.body.appendChild(host);
    const map = new window.BMapGL.Map(host);
    routeHost = { host, map };
    return map;
  }

  // 百度 WebGL SDK 的路线服务需要一个地图实例 + onSearchComplete 回调；
  // 这里用一个离屏 1px 地图承载，结果只取里程与耗时。
  function routeLeg(from, to, mode) {
    return new Promise((resolve) => {
      if (!window.BMapGL || !from || !to || from.lat == null || to.lat == null) return resolve(null);
      const name = ROUTE_CLASS[mode] || 'DrivingRoute';
      const Ctor = window.BMapGL[name];
      if (!Ctor) return resolve(null);
      let settled = false;
      const done = (value) => { if (!settled) { settled = true; resolve(value); } };
      try {
        const a = gcj02ToBd09(from.lat, from.lng);
        const b = gcj02ToBd09(to.lat, to.lng);
        const route = new Ctor(hiddenRouteMap(), {
          onSearchComplete: (res) => {
            try {
              const plan = res && res.getPlan && res.getPlan(0);
              if (!plan) return done(null);
              const km = Number(String(plan.getDistance(true)).replace(/[^\d.]/g, ''));
              const minutes = Number(String(plan.getDuration(true)).replace(/[^\d.]/g, ''));
              if (!isFinite(km) || !km) return done(null);
              done({ distance_km: Number(km.toFixed(2)),
                     duration_min: Math.max(1, Math.round(minutes || km * 3)),
                     source: 'baidu-js' });
            } catch (e) { done(null); }
          },
        });
        route.search(new window.BMapGL.Point(a.lng, a.lat), new window.BMapGL.Point(b.lng, b.lat));
        setTimeout(() => done(null), 7000);
      } catch (e) { done(null); }
    });
  }

  /* ------------------------------ Public entry point ------------------------------ */

  /* ------------------------------ MapLibre + OSM（国际版） ------------------------------ */
  class MapLibreAdapter {
    constructor(container, options) {
      this.el = container;
      this.options = options || {};
      this.map = null;
      this.markers = [];
    }
    init() {
      if (!window.maplibregl) throw new Error('MapLibre GL JS not loaded');
      this.el.innerHTML = '';
      this.map = new window.maplibregl.Map({
        container: this.el,
        style: {
          version: 8,
          sources: {
            osm: {
              type: 'raster',
              // 多端点冗余：主用 OSM 德国镜像，另有官方域名与 Esri 街道图兜底
              tiles: [
                'https://tile.openstreetmap.de/{z}/{x}/{y}.png',
                'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
              ],
              tileSize: 256,
              maxzoom: 19,
              attribution: '© OpenStreetMap contributors · Tiles: OSM.de / Esri',
            },
          },
          layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
        },
        center: [this.options.lng || 2.3522, this.options.lat || 48.8566],
        zoom: this.options.zoom || 11,
        attributionControl: true,
      });
      // 页面自带 ＋/－/⤢ 三个按钮，不再叠加 MapLibre 自带缩放控件，避免两套按钮重叠
      // 面板开合会改变容器尺寸，必须让 MapLibre 重新计算视口，否则瓦片画不出来
if (typeof ResizeObserver !== 'undefined') {
        this._ro = new ResizeObserver(() => { try { this.map.resize(); } catch (e) {} });
        this._ro.observe(this.el);
      }
      // 瓦片不可达（断网或域名被拦）时，保留标记与路线并明确提示，不谎称底图正常
      this._tileErrors = 0;
      this.map.on('error', () => {
        this._tileErrors += 1;
        if (this._tileErrors === 3) {
          const note = document.getElementById('mapNote');
          if (note) note.textContent = '国际版地图：底图瓦片不可达，已降级为标记与路线视图';
        }
      });
      return this;
    }
    setMarkers(list) {
      this.markers.forEach((m) => m.remove());
      this.markers = [];
      (list || []).forEach((item) => {
        const el = document.createElement('div');
        el.className = 'ml-marker';
        el.textContent = item.seq ? String(item.seq) : '●';
        el.title = item.name || '';
        const marker = new window.maplibregl.Marker({ element: el })
          .setLngLat([Number(item.lng), Number(item.lat)])
          .addTo(this.map);
        this.markers.push(marker);
      });
      return this;
    }
    setRoute(data) {
      const sourceId = 'travelone-route';
      if (this.map.getLayer(sourceId)) this.map.removeLayer(sourceId);
      if (this.map.getSource(sourceId)) this.map.removeSource(sourceId);
      const days = (data && data.days) || [];
      if (!days.length) return this;
      const features = [];
      days.forEach((day) => {
        const coords = (day.stops || []).map((s) => [Number(s.lng), Number(s.lat)]);
        if (coords.length) features.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: coords } });
      });
      if (!features.length) return this;
      this.map.addSource(sourceId, { type: 'geojson', data: { type: 'FeatureCollection', features } });
      this.map.addLayer({ id: sourceId, type: 'line', source: sourceId,
        paint: { 'line-color': '#0d5c52', 'line-width': 4, 'line-opacity': 0.9 } });
      return this;
    }
    fit() {
      if (!this.markers.length) return this;
      const bounds = new window.maplibregl.LngLatBounds();
      this.markers.forEach((m) => bounds.extend(m.getLngLat()));
      this.map.fitBounds(bounds, { padding: 48, maxZoom: 13 });
      return this;
    }
    focus(lat, lng, zoom) { this.map.easeTo({ center: [Number(lng), Number(lat)], zoom: zoom || 13 }); return this; }
    locate() { return Promise.resolve(null); }
    setLocate(lat, lng) {
      if (this._locateMarker) this._locateMarker.remove();
      const el = document.createElement('div');
      el.className = 'ml-marker ml-marker-me';
      el.textContent = '◎';
      this._locateMarker = new window.maplibregl.Marker({ element: el })
        .setLngLat([Number(lng), Number(lat)]).addTo(this.map);
      return this;
    }
    zoomIn() { this.map.zoomIn(); }
    zoomOut() { this.map.zoomOut(); }
    resize() { try { this.map.resize(); } catch (e) {} return this; }
  }

  window.TravelMap = {
    DAY_COLORS,
    gcj02ToBd09,
    bd09ToGcj02,
    wgs84ToGcj02,
    routeLeg,
    ensureSdk(ak) {
      if (window.BMapGL) return Promise.resolve(true);
      if (!ak) return Promise.resolve(false);
      return BaiduMap.loadSdk(ak).then(() => true).catch(() => false);
    },
    async create(container, options) {
      const opts = options || {};
      if (opts.mode === 'global') {
        try {
          return { map: new MapLibreAdapter(container, opts).init(), mode: 'maplibre' };
        } catch (err) {
          container.innerHTML = '';
          return { map: new OfflineMap(container, opts), mode: 'offline', error: err.message };
        }
      }
      if (opts.ak) {
        const map = new BaiduMap(container, opts);
        try {
          await map.init(opts.ak);
          return { map, mode: 'baidu' };
        } catch (err) {
          container.innerHTML = '';
          const offline = new OfflineMap(container, opts);
          return { map: offline, mode: 'offline', error: err.message };
        }
      }
      return { map: new OfflineMap(container, opts), mode: 'offline' };
    },
  };
})();