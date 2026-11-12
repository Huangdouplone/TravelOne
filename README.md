# 旅图 TravelOne

**中文** | [English](#english)

## 仓库简介 / Repository Description

> **GitHub About（中文）**
> 旅图 TravelOne：零数据库、双模式的旅行规划器，实时聚合景点、酒店、票价与城际交通，生成逐日路线；支持中英双语、明暗主题与离线演示页。

> **GitHub About (English)**
> TravelOne: a database-free, dual-mode travel planner that aggregates attractions, hotels, prices and intercity transport, then builds day-by-day routes. Bilingual UI, light/dark themes and a self-contained demo page.

**Suggested topics**: `travel-planner` `python` `vanilla-js` `maplibre` `openstreetmap` `wikidata` `baidu-map` `no-database` `travel` `offline-demo`

---

## 中文文档

### 项目定位

一个把**景点、酒店、地铁、门票/房价、城际交通与路线**放进同一页面的旅行规划器。后端只用 Python 标准库即可运行，不使用数据库；前端是单文件页面，支持中英文与明暗主题。

> 开源学习与参赛演示用途。页面只做信息聚合与估算，**不提供任何预订、购买或下单入口**。

### 功能

- **国内 / 国际双模式**：国内走百度地图网页检索；国际走 Wikidata + 本地 MapLibre/OSM 底图。
- **实时抓取 + 本地快照**：查询城市时现场抓取，失败或断网时回放上一次 JSON 快照并标注时间。
- **景点与周边酒店**：评分、票价/房价、来源、抓取时间、实景图、距景点/地铁距离。
- **多平台比价**：多渠道报价并列展示，最低价与价差实时计算；缺价如实显示“暂无”。
- **国际景点搜索**：支持中文简体/繁体、英文与常用别名，例如 `埃菲尔铁塔 / 埃菲爾鐵塔 / Eiffel / 铁塔`。
- **城际交通**：飞机按航距分段、区域铁路按里程估价、自驾按当地油价与固定汇率估算，全部标注“估算”。
- **行程规划**：勾选地点与住宿，按天数生成逐日顺序、距离与时间轴。
- **界面能力**：中英文切换、深色模式、大字版、设置抽屉、搜索弹层、响应式布局。
- **离线演示页**：`TravelOne/TravelOne.html` 内嵌国内/国际快照与实景图，`file://` 可打开且不发外部请求。

### 双模式对照

| 项目 | 国内版（cn） | 国际版（global） |
| --- | --- | --- |
| 地点数据 | 百度地图网页检索（免密钥） | Wikidata（QLever，CC0） |
| 门票/房价 | 百度聚合报价 + 去哪儿门票 | 通常为空，显示“暂无” |
| 覆盖 | 按行政区持续轮扫，300+ 城市 | 内置 50+ 城市，支持任意城市名动态解析 |
| 地图 | 百度地图（可选 AK）或离线示意图 | MapLibre GL JS + OpenStreetMap 瓦片（本地内置） |
| 交通 | 12306 时刻表 + 油价 + 公开运价 | 航距分段 / 区域铁路 / 自驾估价 |
| 搜索 | 中英模糊匹配、跨城市排序 | 中文译名、繁体、英文与地标别名 |

切换模式时会弹出差异声明；国际快照以 `intl::<City>` 作用域保存，避免与国内同名城市冲突。

### 快速开始

要求 Python 3.9+；不装第三方包也能启动。工程本体位于 `TravelOne/`。

```bash
cd TravelOne

# Windows
start.bat

# macOS / Linux
bash start.sh

# 任意系统
python app.py
```

打开 <http://127.0.0.1:8848>。端口被占用时会自动顺延到 8849–8855，实际端口见控制台或 `TravelOne/logs/startup.log`。

> 不要直接双击 `static/app.html`：`file://` 下浏览器会拦截 `/api` 请求。需要单文件演示时用 `TravelOne/TravelOne.html`。

### 配置（可选）

复制 `TravelOne/.env.example` 为 `TravelOne/.env`，全部留空也能运行。

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `TRAVEL_HOST` / `TRAVEL_PORT` | `127.0.0.1` / `8848` | 监听地址与端口 |
| `COLLECT_INTERVAL_SECONDS` | `300` | 页面展示的刷新周期 |
| `COLLECT_ON_STARTUP` | `1` | 启动时是否先抓种子城市 |
| `COLLECT_CITIES` | 北京,上海,杭州,成都,西安,广州,重庆 | 国内种子城市 |
| `LIVE_CRAWL` | `1` | 设为 `0` 时只用上一次快照 |
| `HTTP_TIMEOUT` | `8` | 上游请求超时（秒） |
| `BAIDU_MAP_JS_AK` | 空 | 浏览器端 AK：真实底图与定位 |
| `BAIDU_MAP_SERVER_AK` | 空 | 服务端 AK：真实路线与地理编码 |

国际版不需要地图 Key。百度 AK 申请步骤与常见报错已内置在页面「地图配置」中。

### 数据来源

| 来源 | 用途 | 许可/状态 |
| --- | --- | --- |
| 百度地图网页检索 | 国内景点、酒店、地铁、评分、图片、聚合房价 | 免密钥；无 SLA，可能限流 |
| 去哪儿门票频道 | 景点门票第二价格源 | 公开 JSON；缺价如实标注 |
| 12306 公开时刻表 | 车次与起讫站 | 票价按公开运价估算 |
| icauto.com.cn | 省级成品油挂牌价 | 公开价格表 |
| Wikidata / QLever | 国际城市、景点、酒店、地铁、地标白名单 | CC0 |
| OpenStreetMap 瓦片 | 国际版底图 | © OpenStreetMap contributors，ODbL |

**高德 / 同程价格**：高德客户端里的同程票价与房价来自商业合作，开放平台 POI 接口只有评分与人均消费，
没有票价/房价字段，且协议禁止抓取或缓存客户端数据。合规路径是向同程联盟/分销平台申请授权 API。
页面“高德 / 同程票价”卡片按“合作授权专用”展示，不伪造价格。详见 `TravelOne/docs/平台数据源.md`。

### 目录结构

```text
.
├── README.md                  # 双语说明（本文件）
├── LICENSE                    # MIT 许可证
├── .gitignore
└── TravelOne/                 # 工程本体
    ├── app.py                 # HTTP 服务入口
    ├── web_api.py             # /api 路由与双模式分流
    ├── start.bat / start.sh   # 启动脚本
    ├── core/                  # 配置、快照、i18n、几何、加密、行程
    ├── collectors/            # 百度、去哪儿、12306、油价、Wikidata
    ├── services/              # 抓取、预热、国际数据、交通、路线
    ├── static/                # 页面、样式、脚本、MapLibre
    ├── tools/                 # 构建、图片素材、发布自检
    ├── data/images/           # 离线页图片素材
    ├── docs/                  # 数据源与双模式设计记录
    ├── logs/                  # 启动/预热日志与图片映射
    └── TravelOne.html         # 内嵌数据的演示页（构建产物）
```

### 构建与验证

```bash
cd TravelOne

python -m compileall -q app.py web_api.py collectors core services tools
for f in static/js/*.js; do node --check "$f"; done

python tools/build_single_page.py       # 重建 static/app.html
python tools/build_offline_app.py TravelOne.html
python tools/check_release.py           # 版权头 / README / LICENSE / 20MB 限制
```

- 离线页把快照 JSON 先 gzip 再 base64 内嵌，浏览器用 `DecompressionStream('gzip')` 解压后启动。
- 图片以 WebP data URI 内嵌；城市实景组图按条目轮转，地标使用条目级图片。
- 页面超过 20MB 时构建脚本直接失败，不会产出超限文件。

### 常用接口

| 接口 | 说明 |
| --- | --- |
| `GET /api/health` | 运行状态、存储类型与快照统计 |
| `GET /api/meta?mode=cn / global` | 城市、数量、标签、刷新信息 |
| `GET /api/attractions?mode=&city=&keyword=&page=` | 景点列表 |
| `GET /api/attractions/<key>?mode=` | 景点详情、周边酒店、最近地铁 |
| `GET /api/hotels?mode=&city=&near=&page=` | 酒店列表 |
| `GET /api/hotels/<id>?mode=` | 酒店详情与房型 |
| `GET /api/search?mode=&q=&kind=&page=` | 全局搜索（含国际别名匹配） |
| `GET /api/transport?mode=&from=&to=&date=` | 城际交通比对 |
| `GET /api/fuel?province=` | 省级油价 |
| `GET /api/sources?mode=` | 数据源状态、许可与说明 |
| `GET /api/coverage` / `/api/warmup?mode=global` | 国内覆盖进度 / 国际轮扫进度 |
| `POST /api/trips`、`/api/trips/<id>/plan` | 行程与路线 |

### 合规与边界

- 上游网页接口没有 SLA，可能限流、改版或临时不可达；不可达时只回放快照，不生成假数据。
- 门票、房价、机票、铁路与自驾费用都是**参考估算或聚合报价**，不构成购买承诺。
- 国际源通常没有价格、评分与实景图，页面显示“暂无”。
- 离线页图片来自公开图片搜索，仅用于演示；商用前请自行确认授权并替换。
- 不抓取高德客户端、同程 H5 等受保护数据；需要真实 OTA 价格请走官方合作/授权 API。

### 许可证

代码以 **MIT License** 开源，版权人 **黄豆666/huangdouplone**，详见根目录 [LICENSE](LICENSE)。

第三方数据与内容不适用 MIT：OpenStreetMap 瓦片遵循 ODbL 并保留署名；Wikidata 为 CC0；
百度地图、去哪儿、icauto、公开图片等归各自权利人所有，使用时请遵守其条款。

---

## English

### What it is

A single-page travel planner that puts **attractions, hotels, metro, ticket/room prices, intercity transport and routes** in one place. The backend runs on the Python standard library with no database; the frontend is a self-contained page with bilingual UI and light/dark themes.

> Built for learning and competition demos. It aggregates and estimates information only — **there is no booking, checkout or purchase channel**.

### Features

- **China / Global modes**: Baidu Maps web search for China, Wikidata + local MapLibre/OSM for the rest of the world.
- **Live crawl + local snapshots**: fetch on demand, fall back to the last JSON snapshot (with timestamp) when upstream fails.
- **Attractions and nearby hotels**: rating, ticket/room price, source, fetch time, photos, distance to attraction and metro.
- **Price comparison**: channel quotes side by side, lowest price and spread computed; missing prices are shown as "n/a".
- **International search**: Simplified/Traditional Chinese, English and common aliases, e.g. `埃菲尔铁塔 / 埃菲爾鐵塔 / Eiffel / 铁塔`.
- **Intercity transport**: distance-banded flights, regional rail estimates, self-drive fuel at local pump prices × fixed FX — all labelled as estimates.
- **Trip planning**: pick places and stays, then generate day-by-day order, distance and timeline.
- **UI**: Chinese/English toggle, dark mode, larger text, settings drawer, search overlay, responsive layout.
- **Offline demo**: `TravelOne/TravelOne.html` embeds both snapshots and photos; it opens via `file://` without external requests.

### Two modes

| Item | China (cn) | Global (global) |
| --- | --- | --- |
| Places | Baidu Maps web search (no key) | Wikidata via QLever (CC0) |
| Prices | Baidu aggregated rates + Qunar tickets | Usually empty, shown as "n/a" |
| Coverage | Continuous administrative sweep, 300+ cities | 50+ built-in cities, any city name resolved on demand |
| Map | Baidu Maps (optional AK) or offline schematic | MapLibre GL JS + OpenStreetMap tiles (local vendor) |
| Transport | 12306 timetable + fuel + published tariff | Distance bands / regional rail / self-drive estimates |
| Search | CJK/English fuzzy match, cross-city ranking | Chinese translations, Traditional Chinese, English, landmark aliases |

Switching modes shows a difference notice. International snapshots use the `intl::<City>` scope to avoid clashing with Chinese cities of the same name.

### Quick start

Python 3.9+ is enough; no third-party package is required. The project body lives in `TravelOne/`.

```bash
cd TravelOne

# Windows
start.bat

# macOS / Linux
bash start.sh

# Any platform
python app.py
```

Open <http://127.0.0.1:8848>. If the port is busy it moves to 8849–8855; check the console or `TravelOne/logs/startup.log`.

> Do not open `static/app.html` directly: browsers block `/api` calls under `file://`. Use `TravelOne/TravelOne.html` for a single-file demo.

### Configuration (optional)

Copy `TravelOne/.env.example` to `TravelOne/.env`; everything can stay empty.

| Variable | Default | Purpose |
| --- | --- | --- |
| `TRAVEL_HOST` / `TRAVEL_PORT` | `127.0.0.1` / `8848` | Listen address and port |
| `COLLECT_INTERVAL_SECONDS` | `300` | Refresh cycle shown in the UI |
| `COLLECT_ON_STARTUP` | `1` | Warm seed cities on boot |
| `COLLECT_CITIES` | Beijing,Shanghai,Hangzhou,Chengdu,Xi'an,Guangzhou,Chongqing | China seed cities |
| `LIVE_CRAWL` | `1` | Set `0` to use the last snapshot only |
| `HTTP_TIMEOUT` | `8` | Upstream timeout (seconds) |
| `BAIDU_MAP_JS_AK` | empty | Browser AK for real basemap and geolocation |
| `BAIDU_MAP_SERVER_AK` | empty | Server AK for live routing and geocoding |

Global mode needs no map key. AK application steps and common errors are built into the in-page "Map setup" guide.

### Data sources

| Source | Used for | License / status |
| --- | --- | --- |
| Baidu Maps web search | China POIs, hotels, metro, ratings, photos, aggregated rates | No key; no SLA, may rate-limit |
| Qunar ticket channel | Secondary ticket price source | Public JSON; missing prices are labelled |
| 12306 public timetables | Train numbers and termini | Fares estimated from published tariff |
| icauto.com.cn | Provincial pump prices | Public price table |
| Wikidata / QLever | Global cities, POIs, hotels, metro, landmark whitelist | CC0 |
| OpenStreetMap tiles | Global basemap | © OpenStreetMap contributors, ODbL |

**Amap / Tongcheng prices**: the ticket and room prices shown in the Amap app come from commercial partnerships.
Amap's open POI API exposes only rating and average spend — no ticket or room rate — and its terms forbid scraping
or caching client data. Compliant access requires a Tongcheng distribution/API agreement.
The in-page "Amap / Tongcheng" card is labelled "partnership only" and never invents prices. See `TravelOne/docs/平台数据源.md`.

### Layout

```text
.
├── README.md                  # this bilingual document
├── LICENSE                    # MIT
├── .gitignore
└── TravelOne/                 # project body
    ├── app.py                 # HTTP server entry
    ├── web_api.py             # /api routes and mode switch
    ├── start.bat / start.sh   # launchers
    ├── core/                  # config, snapshots, i18n, geo, crypto, trips
    ├── collectors/            # Baidu, Qunar, 12306, fuel, Wikidata
    ├── services/              # crawl, warm-up, global data, transport, routing
    ├── static/                # pages, CSS, JS, MapLibre
    ├── tools/                 # builds, image assets, release checks
    ├── data/images/           # offline page image assets
    ├── docs/                  # data source and dual-mode notes
    ├── logs/                  # startup/warm-up logs and image maps
    └── TravelOne.html         # embedded-data demo page (build output)
```

### Build and checks

```bash
cd TravelOne

python -m compileall -q app.py web_api.py collectors core services tools
for f in static/js/*.js; do node --check "$f"; done

python tools/build_single_page.py       # rebuild static/app.html
python tools/build_offline_app.py TravelOne.html
python tools/check_release.py           # copyright headers / README / LICENSE / 20MB cap
```

- The offline page gzips the snapshot JSON, base64-embeds it, and inflates it with `DecompressionStream('gzip')`.
- Photos are embedded as WebP data URIs; city scene pools rotate per item and landmarks use item-level images.
- The build fails if the page exceeds 20MB, so an oversized artifact is never produced.

### API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Runtime status, storage type and snapshot stats |
| `GET /api/meta?mode=cn / global` | Cities, counts, tags, refresh info |
| `GET /api/attractions?mode=&city=&keyword=&page=` | Attraction list |
| `GET /api/attractions/<key>?mode=` | Detail, nearby hotels, nearest metro |
| `GET /api/hotels?mode=&city=&near=&page=` | Hotel list |
| `GET /api/hotels/<id>?mode=` | Hotel detail and room types |
| `GET /api/search?mode=&q=&kind=&page=` | Global search including international aliases |
| `GET /api/transport?mode=&from=&to=&date=` | Intercity transport comparison |
| `GET /api/fuel?province=` | Provincial pump prices |
| `GET /api/sources?mode=` | Data source status, licences and notes |
| `GET /api/coverage` / `/api/warmup?mode=global` | China coverage / global warm-up progress |
| `POST /api/trips`、`/api/trips/<id>/plan` | Trips and route plans |

### Compliance and limits

- Upstream web endpoints have no SLA; they may rate-limit, change or fail. On failure the app replays snapshots instead of inventing data.
- Ticket, room, flight, rail and self-drive costs are **estimates or aggregated quotes**, not purchase commitments.
- Global sources usually carry no price, rating or photos; the UI shows "n/a".
- Offline demo photos come from public image search and are for demonstration only; verify licences before commercial use.
- The project does not scrape the Amap client or Tongcheng H5 pages; obtain authorised OTA APIs for real prices.

### License

Code is released under the **MIT License**, copyright **黄豆666/huangdouplone**. See [LICENSE](LICENSE).

Third-party data and content are not covered by MIT: OpenStreetMap tiles require ODbL attribution; Wikidata is CC0;
Baidu Maps, Qunar, icauto and public images remain with their respective owners.

---

Copyright (c) 2026 黄豆666/huangdouplone