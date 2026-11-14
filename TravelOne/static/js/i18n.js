/* Copyright (c) 2026 黄豆666/huangdouplone
 * SPDX-License-Identifier: MIT */
/* TravelOne i18n: English source strings with a Chinese dictionary.
   The toggle switches all UI chrome; place names and POI names keep their
   upstream spelling (proper nouns). */
(function () {
  const STORAGE_KEY = 'travelone.lang';
  const ZH = {
    "Global sources carry no ticket price, rating or theme tags; these filters do not apply.": "国际版数据源不含门票价、评分与主题标签，这些筛选暂不适用。",
    "Global sources carry no room rate, star level or rating; price and rating filters do not apply.": "国际版数据源不含房晚价、星级与评分，价格与评分筛选暂不适用。",
    "TravelOne · All-in-one travel assistant": "TravelOne · 一站式旅行助手",
    "Explore · Compare · Route": "探索 · 比价 · 路线",
    "Overview": "总览",
    "Attractions": "景点",
    "Hotels": "酒店",
    "Price comparison": "多平台比价",
    "Trip & route": "行程与路线",
    "Data sources": "数据源",
    "City / Nationwide": "城市 / 全国",
    "Search": "搜索",
    "Popular cities": "热门城市",
    "Data overview": "数据概览",
    "· Hotels": "· 酒店",
    "Metro stations": "地铁站",
    "· refresh every": "· 刷新周期",
    "Refresh": "刷新",
    "Larger text": "大字",
    "Locate": "定位",
    "Map": "地图",
    "My trip": "我的行程",
    "A one-stop": "一个一站式",
    "travel planner": "旅行规划器",
    "A one-stop travel planner": "一个一站式旅行规划器",
    "Attractions and hotels on one map:": "把景点与酒店放在同一张地图上：",
    "compare, pick, and plan": "比价、选点、排路线",
    "TravelOne is one page for the whole trip: it crawls public map results at runtime for attractions, hotels and metro, compares ticket and room rates with their sources, and now also lines up flights, high-speed rail and self-drive cost against live pump prices. Every number carries a fetch timestamp and is marked as an estimate when no live feed exists. Pick places and stays, then get a day-by-day order, distance and schedule. No booking channel, no database.":
      "旅图用一张网页搞定整趟行程：运行时抓取景点、酒店与地铁，按来源比对门票与房价，并把飞机、高铁与自驾（按实时油价）的时间与费用放在一起比较；每个数字都带抓取时间，没有实时源时明确标为估算。选中景点与住宿后自动生成按天顺序、里程与时间安排。不提供购票渠道，不使用数据库。",
    "TravelOne crawls public map search results at runtime for attractions and hotels: tickets, room rates, ratings, photos, opening hours, coordinates and metro distance all carry a fetch timestamp. Each place shows online price, list price and channel quotes side by side, and clearly says Price pending when none is available. Pick places and hotels to get an automatic day-by-day order, distance and schedule.":
      "旅图在运行时从公开地图检索实时抓取景点与酒店：门票、房价、评分、实景图、营业时间、坐标与地铁距离都带抓取时间；同一地点同时给出在线参考价、门市原价与渠道报价，抓不到价格时明确显示「票价待查」。选中景点与住宿后，可按天自动生成通行顺序、里程与时间安排。",
    "Attractions and hotels on one map: compare, pick, and plan": "把景点与酒店放在同一张地图上：比价、选点、排路线",
    "Attractions": "景点",
    "Hotels nearby": "周边酒店",
    "Areas covered": "覆盖区域",
    "Refresh cycle": "采集间隔",
    "Live crawl · zero config": "实时抓取 · 免配置",
    "Prices with sources": "门票房价带来源",
    "No database": "无数据库",
    "Metro distance": "距地铁距离",
    "Baidu Maps location": "百度地图定位",
    "Day-by-day routes": "按天路线规划",
    "Explore attractions": "景点探索",
    "Loading…": "正在加载…",
    "Recommended": "推荐",
    "Top rated": "评分最高",
    "Lowest price": "价格最低",
    "Nearest": "距离最近",
    "Hide filters": "收起筛选",
    "Show filters": "展开筛选",
    "Filters": "筛选条件",
    "All attractions": "全部景点",
    "City": "城市",
    "Collapse": "折叠",
    "Rating": "评分",
    "Any": "不限",
    "Ticket price": "门票价格",
    "Free": "免费",
    "A-level / type": "景区等级 / 类型",
    "Themes": "主题标签",
    "Clear": "清除",
    "Preferences": "特色偏好",
    "Open at night": "夜景开放",
    "Indoor": "室内场馆",
    "Nature": "自然风光",
    "Free entry": "免费开放",
    "Within 30 km of me": "只看我附近 30 公里",
    "Load more attractions": "加载更多景点",
    "Closest to metro": "距地铁最近",
    "Closest to attraction": "距景点最近",
    "Hotel filters": "酒店筛选",
    "All hotels": "全部酒店",
    "Price range": "价格区间",
    "Under ¥400": "¥400 以下",
    "Star rating": "星级",
    "5-star": "五星",
    "4-star": "四星",
    "3-star and below": "三星及以下",
    "To metro": "距地铁站",
    "Within 200 m": "200 米内",
    "Within 500 m": "500 米内",
    "Within 1 km": "1 公里内",
    "To attraction": "距景点",
    "Within 3 km": "3 公里内",
    "Within 5 km": "5 公里内",
    "Reference attraction (first in city by default)": "选择参照景点（默认当前城市首个）",
    "Load more hotels": "加载更多酒店",
    "Select attractions and hotels to compare online, list and channel prices": "选择景点与酒店，对比在线价 / 门市原价 / 渠道报价",
    "Clear selection": "清空选择",
    "Compare": "生成对比",
    "Pick attractions (up to 6)": "选择景点（最多 6 个）",
    "Pick hotels (up to 8)": "选择酒店（最多 8 家）",
    "Trip & route planning": "行程与路线规划",
    "Add places or hotels, then plan in one click": "添加景点或酒店后即可一键规划",
"Export JSON": "导出 JSON",
    "Import JSON": "导入 JSON",
    "Add a day": "增加一天",
    "Plan route": "生成路线规划",
    "Planning options": "规划参数",
    "Travel mode": "交通方式",
    "Drive": "驾车",
    "Walk": "步行",
    "Cycle": "骑行",
    "Transit": "公交",
    "Daily start time": "每天出发时间",
    "Daily time budget (hours)": "每日时长上限（小时）",
    "Origin": "出发地",
    "Trip centre (auto)": "行程中心点（自动）",
    "My location": "我的位置",
    "Order optimisation": "顺序优化",
    "Auto (nearest + 2-opt)": "自动排序（最近邻 + 2-opt）",
    "Keep my order": "保持我的顺序",
    "Checking routing engine…": "路线规划引擎检测中…",
    "Checking engine…": "引擎检测中…",
    "Data sources & crawl status": "数据源 · 抓取状态",
    "Continuous nationwide sweep, no configuration": "全网动态轮扫，无需任何配置",
    "Fetch this city now": "立即抓取当前城市",
    "Clear local snapshots": "清空本地存档",
    "Map API guide: apply for a Baidu Maps AK → paste → verify": "地图 API 教学：百度地图 AK 申请 → 填入 → 验证",
    "Open AK settings": "打开 AK 配置",
    "Crawl log (last 8 runs)": "抓取记录（最近 8 轮）",
    "Started": "开始时间",
    "Trigger": "触发",
    "Status": "状态",
    "Fetched": "抓取",
    "New": "新增",
    "No crawl runs yet": "暂无抓取记录",
    "This project": "本项目",
    "ships no database and no bundled dataset": "不携带数据库与任何预置数据",
    ": attractions, hotels, tickets and rates are crawled from Baidu Maps at runtime.": "：景点、酒店、门票、房价都在运行时从百度地图网页检索抓取，",
    "holds only the last fetch per area as JSON and can be cleared in one click. Ctrip, Tongcheng and Qunar throttle anonymous high-frequency access,":
      "里只有上一次抓取的 JSON 存档，可一键清空。携程/同程/去哪儿对匿名高频访问有风控，",
    "so the page does not crawl them directly. Baidu Maps already aggregates channel rates and the page labels them as Qunar (via Baidu Maps).":
      "页面不直接抓它们；百度地图本身聚合了去哪儿等渠道的报价，页面会如实标注来源。",
    "Map location": "地图定位",
    "Setup guide": "配置指南",
    "Trip stops": "行程站点",
    "Enable the real Baidu basemap and live routes": "启用百度地图真实底图与真实路线",
    "Everything works without an AK: lists, price comparison, the offline schematic map, nearest-first sorting and locally estimated routes. With an AK the map becomes the real basemap, browser geolocation is available, and routes are computed live by Baidu.":
      "不填 AK 也能用：列表、比价、离线示意地图、就近排序与本地路线估算都可用。填入 AK 后地图换成真实底图、可浏览器定位，路线改由百度实时计算。",
    "AKs are stored only on this machine": "AK 只保存在本机",
    "Open": "打开",
    "Baidu LBS Open Platform": "百度地图开放平台",
    "and complete identity verification": "，注册并完成实名认证",
    "Console → App Management → My Apps → Create App. Choose type": "控制台 → 应用管理 → 我的应用 → 创建应用；应用类型选",
    "Browser": "浏览器端",
    "and enable JavaScript API": "，勾选 JavaScript API",
    "Set the Referer whitelist to": "Referer 白名单填",
    "(or add 127.0.0.1 and localhost too). Replace it with your domain in production.": "（或同时加 127.0.0.1、localhost）；上线后改成你的域名",
    "Copy the 24-character AK and paste it into Browser-side AK below": "复制 24 位左右的 AK，粘贴到下方浏览器端 AK",
    "For real driving/transit routes and address lookup, create a second": "要真实驾车/公交路线与地址解析，再建一个",
    "Server": "服务端",
    "app with IP whitelist 127.0.0.1 and paste its AK into Server AK": "应用，IP 白名单填 127.0.0.1，取其 AK 填到服务端 AK",
    "Save, click Test AK, and it takes effect immediately; the map header shows Baidu Maps": "保存后点测试 AK，通过即生效；地图标题显示百度地图",
    "No AK configured; using the offline schematic map": "当前未配置 AK，使用离线示意地图",
    "Browser-side AK (map rendering / geolocation)": "浏览器端 AK（地图渲染 / 定位）",
    "Server AK (routing / geocoding, optional)": "服务端 AK（路线规划 / 地理编码，可选）",
    "Security: the field accepts paste only and blocks copy and right-click. The value is encrypted on this machine before saving; only ciphertext is stored.":
      "安全说明：输入框只接受粘贴、禁止复制与右键；提交前在本机加密，服务端只保存密文。",
    "Save and apply": "保存并生效",
    "Test AK": "测试 AK",
    "Later": "稍后再说",
    "AKs are stored only on this machine in data/runtime_config.json (encrypted) and never uploaded.": "AK 只保存在本机 data/runtime_config.json（密文），不会上传。",
    "Common errors (expand)": "常见报错对照（点开）",
    "Error": "报错", "Cause": "原因", "Fix": "处理",
    "APP service disabled": "APP 服务被禁用",
    "JavaScript API was not enabled when the app was created": "创建应用时没勾选 JavaScript API",
    "Edit the app, enable JavaScript API, save again": "编辑应用勾选后重新保存",
    "AK does not exist / INVALID_USER_SCODE": "AK 不存在 / INVALID_USER_SCODE",
    "The AK was copied incompletely or deleted": "AK 复制不完整或已被删除",
    "Copy it again without spaces": "重新复制，注意不要带空格",
    "Referer whitelist validation failed": "Referer 白名单校验失败",
    "The whitelist does not include the current origin": "白名单不含当前页面来源",
    "Use * or add 127.0.0.1": "填 * 或加入 127.0.0.1",
    "Permission denied": "权限校验失败",
    "A browser AK was used on a server endpoint": "浏览器 AK 用在了服务端接口",
    "Create a separate server AK for server endpoints": "服务端接口另建服务端 AK",
    "Quota exceeded": "配额超限 / quota",
    "The daily free quota is used up": "当日免费额度用完",
    "Resets next day, or raise the quota": "次日恢复或提升配额",
    "Open this app through the local service": "请通过本地服务打开本应用",
    "Detected that the page was opened via": "检测到当前是",
    ". Browsers block all data requests from file:// URLs, so detail views show Failed to fetch.": "直接打开页面，浏览器会拦截所有数据请求，因此详情页显示 Failed to fetch。",
    "Windows: double-click": "Windows：双击项目根目录的",
    "macOS / Linux: run in the project folder": "macOS / Linux：在项目目录执行",
    "or run manually:": "或手动执行：",
    "Then open": "启动后浏览器访问",
    "in your browser to load live attraction and hotel data.": "即可正常加载景点与酒店数据。",
    "Started — reload": "已启动，重新加载",
    "Live crawl": "实时抓取",
    "Last snapshot": "上次抓取存档",
    "No data": "暂无数据",
    "Price pending": "票价待查",
    "Rate pending": "房价待查",
    "Free": "免费",
    "from": "起",
    "Details": "详情",
    "AKs are stored only on this machine.": "AK 只保存在本机。",
    "Timetable": "时刻表",
    "Train numbers and origin/destination are read from the public 12306 timetable files, so each corridor lists its real trains. The ticket API returns an encrypted payload, so fares stay estimates from the published tariff.": "车次号与起讫站来自 12306 公开时刻表文件，可列出走廊上的真实车次；余票接口返回加密载荷，票价仍按公开运价估算。",
    "Trains from the 12306 timetable; fare estimated from the published tariff": "车次来自 12306 公开时刻表，票价按公开运价估算",
    "Timetable trains": "时刻表车次",
    "Comparison ready": "比价结果已生成",
    "Fetch still running; click Refresh later to see results": "抓取仍在进行，稍后点刷新查看结果",
    "Locate failed: permission denied or unsupported": "定位失败：权限被拒绝或浏览器不支持",
    "No attractions for this city yet": "这个城市暂时没有景点数据",
    "No coordinates for this hotel": "这家酒店没有坐标",
    "Already in trip": "已在行程中",
    "Added as stay": "已加入住宿",
    "Added to trip": "已加入行程",
    "A fetch is already running; the page refreshes when it finishes": "已有抓取在跑，完成后页面会自动刷新",
    "Fetch started; refreshing when it finishes…": "已开始抓取，完成后自动刷新…",
    "A fetch is already running; waiting for it…": "已有抓取在跑，正在等待…",
    "Started fetching this city…": "正在抓取这个城市…",
    "Switched to nationwide coverage": "已切换到全国范围",
    "AK field accepts paste only (Ctrl+V / Cmd+V)": "AK 输入框只接受粘贴（Ctrl+V / Cmd+V）",
    "Copy and select-all are disabled in the AK field": "AK 输入框已禁用复制与全选",
    "AK saved. Reload the page to enable the real basemap.": "AK 已保存，刷新页面即可启用真实底图。",
    "Server AK saved. Routes now use live Baidu routing.": "服务端 AK 已保存，路线改用百度实时规划。",
    "Origin selected": "已设为出发点",
    "Intercity transport & cost": "城际交通与费用",
    "Crawl log": "抓取日志",
    "English": "英文",
    "No anonymous feed": "无匿名报价",
    "Channel room rates come back through the built-in Baidu Maps aggregation; each quote keeps its own source label and fetch time.": "渠道房价由内置的百度地图聚合返回，每条报价保留自己的来源与抓取时间。",
    "Public pages expose hotel names, star ratings, guest scores and review counts. Room prices require an authenticated session, so no anonymous price is shown.": "公开页面能看到酒店名称、星级、点评分与点评数；房价需要登录态，因此不展示匿名价格。",
    "Featured lists carry prices, but there is no stable per-hotel anonymous endpoint; the app does not guess or mirror those numbers.": "精选列表带价格，但没有稳定的单店匿名接口；应用不会猜测或镜像这些数字。",
    "The H5 list API (/tapi/*) requires an h5sign signature; anonymous requests are rejected, so no price or rating is claimed.": "H5 列表接口需要 h5sign 签名，匿名请求会被拒绝，因此不声称有价格或评分。",
    "Hotel search returns 403 without an mtgsig-signed session; the app reports the platform as unavailable instead of inventing a quote.": "酒店搜索需要 mtgsig 签名会话，否则返回 403；应用直接标注平台不可用，不编造报价。",
    "holds only the last fetch per area as JSON and can be cleared in one click.": "每个区域只保留最近一次抓取的 JSON，可一键清空。",
    "No crawl runs yet; the first sweep starts when the service starts": "还没有抓取记录，服务启动后会开始第一轮",
    "Search attractions and hotels (Ctrl K)": "搜索景点与酒店（Ctrl K）",
    "Switch to English": "切换到英文",
    "Fetch the latest attractions and hotels now": "立即抓取最新的景点与酒店",
    "Toggle larger text for presenting or easier reading": "切换大字，便于演示或阅读",
    "Live · Baidu Maps (built-in)": "实时 · 百度地图（内置）",
    "View Baidu Maps AK application steps": "查看百度地图 AK 申请步骤",
    "Close map": "关闭地图",
    "Zoom in": "放大",
    "Zoom out": "缩小",
    "Fit all markers": "显示全部标记",
    "OpenMap": "打开地图",
    "Close search": "关闭搜索",
    "MapSetup guide": "地图配置指南",
    "Close": "关闭",
    "Close menu": "关闭菜单",
    "Open menu": "打开菜单",
    "Back to top": "回到顶部",
    "e.g. Beijing": "例如 北京",
    "e.g. Shanghai": "例如 上海",
    "Attraction ticket comparison": "景点门票比价",
    "Hotel rate comparison": "酒店房价比价",
    "Attraction": "景点",
    "Attraction": "景点",
    "Lowest": "最低",
    "Breakfast / cancellation": "早餐 / 取消政策",
    "Nearest metro": "最近地铁",
    "No attractions available": "暂无可选景点",
    "No hotels available": "暂无可选酒店",
    "Comparison ready": "比价结果已生成",
    "Pick attractions or hotels to compare first": "先选择要比较的景点或酒店",
    "Quotes are online and list prices aggregated by Baidu Maps, each with a fetch time. Channels without a price show —; estimates are never presented as live rates.": "报价为百度地图聚合的在线价与门市价，均带抓取时间；没有价格的渠道显示 —，估算值绝不冒充实时价。",
    "Standard": "标准",
    "Larger text": "大字",
    "Larger text on": "已切换到大字",
    "Standard text on": "已切换到标准字号",
    "Any": "不限",
    "5-star": "五星",
    "4-star": "四星",
    "3-star": "三星",
    "2-star": "二星",
    "1-star": "一星",
    "Transport & fuel sources": "交通与油价数据源",
    "Fuel price table": "油价数据表（全国）",
    "Live": "实时",
    "China Railway (12306)": "中国铁路 12306",
    "Encrypted feed": "加密载荷",
    "Flight lists": "航班列表",
    "Signed API": "需签名接口",
    "Booking": "购票与下单",
    "Not provided": "不提供",
    "Provincial 92#/95#/0# pump prices are read from a public price table and cached for six hours; they feed the self-drive cost.": "各省 92#/95#/0# 挂牌价取自公开油价表，缓存六小时，用于自驾油费估算。",
    "The anonymous ticket API now returns an encrypted payload, so fares fall back to the published rail tariff and are labelled as estimates.": "12306 匿名余票接口返回加密载荷，票价改按公开运价规则估算，并明确标注为估算。",
    "Airline and OTA flight lists require a signed client session; TravelOne shows time and price ranges marked as estimates and never presents them as live quotes.": "航司与 OTA 航班列表需要签名会话；旅图给出标注为估算的时间与价格区间，不冒充实时报价。",
    "There is no purchase or ticketing channel in this app: it only synchronises and compares published prices and travel time.": "本应用不提供购票或下单入口，只同步与比对公开价格与耗时。",
    "From city": "出发城市",
    "To city": "到达城市",
    "Depart date": "出发日期",
    "Compare options": "比对方案",
    "Not compared yet": "尚未比对",
    "Comparing…": "正在比对…",
    "Mode": "方式",
    "Price range": "价格区间",
    "Source": "来源",
    "Estimated trip total": "预估行程总价",
    "tickets / stays": "门票住宿",
    "Straight-line": "直线距离",
    "Enter both cities": "请先填写两个城市",
    "92# petrol": "92# 汽油",
    "0# diesel": "0# 柴油",
    "High-speed rail": "高铁",
    "Flight": "飞机",
    "Self-drive": "自驾",
    "Could not compare": "无法比对",
    "Selected": "已选",
    "Fuel price unavailable right now": "暂时取不到油价",
    "Flights and trains are compared from public data only. TravelOne does not sell tickets or take bookings.": "机票与火车票只比对公开数据；旅图不出售票、不接单。",
    "Live train data · estimated fares": "车次实时 · 票价估算",
    "Real trains · estimated fares": "真实车次 · 票价估算",
    "Estimated (no anonymous fare feed)": "估算（无匿名报价源）",
    "Estimated from published rail tariff": "按公开运价规则估算",
    "Estimated from distance; no anonymous fare feed": "按航距估算（无匿名报价源）",
    "Fuel price fetched live; tolls and consumption estimated": "油价实时，油耗与通行费按经验值估算",
    "Attractions nearby": "周边景点",
    "Transit stop": "交通站点",
    "Price from": "报价来源",
    "Search an attraction, hotel or landmark": "搜索景点、酒店或地标",
    "Type at least two characters; results span every tracked city.": "输入至少两个字符，结果覆盖所有已跟踪城市。",
    "Searching…": "正在搜索…",
    "Search failed": "搜索失败",
    "No matches": "没有匹配结果",
    "Try a shorter name, a brand, or a landmark such as \"Disney\" / \"故宫\".": "可以试一个更短的名字、品牌，或「迪士尼」「故宫」这类地标。",
    "Load more": "加载更多",
    "Attractions and hotels across every tracked city": "覆盖所有已跟踪城市的景点与酒店",
    "Add to trip": "加入行程",
    "Add as stay": "加入住宿",
    "Set as origin": "设为出发点",
    "Open in Baidu Maps": "百度地图打开",
    "reviews": "条点评",
    "No rating yet": "暂无评分数据",
    "quotes": "个报价",
    "quote": "个报价",
    "lowest": "最低",
    "No quotes": "暂无报价",
    "About this attraction": "景点介绍",
    "Price range": "价格与波动",
    "Ticket policy": "门票政策",
    "Free entry": "免票",
    "Discount": "优惠",
    "Booking": "预约",
    "Refunds": "退改",
    "Ticket types": "票种与价格",
    "Type": "票种",
    "Notes": "说明",
    "Price": "价格",
    "Location & transport": "位置与交通",
    "No metro data": "暂无地铁数据",
    "Opening hours": "开放时间",
    "see venue notice": "以公告为准",
    "Nearby hotels": "周边酒店",
    "Sorted by distance": "按距离排序",
    "More in this city": "同城推荐",
    "Stay policy": "入住政策",
    "Check-in": "入住",
    "Cancellation": "取消",
    "Children": "儿童",
    "Nearby attractions": "周边景点",
    "Room / date": "房型 / 日期",
    "Room type": "房型",
    "Ticket type": "票种",
    "Channel price": "平台价",
    "Channel": "平台",
    "Options": "规格",
    "Option": "规格",
    "List price": "门市原价",
    "Bookable": "可订",
    "Sold out": "满房",
    "No metro distance": "暂无地铁距离",
    "No nearby metro": "暂无就近地铁数据",
    "🚇 No nearby metro": "🚇 暂无就近地铁数据",
    "Filter this list…": "筛选这个列表…",
    "Load all attractions in this city": "加载本城市全部景点",
    "Show fewer": "收起",
    "More star levels": "更多星级",
    "Fewer levels": "收起星级",
    "Address pending": "地址待补充",
    "No description yet; it appears when the source provides one.": "暂无详细介绍，数据源补充后会自动展示。",
    "No price yet for this item; quotes appear here as soon as a source provides them.": "该条目暂无价格数据；数据源补充报价后会自动出现在这里。",
    "No channel quotes yet. They fill in automatically once a source returns a price.": "暂无平台报价：接入数据源后各渠道价格会自动填充。",
    "No nearby hotels matched yet; they appear here as hotel data arrives.": "该景点暂未匹配到周边酒店；新增酒店数据后会自动出现。",
    "No nearby attractions matched for this hotel yet.": "该酒店暂未匹配到周边景点。",
    "No ticket-type breakdown; see the channel quotes above.": "暂无分票种数据，可参考上方平台报价。",
    "Your trip is empty": "行程还是空的",
    "Use Add to trip on an attraction card, or Add as stay on a hotel card": "在景点卡片点击加入行程，在酒店卡片点击加入住宿",
    "Nothing planned for this day": "这一天还没有安排",
    "Plan result": "规划结果",
    "Total km": "总里程 km",
    "Travel time": "通行耗时",
    "Tickets / stays": "门票 / 住宿合计",
    "Days": "天数",
    "Stops": "地点数",
    "Attraction ticket comparison": "景点门票对比",
    "Hotel rate comparison": "酒店房价对比",
    "Attraction": "景点",
    "Hotel": "酒店",
    "Lowest": "最低价",
    "Breakfast / cancellation": "早餐 / 取消",
    "Spread": "价差",
    "Live fetch": "实时抓取",
    "No attractions available": "暂无可选景点",
    "No hotels available": "暂无可选酒店",
    "No attractions match": "没有符合条件的景点",
    "Try wider price or rating ranges, or clear tags": "试着放宽价格、评分或清除标签",
    "No hotels match": "没有符合条件的酒店",
    "Try wider price, star or distance ranges": "试着放宽价格、星级或距离条件",
    "Popular": "热门",
    "Night tours": "可夜游",
    "Nearby only": "只看附近",
    "Failed to load": "加载失败",
    "Reload": "重新加载",
    "Details not found": "详情不存在",
    "Already in trip": "已在行程中",
    "Added to trip": "已加入行程",
    "Added as stay": "已加入住宿",
    "Yes": "是", "No": "否",
    "All": "全部",
    "Search an attraction, hotel or landmark": "搜索景点、酒店或地标",
    "Type at least two characters; results span every tracked city.": "至少输入两个字；结果覆盖所有已跟踪城市。",
    "Searching…": "搜索中…", "No matches": "没有匹配结果",
    "Try a shorter name, a brand, or a landmark such as \"Disney\" / \"故宫\".": "试试更短的关键词、品牌名，或地标（如迪士尼、故宫）。",
    "Hotels nearby": "附近酒店", "Load more": "加载更多",
    "results across": "条结果，覆盖", "cities": "个城市",
    "Search failed": "搜索失败",
    "Nearby hotels around": "周边酒店：",
    "Search": "搜索", "Hotel": "酒店", "Attraction": "景点",
    "Platform sources": "平台数据源", "Platform ratings": "平台评分",
    "Live price": "实时价格", "Ratings only": "仅评分", "Blocked": "不可用",
    "price needs platform session": "价格需平台登录会话",
    "No platform ratings matched yet.": "暂未匹配到平台评分。",
    "Prices appear only when a platform actually returns one; Ctrip scores come from its public pages.": "只有平台真实返回价格时才显示报价；携程评分来自其公开页面。",
    "Platform status unavailable.": "平台状态暂不可用。",
    "Settings": "设置", "Theme": "主题", "Auto": "自动", "Light": "浅色", "Dark": "深色", "Map API": "地图 API", "Appearance": "外观", "Language": "语言", "Text size": "字号",
    "Appearance, data sources and map API": "外观、数据源与地图 API",
    "Close settings": "关闭设置", "About": "关于",
    "Data sources & crawl status": "数据源与抓取状态",
    "Continuous nationwide sweep, no configuration": "全网动态轮扫，无需任何配置",
    "Baidu server AK detected: routes use live Baidu routing with per-leg navigation and traffic.": "已检测到百度地图服务端 AK：路线将使用百度实时路径计算，分段导航与路况更准确。",
    "No Baidu server AK: routes use local optimisation (nearest neighbour + 2-opt) and a road factor, labelled as estimates.": "未配置百度地图服务端 AK：将使用本地路径优化（最近邻 + 2-opt）与道路系数估算，结果会标注「估算」。",
    "To reference attraction": "距参照景点",
    "JavaScript API docs": "JavaScript API 文档",
    "Offline schematic map · no AK configured": "离线示意地图 · 未配置 AK",
    "holds only the last fetch per area as JSON and can be cleared in one click. Ctrip, Tongcheng and Qunar throttle anonymous high-frequency access,": "里只有上一次抓取的 JSON 存档，可一键清空。携程/同程/去哪儿对匿名高频访问有风控，",
    "schedule": "定时", "startup": "启动", "manual": "手动", "ok": "正常", "degraded": "部分降级",
    "Baidu Maps web search (built-in)": "百度地图网页检索（内置）",
    "/night from": "/晚起", "/night": "/晚", "Console · My Apps": "控制台 · 我的应用",
    "Healthy": "正常", "Warming up": "预热中", "Running": "运行中", "Degraded": "部分降级",
    "Metro": "地铁", "Areas": "区域", "Coverage": "覆盖率", "Sweeps": "轮扫",
    "Source https://map.baidu.com/ · no key · no crawler configuration": "数据源 https://map.baidu.com/ · 免密钥 · 无需配置爬虫",
    "Name": "名称", "Address": "地址", "Coordinates": "坐标", "Review count": "点评数",
    "Photos": "实景图", "Opening hours": "营业时间",
    "Ticket price (online / list)": "景点票价（在线价 / 门市价）",
    "Live hotel rates and room types": "酒店实时房价与房型",
    "Baidu Maps JS API (real basemap / geolocation)": "百度地图 JS API（真实底图 / 定位）",
    "Baidu Maps Web Service AK (routing / geocoding)": "百度地图 Web 服务 AK（真实路线 / 地理编码）",
    "Optional": "可选", "Configure AK": "配置 AK", "View guide": "查看教学",
    "Use: Map rendering and browser geolocation. Optional: without it the map falls back to the schematic view and routes to local estimates.":
      "用途：地图渲染与浏览器定位。不配置也能用：地图退回离线示意、路线退回本地估算。",
    "Use: Driving, walking and cycling routes plus address lookup. Optional: without it the map falls back to the schematic view and routes to local estimates.":
      "用途：驾车/步行/骑行路径与地址解析。不配置也能用：地图退回离线示意、路线退回本地估算。",
    "Built in. No keys, crawlers, or configuration required: administrative areas are discovered at runtime and continuously re-scanned nationwide.":
      "站点自带能力，不需要配置任何密钥或爬虫：运行时发现全国行政区并持续轮扫。",
    "Baidu Maps AK: real basemap and real routes": "百度地图 AK：真实底图与真实路线",
    "No AK? Everything still works: lists, price comparison, the offline schematic map, nearest-first sorting and locally estimated routes. With an AK, the map switches to the real basemap, browser geolocation becomes available, and routes are computed live by Baidu.":
      "不填 AK 也能用：列表、比价、离线示意地图、就近排序与本地路线估算都可用。填入 AK 后地图换成真实底图、可浏览器定位，路线改由百度实时计算。",
    "Register and verify": "注册并实名",
    "Create a browser-side app": "创建浏览器端应用",
    "Set the Referer whitelist": "填写 Referer 白名单",
    "Copy the AK": "复制 AK",
    "(Optional) create a server-side app": "（可选）创建服务端应用",
    "Paste, save, verify": "粘贴、保存、验证",
    "Register & verify": "注册并实名", "Create browser app": "创建浏览器端应用",
    "Enable JS API": "勾选 JS API", "Whitelist *": "白名单填 *",
    "Copy AK": "复制 AK", "Paste & test": "粘贴并测试",
    "Open lbsyun.baidu.com and sign up with a phone number. Individual developers must complete identity verification, otherwise calls are limited.":
      "打开 lbsyun.baidu.com，用手机号注册；个人开发者需完成实名认证，否则调用会受到限制。",
    "Console → App Management → My Apps → Create App. Choose the Browser type and enable JavaScript API.":
      "控制台 → 应用管理 → 我的应用 → 创建应用。应用类型选浏览器端，勾选 JavaScript API。",
    "For local demos use * (or add 127.0.0.1 and localhost as well). For production, replace it with your domain, e.g. https://your.site/*.":
      "本地演示填 *（或同时加 127.0.0.1、localhost）；上线后改成你的域名，例如 https://your.site/*。",
    "After saving, the list shows a 24-character AK. That is the Browser-side AK to paste below.":
      "提交后列表会显示 24 位左右的 AK，这就是要填的浏览器端 AK。",
    "For real driving/transit routes and address lookup, create a second app of type Server with IP whitelist 127.0.0.1 for local use, then paste its AK into Server AK.":
      "要真实驾车/公交路线与地址解析，再建一个服务端应用，IP 白名单填 127.0.0.1，把它的 AK 填到服务端 AK。",
    "Paste the AK into the map configuration (the field accepts paste only), save, then reload the page. The map header shows Baidu Maps when it is active.":
      "把 AK 粘贴到地图配置（输入框只接受粘贴），保存后刷新页面；地图标题显示百度地图即生效。",
    "APP service disabled": "APP 服务被禁用",
    "JavaScript API was not enabled when the app was created": "创建应用时没有勾选 JavaScript API",
    "Edit the app, enable JavaScript API, save again": "编辑应用，勾选 JavaScript API 后重新保存",
    "AK does not exist / INVALID_USER_SCODE": "AK 不存在 / INVALID_USER_SCODE",
    "The AK was copied incompletely or has been deleted": "AK 复制不完整或已被删除",
    "Copy it again from the console without spaces": "回控制台重新复制，不要带空格",
    "Referer whitelist validation failed": "Referer 白名单校验失败",
    "The whitelist does not include the current origin": "白名单没有包含当前页面来源",
    "Use * for the browser app, or add 127.0.0.1": "浏览器端应用白名单填 *，或加入 127.0.0.1",
    "Permission denied": "权限校验失败",
    "A browser AK was used against a server-side endpoint": "浏览器 AK 用在了服务端接口",
    "Create a separate server-side AK for server endpoints": "服务端接口另建服务端 AK",
    "Quota exceeded": "配额超限 / quota",
    "The daily free quota is used up": "当日免费额度用完",
    "It resets the next day, or raise the quota in the console": "次日恢复，或在控制台提升配额",
    "After saving, click Test AK: it loads the Baidu Maps JS API once and reports success or the exact error code.":
      "保存后点击测试 AK：会真实加载一次百度地图 JS，成功会提示，失败会返回具体错误码。",
    "The map panel header changes to Baidu Maps and real roads/place labels appear when the browser AK works.":
      "地图面板标题变成百度地图，并能看到真实道路与地名，即浏览器端 AK 生效。",
    "Generate a route in Trip & Route: if each leg is labelled Live Baidu route, the server AK is active.":
      "在行程与路线里生成路线，若每一步显示百度实时路径，则为服务端 AK 生效。",
    "Both AKs can be the same app if it enables JavaScript API and Web Service API together, or two separate apps for cleaner permissions.":
      "两个 AK 可以来自同一应用（同时勾选 JavaScript API 与 Web 服务 API），也可以分开建两个应用，权限更清晰。",
    "AKs are stored only on this machine in data/runtime_config.json, encrypted at rest. Delete that file to revoke the local configuration.":
      "AK 只保存在本机 data/runtime_config.json，落盘为密文；删除该文件即可撤销本机配置。",
    "How to verify": "怎么验证生效",
    "Search attractions / hotels / tags": "搜索景点 / 酒店 / 标签",
    "Enter any city; leave blank for nationwide": "输入任意城市，留空为全国",
    "Min price": "最低价",
    "Max price": "最高价",
    "Paste only: Ctrl+V / Cmd+V": "仅支持粘贴：Ctrl+V / ⌘V",
    "Min ¥": "最低 ¥",
    "Max ¥": "最高 ¥",
    "Reference attraction (auto)": "参照景点（自动）",
    "Loading hotel details": "正在加载酒店详情",
    "Loading attraction details": "正在加载景点详情",
    "Failed to load details": "详情加载失败",
    "Start the service with start.bat or python app.py, then open http://127.0.0.1:8848": "请用 start.bat 或 python app.py 启动服务，然后访问 http://127.0.0.1:8848",
    "Historic Site": "历史古迹", "Historic Building": "历史建筑", "Museum": "博物馆",
    "Art Museum": "美术馆", "Memorial": "纪念馆", "Science Museum": "科技馆",
    "Park": "公园", "Forest Park": "森林公园", "Wetland Park": "湿地公园",
    "Theme Park": "主题公园", "Amusement Park": "乐园", "Water Park": "水上乐园",
    "Zoo": "动物园", "Botanical Garden": "植物园", "Aquarium": "海洋馆",
    "Ancient Town": "古镇", "Old Town": "古城", "Pedestrian Street": "步行街",
    "Viewpoint": "观景台", "Hot Spring": "温泉", "Resort": "度假区",
    "Scenic Area": "景区", "Scenic Spot": "风景名胜", "Heritage Site": "遗址",
    "Temple": "寺庙", "Pagoda": "塔", "Lake": "湖泊", "Mountain": "山岳",
    "Canyon": "峡谷", "Waterfall": "瀑布", "Grassland": "草原", "Island": "岛屿",
    "Church": "教堂", "City Wall": "城墙", "Night View": "夜景",
    "Family Friendly": "亲子", "Food": "美食", "Show": "演出", "Seaside": "海滨",
    "City": "城市", "National": "国家级", "World Heritage": "世界遗产", "Landmark": "地标",
    "Garden": "园林", "Culture": "文化", "Art": "艺术", "Shopping": "购物",
    "Leisure": "休闲娱乐", "Sports": "运动健身", "Theater": "剧院",
    "Ancient Village": "古村", "City Park": "城市公园", "Forest": "森林",
    "Exhibition Hall": "展览馆", "Sports Venue": "体育场馆", "Shopping Street": "商业街",
  };

  const PARTIAL = [
    ["holds only the last fetch per area as JSON and can be cleared in one click. Ctrip, Tongcheng and Qunar throttle anonymous high-frequency access,", "里只有上一次抓取的 JSON 存档，可一键清空。携程/同程/去哪儿对匿名高频访问有风控，"],
    ["so the page does not crawl them directly. Baidu Maps already aggregates channel rates and the page labels them as Qunar (via Baidu Maps).", "页面不直接抓它们；百度地图本身聚合了去哪儿等渠道的报价，页面会如实标注来源。"],
    ["ships no database and no bundled dataset", "不携带数据库与任何预置数据"],
    [": attractions, hotels, tickets and rates are crawled from Baidu Maps at runtime.", "：景点、酒店、门票、房价都在运行时从百度地图网页检索抓取，"],
  ];

  const RULES = [
    [/^([\d,]+) attractions · page (\d+) (Live crawl|Last snapshot|No data)(?: · (.+))?$/, (m) =>
      `${m[1]} 个景点 · 第 ${m[2]} 页${m[3] === "Live crawl" ? " · 实时抓取" : m[3] === "Last snapshot" ? " · 上次抓取存档" : ""}${m[4] ? " · " + m[4] : ""}`],
    [/^([\d,]+) attractions$/, (m) => `${m[1]} 个景点`],
    [/^([\d,]+) hotels$/, (m) => `${m[1]} 家酒店`],
    [/^([\d,]+) hotels · near (.+)$/, (m) => `${m[1]} 家酒店 · 参照 ${m[2]}`],
    [/^¥([\d,.]+)\/night from$/, (m) => `¥${m[1]}/晚起`],
    [/^To reference attraction ([\d.]+) km$/, (m) => `距参照景点 ${m[1]} 公里`],
    [/^Price from (.+)$/, (m) => `报价来源 ${m[1]}`],
    [/^(.+) failed: (.+)$/, (m) => `${m[1]}失败：${m[2]}`],
    [/^([\d,]+) attractions · ([\d,]+) hotels$/, (m) => `${m[1]} 个景点 · ${m[2]} 家酒店`],
    [/^Background sweep completed: ([\d,]+) attractions · ([\d,]+) hotels$/, (m) => `后台轮扫完成：${m[1]} 个景点 · ${m[2]} 家酒店`],
    [/^Route ready: (\d+) stops \/ ([\d.]+) km$/, (m) => `路线已生成：${m[1]} 个地点 / ${m[2]} 公里`],
    [/^Attractions near (.+)$/, (m) => `${m[1]} 周边景点`],
    [/^Nearby hotels around (.+)$/, (m) => `${m[1]} 周边酒店`],
    [/^Located via (.+)$/, (m) => `定位来源：${m[1]}`],
    [/^Set as origin: (.+)$/, (m) => `已设为出发点：${m[1]}`],
    [/^Cleared (\d+) area snapshots$/, (m) => `已清空 ${m[1]} 个区域快照`],
    [/^(\d+) reference attractions available$/, (m) => `已加载 ${m[1]} 个参照景点`],
    [/^Switched to (.+); live data$/, (m) => `已切换到 ${m[1]}，实时数据`],
    [/^(\d+) (?:attractions and hotels|attractions|hotels) across (\d+) cities(?: · showing (\d+))?(?: · (live crawl|last snapshot))?$/, (m) => {
      const kind = m[1] + (m[1] === '1' ? ' 条' : ' 条');
      const scope = m[4] === 'live crawl' ? ' · 实时抓取' : m[4] === 'last snapshot' ? ' · 上次抓取存档' : '';
      return `${kind}结果 · 覆盖 ${m[2]} 个城市` + (m[3] ? ` · 已显示 ${m[3]} 条` : '') + scope;
    }],
    [/^🚇 (.+) · (\d+) m walk$/, (m) => `🚇 ${m[1]} · 步行 ${m[2]} 米`],
    [/^([\d,]+) attractions · page (\d+) (Live crawl|Last snapshot)(?: · (.+))?$/, (m) =>
      `${m[1]} 个景点 · 第 ${m[2]} 页${m[3] === "Live crawl" ? " · 实时抓取" : " · 上次抓取存档"}${m[4] ? " · " + m[4] : ""}`],
    [/^([\d,]+) (?:quote|quotes) · lowest (.+)$/, (m) => `${m[1]} 个报价 · 最低 ${m[2]}`],
    [/^([\d,]+) reviews$/, (m) => `${m[1]} 条点评`],
    [/^([\d.]+) km away$/, (m) => `${m[1]} 公里`],
    [/^([\d.]+) km · (.+) min walk$/, (m) => `${m[1]} 公里 · 步行约 ${m[2]} 分钟`],
    [/^([\d.]+) m walk$/, (m) => `步行 ${m[1]} 米`],
    [/^Within ([\d.]+) km$/, (m) => `${m[1]} 公里内`],
    [/^Metro within ([\d.]+) m$/, (m) => `地铁 ${m[1]} 米内`],
    [/^([\d.]+)-star$/, (m) => `${m[1]} 星`],
    [/^([\d.]+) stars? · ★ ([\d.]+)$/, (m) => `${m[1]} 星 · ★ ${m[2]}`],
    [/^¥([\d,.]+) \/night from · lowest ¥([\d,.]+)$/, (m) => `¥${m[1]}/晚起 · 最低 ¥${m[2]}`],
    [/^¥([\d,.]+)\/night · (.+) away$/, (m) => `¥${m[1]}/晚 · 距此 ${m[2]}`],
    [/^Areas (\d+) \/ (\d+)$/, (m) => `已扫描 ${m[1]} / 发现 ${m[2]}`],
    [/^Coverage (\d+)%$/, (m) => `覆盖率 ${m[1]}%`],
    [/^Sweeps (\d+)$/, (m) => `轮扫 ${m[1]}`],
    [/^Discovery rounds (\d+)$/, (m) => `发现轮次 ${m[1]}`],
    [/^(\d+) stops \/ ([\d.]+) km$/, (m) => `${m[1]} 个地点 / ${m[2]} 公里`],
    [/^(\d+) places · about ¥([\d,.]+)$/, (m) => `${m[1]} 个地点 · 约 ¥${m[2]}`],
    [/^(\d+) places · ([\d.]+) days · .*$/, (m) => `${m[1]} 个地点 · ${m[2]} 天`],
    [/^Depart (.+) · finish (.+) · ([\d.]+) km$/, (m) => `${m[1]} 出发 · ${m[2]} 结束 · ${m[3]} 公里`],
    [/^Arrive (.+) · leave (.+)$/, (m) => `${m[1]} 抵达 · ${m[2]} 离开`],
    [/^About (\d+) min visiting and staying; ([\d.]+) h in total \((.+)\)$/, (m) => `含游览与住宿约 ${m[1]} 分钟，全天 ${m[2]} 小时（${m[3]}）`],
    [/^Suggested visit (.+)$/, (m) => `建议游览 ${m[1]}`],
    [/^(\d+) h(?: (\d+) min)?$/, (m) => `${m[1]} 小时${m[2] ? " " + m[2] + " 分" : ""}`],
    [/^(\d+) min$/, (m) => `${m[1]} 分钟`],
    [/^(\d+) records processed \(([^)]+)\)$/, (m) => `处理 ${m[1]} 条（${m[2]}）`],
    [/^Dynamic national sweep · (\d+) areas discovered · (\d+) scanned · progress (\d+)%$/, (m) => `全网动态轮扫 · 已发现 ${m[1]} 个区域 · 已扫描 ${m[2]} 个 · 进度 ${m[3]}%`],
    [/^(Live crawl|Last snapshot) · (.+)$/, (m) =>
      `${m[1] === "Live crawl" ? "实时抓取" : "上次抓取存档"} · ${m[2]}`],
    [/^([\d,]+) attractions · page (\d+)$/, (m) => `${m[1]} 个景点 · 第 ${m[2]} 页`],
    [/^([\d,]+) (quote|quotes) · lowest$/, (m) => `${m[1]} 个报价 · 最低`],
    [/^([\d,]+) star$/, (m) => `${m[1]} 星`],
    [/^Page (\d+)$/, (m) => `第 ${m[1]} 页`],
    [/^Day (\d+)$/, (m) => `第 ${m[1]} 天`],
    [/^(.+) from (.+)$/, (m) => `${m[2]} 至 ${m[1]}`],
  ];

  // 默认语言跟随浏览器：中文系统直接显示中文，其它语言显示英文；用户手动切换后以记忆值为准
  const storedLang = localStorage.getItem(STORAGE_KEY);
  const browserLang = String((navigator.language || navigator.userLanguage || '') + '').toLowerCase();
  let lang = storedLang === 'zh' || storedLang === 'en'
    ? storedLang
    : (browserLang.indexOf('zh') === 0 ? 'zh' : 'en');
  const originals = new Map(); // text node / element -> original English value
  const translated = new WeakMap(); // text node -> value we wrote during translation
  const attrOriginals = new Map();

  function tidy(text) {
    // 中文里不应出现两个汉字之间的空格（HTML 里换行/强调标签会带出来）
    return String(text)
      .replace(/(?<=[一-鿿])[ 	]+(?=[一-鿿])/g, '')
      .replace(/(?<=[一-鿿])[ 	]+$/g, '');
  }

  function lookup(value) {
    const text = String(value == null ? '' : value);
    if (lang !== 'zh' || !text) return text;
    const key = text.trim();
    if (!key) return text;
    if (Object.prototype.hasOwnProperty.call(ZH, key)) {
      return text.replace(key, ZH[key]);
    }
    for (const [en, zh] of PARTIAL) {
      if (text.includes(en)) return text.replace(en, zh);
    }
    for (const [re, fn] of RULES) {
      const m = key.match(re);
      if (m) return text.replace(key, fn(m));
    }
    return text;
  }

  function translate(value) {
    const out = lookup(value);
    return lang === 'zh' ? tidy(out) : out;
  }

  function translateTextNode(node) {
    const value = node.nodeValue;
    if (!value || !value.trim()) return;
    if (lang === 'zh') {
      originals.set(node, value);
      const next = translate(value);
      if (next !== value) {
        node.nodeValue = next;
        translated.set(node, next);
      }
    } else if (originals.has(node)) {
      node.nodeValue = originals.get(node);
    }
  }

  function translateAttributes(el) {
    for (const attr of ['placeholder', 'title', 'aria-label']) {
      if (!el.hasAttribute(attr)) continue;
      const key = el;
      const source = attrOriginals.get(key) || {};
      if (lang === 'zh') {
        source[attr] = source[attr] || el.getAttribute(attr);
        attrOriginals.set(key, source);
        const next = lookup(source[attr]);
        if (next !== source[attr]) el.setAttribute(attr, next);
      } else if (source[attr]) {
        el.setAttribute(attr, source[attr]);
      }
    }
  }

  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) {
      translateTextNode(root);
      return;
    }
    if (root.nodeType !== 1 && root.nodeType !== 9) return;
    if (root.nodeType === 1) translateAttributes(root);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let node = walker.nextNode();
    while (node) {
      if (node.nodeType === 3) translateTextNode(node);
      else if (node.nodeType === 1) translateAttributes(node);
      node = walker.nextNode();
    }
  }

  let observer = null;
  let applying = false;

  function startObserver() {
    if (observer) return;
    observer = new MutationObserver((mutations) => {
      if (lang !== 'zh' || applying) return;
      applying = true;
      try {
        for (const mutation of mutations) {
          if (mutation.type === 'characterData') {
            const node = mutation.target;
            if (node.nodeType === 3 && node.nodeValue && node.nodeValue.trim()) {
              if (translated.get(node) === node.nodeValue) continue;
              originals.set(node, node.nodeValue);
              const next = translate(node.nodeValue);
              if (next !== node.nodeValue) {
                node.nodeValue = next;
                translated.set(node, next);
              }
            }
          } else if (mutation.type === 'childList') {
            mutation.addedNodes.forEach((child) => walk(child));
          }
        }
      } finally {
        applying = false;
      }
    });
    observer.observe(document.body, { subtree: true, childList: true, characterData: true });
  }

  function apply(nextLang) {
    lang = nextLang === 'zh' ? 'zh' : 'en';
    localStorage.setItem(STORAGE_KEY, lang);
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    document.title = translate('TravelOne · All-in-one travel assistant');
    const meta = document.querySelector('meta[name="description"]');
    if (meta) {
      const orig = meta.getAttribute('data-i18n-orig') || meta.getAttribute('content');
      meta.setAttribute('data-i18n-orig', orig);
      meta.setAttribute('content', lang === 'zh'
        ? '实时抓取景点与酒店、门票房价比价、百度地图定位与行程路线规划的一站式旅行应用（无数据库、单页集成）'
        : orig);
    }
    walk(document.body);
    updateButtons();
    updateLangSeg();
    startObserver();
    document.dispatchEvent(new CustomEvent('travelone:lang', { detail: { lang } }));
  }

  function updateButtons() {
    document.querySelectorAll('[data-lang-toggle]').forEach((btn) => {
      btn.textContent = lang === 'zh' ? 'EN' : '中文';
      btn.setAttribute('aria-label', lang === 'zh' ? 'Switch to English' : '切换到中文');
      btn.setAttribute('title', lang === 'zh' ? 'Switch to English' : '切换到中文');
    });
  }

  function updateLangSeg() {
    document.querySelectorAll('[data-lang-set]').forEach((btn) => {
      const active = btn.dataset.langSet === lang;
      btn.classList.toggle('on', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function toggle() {
    apply(lang === 'zh' ? 'en' : 'zh');
  }

  window.TravelI18n = {
    t: translate,
    apply,
    toggle,
    get lang() { return lang; },
  };

  document.addEventListener('click', (ev) => {
    const quick = ev.target.closest('[data-lang-toggle]');
    if (quick) { toggle(); return; }
    const explicit = ev.target.closest('[data-lang-set]');
    if (explicit) apply(explicit.dataset.langSet);
  });
  document.addEventListener('DOMContentLoaded', () => {
    apply(lang);
  });
})();