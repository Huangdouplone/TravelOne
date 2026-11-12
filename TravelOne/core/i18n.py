# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""English display helpers for UI chrome and vocabulary.

Place names and POI names come from upstream in Chinese; they are proper nouns.
This module provides English labels for administrative areas and tag vocabulary
so the interface itself can stay fully English.
"""
from __future__ import annotations

import re

from typing import Iterable, List

CITY_EN = {
    # 动态发现的地级/县级点位（覆盖全国轮扫结果）
    "七台河": "Qitaihe", "乌海": "Wuhai", "伊春": "Yichun", "侯马": "Houma",
    "信阳": "Xinyang", "克拉玛依": "Karamay", "六安": "Lu'an", "兴义": "Xingyi",
    "内江": "Neijiang", "冷水江": "Lengshuijiang", "吉安": "Ji'an", "周口": "Zhoukou",
    "商洛": "Shangluo", "嫩江": "Nenjiang", "安国": "Anguo", "定西": "Dingxi",
    "宣城": "Xuancheng", "崇左": "Chongzuo", "嵊州": "Shengzhou",
    "巴彦淖尔": "Bayannur", "库车": "Kuqa", "应城": "Yingcheng", "康定": "Kangding",
    "廊坊": "Langfang", "建瓯": "Jian'ou", "当阳": "Dangyang", "德令哈": "Delingha",
    "德州": "Dezhou", "德阳": "Deyang", "怒江傈僳族": "Nujiang", "怒江": "Nujiang",
    "慈溪": "Cixi", "揭阳": "Jieyang", "攀枝花": "Panzhihua", "敦化": "Dunhua",
    "日照": "Rizhao", "昭通": "Zhaotong", "朔州": "Shuozhou", "松原": "Songyuan",
    "枣庄": "Zaozhuang", "根河": "Genhe", "梅河口": "Meihekou", "毕节": "Bijie",
    "江油": "Jiangyou", "沧州": "Cangzhou", "海北藏族": "Haibei", "海北": "Haibei",
    "淮北": "Huaibei", "滁州": "Chuzhou", "潮州": "Chaozhou", "瑞昌": "Ruichang",
    "瑞金": "Ruijin", "登封": "Dengfeng", "白银": "Baiyin", "百色": "Baise",
    "监利": "Jianli", "绥化": "Suihua", "聊城": "Liaocheng", "肥城": "Feicheng",
    "芒市": "Mangshi", "茂名": "Maoming", "荣成": "Rongcheng", "莱州": "Laizhou",
    "蚌埠": "Bengbu", "衡水": "Hengshui", "许昌": "Xuchang", "调兵山": "Diaobingshan",
    "辽源": "Liaoyuan", "邹平": "Zouping", "郴州": "Chenzhou", "都匀": "Duyun",
    "金昌": "Jinchang", "铜川": "Tongchuan", "阿勒泰": "Altay", "伊犁": "Ili",
    "巴音郭楞": "Bayingolin", "博尔塔拉": "Bortala", "昌吉回族": "Changji",
    "凉山彝族": "Liangshan", "甘孜藏族": "Ganzi", "阿里": "Ngari", "那曲": "Nagqu",
    "日喀则": "Shigatse", "林芝": "Nyingchi", "山南": "Shannan", "昌都": "Qamdo",
    "鄂尔多斯": "Ordos", "呼伦贝尔": "Hulunbuir", "满洲里": "Manzhouli",
    "兴安盟": "Hinggan", "锡林郭勒": "Xilingol", "阿拉善": "Alxa",
    "黔东南": "Qiandongnan", "黔西南": "Qianxinan", "黔南": "Qiannan",
    "恩施土家族苗族": "Enshi", "恩施": "Enshi", "湘西土家族苗族": "Xiangxi",
    "延边朝鲜族": "Yanbian", "长白山": "Changbaishan", "大兴安岭": "Daxinganling",
    "伊春市": "Yichun",
    "北京": "Beijing", "北京市": "Beijing", "上海": "Shanghai", "上海市": "Shanghai",
    "天津": "Tianjin", "天津市": "Tianjin", "重庆": "Chongqing", "重庆市": "Chongqing",
    "广州": "Guangzhou", "广州市": "Guangzhou", "深圳": "Shenzhen", "深圳市": "Shenzhen",
    "杭州": "Hangzhou", "杭州市": "Hangzhou", "南京": "Nanjing", "南京市": "Nanjing",
    "苏州": "Suzhou", "苏州市": "Suzhou", "无锡": "Wuxi", "无锡市": "Wuxi",
    "宁波": "Ningbo", "宁波市": "Ningbo", "温州": "Wenzhou", "温州市": "Wenzhou",
    "绍兴": "Shaoxing", "绍兴市": "Shaoxing", "嘉兴": "Jiaxing", "嘉兴市": "Jiaxing",
    "金华": "Jinhua", "金华市": "Jinhua", "台州": "Taizhou", "台州市": "Taizhou",
    "成都": "Chengdu", "成都市": "Chengdu", "乐山": "Leshan", "乐山市": "Leshan",
    "西安": "Xi'an", "西安市": "Xi'an", "咸阳": "Xianyang", "咸阳市": "Xianyang",
    "武汉": "Wuhan", "武汉市": "Wuhan", "宜昌": "Yichang", "宜昌市": "Yichang",
    "长沙": "Changsha", "长沙市": "Changsha", "张家界": "Zhangjiajie", "张家界市": "Zhangjiajie",
    "郑州": "Zhengzhou", "郑州市": "Zhengzhou", "洛阳": "Luoyang", "洛阳市": "Luoyang",
    "开封": "Kaifeng", "开封市": "Kaifeng", "济南": "Jinan", "济南市": "Jinan",
    "青岛": "Qingdao", "青岛市": "Qingdao", "烟台": "Yantai", "烟台市": "Yantai",
    "威海": "Weihai", "威海市": "Weihai", "泰安": "Tai'an", "泰安市": "Tai'an",
    "厦门": "Xiamen", "厦门市": "Xiamen", "福州": "Fuzhou", "福州市": "Fuzhou",
    "泉州": "Quanzhou", "泉州市": "Quanzhou", "南昌": "Nanchang", "南昌市": "Nanchang",
    "景德镇": "Jingdezhen", "景德镇市": "Jingdezhen", "合肥": "Hefei", "合肥市": "Hefei",
    "黄山": "Huangshan", "黄山市": "Huangshan", "哈尔滨": "Harbin", "哈尔滨市": "Harbin",
    "长春": "Changchun", "长春市": "Changchun", "吉林": "Jilin", "吉林市": "Jilin",
    "沈阳": "Shenyang", "沈阳市": "Shenyang", "大连": "Dalian", "大连市": "Dalian",
    "丹东": "Dandong", "丹东市": "Dandong", "石家庄": "Shijiazhuang", "石家庄市": "Shijiazhuang",
    "唐山": "Tangshan", "唐山市": "Tangshan", "秦皇岛": "Qinhuangdao", "秦皇岛市": "Qinhuangdao",
    "承德": "Chengde", "承德市": "Chengde", "保定": "Baoding", "保定市": "Baoding",
    "太原": "Taiyuan", "太原市": "Taiyuan", "大同": "Datong", "大同市": "Datong",
    "平遥": "Pingyao", "平遥县": "Pingyao", "呼和浩特": "Hohhot", "呼和浩特市": "Hohhot",
    "包头": "Baotou", "包头市": "Baotou", "鄂尔多斯": "Ordos", "鄂尔多斯市": "Ordos",
    "呼伦贝尔": "Hulunbuir", "呼伦贝尔市": "Hulunbuir", "南宁": "Nanning", "南宁市": "Nanning",
    "桂林": "Guilin", "桂林市": "Guilin", "柳州": "Liuzhou", "柳州市": "Liuzhou",
    "北海": "Beihai", "北海市": "Beihai", "阳朔": "Yangshuo", "阳朔县": "Yangshuo",
    "海口": "Haikou", "海口市": "Haikou", "三亚": "Sanya", "三亚市": "Sanya",
    "贵阳": "Guiyang", "贵阳市": "Guiyang", "遵义": "Zunyi", "遵义市": "Zunyi",
    "昆明": "Kunming", "昆明市": "Kunming", "大理": "Dali", "大理市": "Dali",
    "丽江": "Lijiang", "丽江市": "Lijiang", "西双版纳": "Xishuangbanna",
    "香格里拉": "Shangri-La", "香格里拉市": "Shangri-La", "腾冲": "Tengchong", "腾冲市": "Tengchong",
    "拉萨": "Lhasa", "拉萨市": "Lhasa", "日喀则": "Shigatse", "日喀则市": "Shigatse",
    "林芝": "Nyingchi", "林芝市": "Nyingchi", "兰州": "Lanzhou", "兰州市": "Lanzhou",
    "敦煌": "Dunhuang", "敦煌市": "Dunhuang", "嘉峪关": "Jiayuguan", "嘉峪关市": "Jiayuguan",
    "张掖": "Zhangye", "张掖市": "Zhangye", "天水": "Tianshui", "天水市": "Tianshui",
    "酒泉": "Jiuquan", "酒泉市": "Jiuquan", "西宁": "Xining", "西宁市": "Xining",
    "格尔木": "Golmud", "格尔木市": "Golmud", "银川": "Yinchuan", "银川市": "Yinchuan",
    "中卫": "Zhongwei", "中卫市": "Zhongwei", "乌鲁木齐": "Urumqi", "乌鲁木齐市": "Urumqi",
    "喀什": "Kashgar", "喀什市": "Kashgar", "吐鲁番": "Turpan", "吐鲁番市": "Turpan",
    "伊犁": "Ili", "伊犁哈萨克自治州": "Ili", "阿勒泰": "Altay", "阿勒泰市": "Altay",
    "库尔勒": "Korla", "库尔勒市": "Korla", "哈密": "Hami", "哈密市": "Hami",
    "香港": "Hong Kong", "澳门": "Macau", "台北": "Taipei", "高雄": "Kaohsiung",
    "台中": "Taichung", "花莲": "Hualien", "东莞": "Dongguan", "东莞市": "Dongguan",
    "佛山": "Foshan", "佛山市": "Foshan", "珠海": "Zhuhai", "珠海市": "Zhuhai",
    "中山": "Zhongshan", "中山市": "Zhongshan", "汕头": "Shantou", "汕头市": "Shantou",
    "惠州": "Huizhou", "惠州市": "Huizhou", "常州": "Changzhou", "常州市": "Changzhou",
    "徐州": "Xuzhou", "徐州市": "Xuzhou", "扬州": "Yangzhou", "扬州市": "Yangzhou",
    "镇江": "Zhenjiang", "镇江市": "Zhenjiang", "南通": "Nantong", "南通市": "Nantong",
    "盐城": "Yancheng", "盐城市": "Yancheng", "淮安": "Huai'an", "淮安市": "Huai'an",
    "连云港": "Lianyungang", "连云港市": "Lianyungang", "泰州": "Taizhou", "泰州市": "Taizhou",
    "宿迁": "Suqian", "宿迁市": "Suqian", "舟山": "Zhoushan", "舟山市": "Zhoushan",
    "湖州": "Huzhou", "湖州市": "Huzhou", "衢州": "Quzhou", "衢州市": "Quzhou",
    "丽水": "Lishui", "丽水市": "Lishui", "义乌": "Yiwu", "义乌市": "Yiwu",
    "绵阳": "Mianyang", "绵阳市": "Mianyang", "宜宾": "Yibin", "宜宾市": "Yibin",
    "泸州": "Luzhou", "泸州市": "Luzhou", "南充": "Nanchong", "南充市": "Nanchong",
    "都江堰": "Dujiangyan", "都江堰市": "Dujiangyan", "峨眉山": "Emeishan", "峨眉山市": "Emeishan",
    "遵义市": "Zunyi", "安顺": "Anshun", "安顺市": "Anshun", "六盘水": "Liupanshui",
    "六盘水市": "Liupanshui", "曲靖": "Qujing", "曲靖市": "Qujing", "玉溪": "Yuxi",
    "玉溪市": "Yuxi", "宝鸡": "Baoji", "宝鸡市": "Baoji", "延安": "Yan'an", "延安市": "Yan'an",
    "汉中": "Hanzhong", "汉中市": "Hanzhong", "榆林": "Yulin", "榆林市": "Yulin",
    "襄阳": "Xiangyang", "襄阳市": "Xiangyang", "荆州": "Jingzhou", "荆州市": "Jingzhou",
    "十堰": "Shiyan", "十堰市": "Shiyan", "恩施": "Enshi", "恩施土家族苗族自治州": "Enshi",
    "岳阳": "Yueyang", "岳阳市": "Yueyang", "常德": "Changde", "常德市": "Changde",
    "衡阳": "Hengyang", "衡阳市": "Hengyang", "凤凰": "Fenghuang", "凤凰县": "Fenghuang",
    "安阳": "Anyang", "安阳市": "Anyang", "焦作": "Jiaozuo", "焦作市": "Jiaozuo",
    "南阳": "Nanyang", "南阳市": "Nanyang", "曲阜": "Qufu", "曲阜市": "Qufu",
    "蓬莱": "Penglai", "漳州": "Zhangzhou", "漳州市": "Zhangzhou", "武夷山": "Wuyishan",
    "武夷山市": "Wuyishan", "九江": "Jiujiang", "九江市": "Jiujiang", "上饶": "Shangrao",
    "上饶市": "Shangrao", "婺源": "Wuyuan", "婺源县": "Wuyuan", "赣州": "Ganzhou",
    "赣州市": "Ganzhou", "芜湖": "Wuhu", "芜湖市": "Wuhu", "安庆": "Anqing",
    "安庆市": "Anqing", "池州": "Chizhou", "池州市": "Chizhou", "亳州": "Bozhou",
    "亳州市": "Bozhou", "齐齐哈尔": "Qiqihar", "齐齐哈尔市": "Qiqihar",
    "牡丹江": "Mudanjiang", "牡丹江市": "Mudanjiang", "佳木斯": "Jiamusi",
    "佳木斯市": "Jiamusi", "漠河": "Mohe", "漠河市": "Mohe", "延吉": "Yanji",
    "延吉市": "Yanji", "长白山": "Changbaishan", "鞍山": "Anshan", "鞍山市": "Anshan",
    "本溪": "Benxi", "本溪市": "Benxi", "邯郸": "Handan", "邯郸市": "Handan",
    "张家口": "Zhangjiakou", "张家口市": "Zhangjiakou", "临汾": "Linfen",
    "临汾市": "Linfen", "运城": "Yuncheng", "运城市": "Yuncheng", "满洲里": "Manzhouli",
    "满洲里市": "Manzhouli", "赤峰": "Chifeng", "赤峰市": "Chifeng", "梧州": "Wuzhou",
    "梧州市": "Wuzhou", "琼海": "Qionghai", "琼海市": "Qionghai", "儋州": "Danzhou",
    "儋州市": "Danzhou", "文昌": "Wenchang", "文昌市": "Wenchang", "铜仁": "Tongren",
    "铜仁市": "Tongren", "荔波": "Libo", "荔波县": "Libo", "昌都": "Qamdo",
    "昌都市": "Qamdo", "阿里": "Ngari", "山南": "Shannan", "山南市": "Shannan",
    "海东": "Haidong", "海东市": "Haidong", "玉树": "Yushu", "玉树市": "Yushu",
    "茶卡": "Chaka", "石嘴山": "Shizuishan", "石嘴山市": "Shizuishan",
    "吴忠": "Wuzhong", "吴忠市": "Wuzhong", "固原": "Guyuan", "固原市": "Guyuan",
    "和田": "Hotan", "和田市": "Hotan", "丹江口": "Danjiangkou", "丹江口市": "Danjiangkou",
}

TAG_EN = {
    # 数据驱动汇总的常见类型（与上游标签一致）
    "旅游景点": "Tourist Attraction", "度假村": "Resort", "儿童乐园": "Kids' Playground",
    "艺术馆": "Art Gallery", "村庄": "Village", "乡镇": "Town", "旅游度假区": "Tourism Resort",
    "温泉酒店": "Hot Spring Hotel", "经济型": "Budget", "舒适型": "Comfort",
    "高档型": "Upscale", "豪华型": "Luxury", "民宿": "Guesthouse", "商务酒店": "Business Hotel",
    "公寓式酒店": "Apartment Hotel", "青年旅舍": "Hostel", "客栈": "Inn",
    "四星级": "4-star", "五星级": "5-star", "三星级": "3-star", "招待所": "Guesthouse",
    "景点附属设施": "Facility", "门": "Gate", "休闲场所": "Leisure Venue",
    "游乐场": "Playground", "水族馆": "Aquarium", "动物园": "Zoo", "植物园": "Botanical Garden",
    "观景台": "Viewpoint", "温泉": "Hot Spring", "滑雪": "Skiing", "漂流": "Rafting",
    "采摘": "Picking Farm", "农家乐": "Farmhouse", "湿地": "Wetland", "石窟": "Grottoes",
    "石刻": "Stone Inscription", "陵墓": "Tomb", "庙": "Temple", "道观": "Taoist Temple",
    "图书馆": "Library", "剧院": "Theater", "音乐厅": "Concert Hall", "沙滩": "Beach",
    "沙漠": "Desert", "冰川": "Glacier", "溶洞": "Karst Cave", "石林": "Stone Forest",

    "历史古迹": "Historic Site", "古迹": "Historic Site", "历史建筑": "Historic Building",
    "博物馆": "Museum", "美术馆": "Art Museum", "纪念馆": "Memorial", "科技馆": "Science Museum",
    "公园": "Park", "森林公园": "Forest Park", "湿地公园": "Wetland Park",
    "主题公园": "Theme Park", "乐园": "Amusement Park", "水上乐园": "Water Park",
    "动物园": "Zoo", "植物园": "Botanical Garden", "海洋馆": "Aquarium",
    "古镇": "Ancient Town", "古城": "Old Town", "步行街": "Pedestrian Street",
    "观景台": "Viewpoint", "温泉": "Hot Spring", "度假区": "Resort", "景区": "Scenic Area",
    "风景名胜": "Scenic Spot", "遗址": "Heritage Site", "寺": "Temple", "寺庙": "Temple",
    "塔": "Pagoda", "湖": "Lake", "山": "Mountain", "峡谷": "Canyon", "瀑布": "Waterfall",
    "草原": "Grassland", "岛": "Island", "教堂": "Church", "城墙": "City Wall",
    "夜景": "Night View", "夜游": "Night Tour", "免费": "Free", "亲子": "Family Friendly",
    "自然": "Nature", "美食": "Food", "演出": "Show", "海滨": "Seaside", "城市": "City", "城市风光": "City Views",
    "国家级": "National", "世界遗产": "World Heritage", "地标": "Landmark",
    "寺庙道观": "Temple", "公园广场": "Park", "运动健身": "Sports", "购物": "Shopping",
    "休闲娱乐": "Leisure", "文化": "Culture", "艺术": "Art", "宗教": "Religious Site",
    "瀑布湖泊": "Waterfall & Lake", "峡谷洞穴": "Canyon & Cave", "山峰": "Peak",
    "河流": "River", "滑雪场": "Ski Resort", "高尔夫": "Golf", "剧院": "Theater",
    "古村": "Ancient Village", "城市公园": "City Park", "森林": "Forest", "湖泊": "Lake",
    "山岳": "Mountain", "园林": "Garden", "湿地": "Wetland", "水族馆": "Aquarium",
    "展览馆": "Exhibition Hall", "体育场馆": "Sports Venue", "商业街": "Shopping Street",
    "度假": "Resort", "主题乐园": "Theme Park", "游乐园": "Amusement Park",
    "名胜古迹": "Scenic Heritage", "文化遗址": "Cultural Heritage", "革命遗址": "Revolutionary Site",
    "寺庙道观": "Temple", "道观": "Taoist Temple", "清真寺": "Mosque", "教堂": "Church",
    "步行街": "Pedestrian Street", "观景台": "Viewpoint", "夜景": "Night View",
    "演出场馆": "Performance Venue", "体育馆": "Gymnasium", "博物馆": "Museum",
}

LEVEL_EN = {"5A": "5A", "4A": "4A", "3A": "3A", "2A": "2A"}

HOTEL_LEVEL_EN = {
    "经济型": "Economy", "快捷": "Budget", "舒适型": "Comfort", "高档型": "Upscale",
    "豪华型": "Luxury", "三星级": "3-star", "四星级": "4-star", "五星级": "5-star",
    "客栈": "Guesthouse", "青年旅舍": "Hostel", "公寓": "Apartment", "民宿": "Homestay",
}

SOURCE_ZH = {
    "Baidu Maps": "百度地图",
    "Baidu Maps · ticket": "百度地图 · 景区票价",
    "Qunar (via Baidu Maps)": "去哪儿（经百度地图）",
    "Ctrip (via Baidu Maps)": "携程（经百度地图）",
    "Meituan (via Baidu Maps)": "美团（经百度地图）",
    "Tongcheng (via Baidu Maps)": "同程（经百度地图）",
    "Elong (via Baidu Maps)": "艺龙（经百度地图）",
    "List price": "门市原价",
    "Live fetch": "实时抓取",
}

SOURCE_EN = {
    "百度地图": "Baidu Maps",
    "百度地图 · 景区票价": "Baidu Maps · ticket",
    "去哪儿（百度地图聚合）": "Qunar (via Baidu Maps)",
    "携程（百度地图聚合）": "Ctrip (via Baidu Maps)",
    "美团（百度地图聚合）": "Meituan (via Baidu Maps)",
    "同程（百度地图聚合）": "Tongcheng (via Baidu Maps)",
    "艺龙（百度地图聚合）": "Elong (via Baidu Maps)",
    "门市原价": "List price",
    "实时抓取": "Live fetch",
}


def hotel_level(name: str) -> str:
    text = str(name or "").strip()
    if not text:
        return ""
    for key, value in HOTEL_LEVEL_EN.items():
        if key in text:
            return value
    return text


ROOM_TOKENS = (
    ("不可取消", "Non-refundable"), ("免费取消", "Free cancellation"),
    ("限时取消", "Limited-time cancellation"), ("无早", "Room only"),
    ("单早", "1 breakfast"), ("双早", "2 breakfasts"), ("三早", "3 breakfasts"),
    ("大床", "King bed"), ("特大床", "Extra-large bed"), ("双床", "Twin beds"),
    ("单人床", "Single bed"), ("标准间", "Standard room"), ("大床房", "King room"),
    ("双床房", "Twin room"), ("家庭房", "Family room"), ("经济房", "Economy room"),
    ("高级", "Superior"), ("豪华", "Deluxe"), ("商务", "Business"), ("行政", "Executive"),
    ("单人间", "Single room"), ("双人间", "Double room"), ("三人间", "Triple room"),
    ("标准间", "Standard room"), ("大床房", "King room"), ("双床房", "Twin room"),
    ("家庭房", "Family room"), ("亲子房", "Family room"), ("套房", "Suite"),
    ("标间", "Standard room"), ("㎡", "m²"),
    ("公共卫浴", "shared bathroom"), ("独立卫浴", "private bathroom"),
)


OPEN_TOKENS = (
    ("周一至周日", "Mon–Sun"), ("周一至周五", "Mon–Fri"), ("周六至周日", "Sat–Sun"),
    ("周一", "Mon"), ("周二", "Tue"), ("周三", "Wed"), ("周四", "Thu"),
    ("周五", "Fri"), ("周六", "Sat"), ("周日", "Sun"),
    ("一月至十二月", "Jan–Dec"), ("开放时间", "Hours"), ("全天", "All day"),
    ("全年", "Year-round"), ("淡季", "Low season"), ("旺季", "Peak season"),
)


def open_time(text: str) -> str:
    value = str(text or "")
    for zh, en in OPEN_TOKENS:
        value = value.replace(zh, en)
    return value


def room_text(text: str) -> str:
    import re
    value = str(text or "")
    for zh, en in sorted(ROOM_TOKENS, key=lambda pair: -len(pair[0])):
        value = value.replace(zh, en)
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    return re.sub(r"\s{2,}", " ", value).strip()


NOTE_EN = (
    ("实时数据", "Live data"), ("每晚起", "per night from"), ("在线参考价", "online reference"),
    ("门市价", "list price"), ("景区门市价", "venue list price"), ("酒店门市价", "hotel list price"),
    ("可预订", "Bookable"), ("已售完", "Sold out"), ("标准房", "Standard room"),
    ("票种", "Ticket type"), ("房型", "Room type"), ("说明", "Notes"), ("门票", "Ticket"),
    ("自助早餐", "Buffet breakfast"), ("含早", "Breakfast included"), ("不含早", "No breakfast"),
)


def note_en(text: str) -> str:
    """把报价/票种说明里的常见中文短语换成英文（用于英文界面）。"""
    value = room_text(str(text or ""))
    for zh, en in sorted(NOTE_EN, key=lambda pair: -len(pair[0])):
        value = value.replace(zh, en)
    value = re.sub(r"(\d+(?:\.\d+)?)\s*元", lambda m: "CNY " + m.group(1), value)
    return re.sub(r"\s{2,}", " ", value).strip()


ROOM_TOKENS_REV = tuple((en, zh) for zh, en in ROOM_TOKENS)


def room_text_zh(text: str) -> str:
    """把英文房型说明尽量还原成中文（用于旧快照缺失中文原文时）。"""
    import re
    value = str(text or "")
    if not value:
        return ""
    if any("一" <= ch <= "鿿" for ch in value):
        return value
    for en, zh in sorted(ROOM_TOKENS_REV, key=lambda pair: -len(pair[0])):
        value = re.sub(re.escape(en), zh, value, flags=re.IGNORECASE)
    value = value.replace("m²", "㎡").replace("Mon-Sun", "周一至周日")
    return re.sub(r"\s{2,}", " ", value).strip()


def source(name: str) -> str:
    text = str(name or "").strip()
    if not text:
        return ""
    if text in SOURCE_EN:
        return SOURCE_EN[text]
    for key, value in SOURCE_EN.items():
        if key and key in text:
            return text.replace(key, value)
    return text


def source_zh(name: str) -> str:
    """把英文来源名还原成中文（中文界面用）。"""
    text = str(name or "").strip()
    if not text:
        return ""
    if text in SOURCE_ZH:
        return SOURCE_ZH[text]
    for key, value in SOURCE_ZH.items():
        if key and key in text:
            return text.replace(key, value)
    return text


def city(name: str) -> str:
    if not name:
        return ""
    text = str(name).strip()
    if text in CITY_EN:
        return CITY_EN[text]
    if text.endswith("市") and text[:-1] in CITY_EN:
        return CITY_EN[text[:-1]]
    return text


def tag(name: str) -> str:
    text = str(name or "").strip()
    if text in TAG_EN:
        return TAG_EN[text]
    for suffix in ("风景区", "景区", "公园"):
        if text.endswith(suffix) and text[:-len(suffix)] in TAG_EN:
            return TAG_EN[text[:-len(suffix)]] + " " + suffix.replace("风景区", "Scenic Area").replace("景区", "Scenic Area").replace("公园", "Park")
    return text


def tags(values: Iterable[str]) -> List[str]:
    return [tag(v) for v in (values or []) if str(v).strip()]