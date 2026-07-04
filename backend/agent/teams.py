"""48 支参赛队静态元数据。

- code: FIFA 三字码（与 Wikipedia 模板一致，作为全项目主键）
- name_en: 英文名（用于匹配 eloratings.net 队名，含别名）
- name_zh: 中文名（前端展示）
- fifa_rank: FIFA 排名静态快照（2025-12，微调项，权重低）
"""

TEAMS = {
    # Group A
    "MEX": {"name_en": "Mexico", "name_zh": "墨西哥", "group": "A", "fifa_rank": 14},
    "RSA": {"name_en": "South Africa", "name_zh": "南非", "group": "A", "fifa_rank": 55},
    "KOR": {"name_en": "South Korea", "name_zh": "韩国", "group": "A", "fifa_rank": 23},
    "CZE": {"name_en": "Czech Republic", "name_zh": "捷克", "group": "A", "fifa_rank": 42},
    # Group B
    "SUI": {"name_en": "Switzerland", "name_zh": "瑞士", "group": "B", "fifa_rank": 17},
    "CAN": {"name_en": "Canada", "name_zh": "加拿大", "group": "B", "fifa_rank": 28},
    "BIH": {"name_en": "Bosnia and Herzegovina", "name_zh": "波黑", "group": "B", "fifa_rank": 68},
    "QAT": {"name_en": "Qatar", "name_zh": "卡塔尔", "group": "B", "fifa_rank": 51},
    # Group C
    "BRA": {"name_en": "Brazil", "name_zh": "巴西", "group": "C", "fifa_rank": 5},
    "MAR": {"name_en": "Morocco", "name_zh": "摩洛哥", "group": "C", "fifa_rank": 11},
    "SCO": {"name_en": "Scotland", "name_zh": "苏格兰", "group": "C", "fifa_rank": 38},
    "HAI": {"name_en": "Haiti", "name_zh": "海地", "group": "C", "fifa_rank": 84},
    # Group D
    "USA": {"name_en": "United States", "name_zh": "美国", "group": "D", "fifa_rank": 15},
    "AUS": {"name_en": "Australia", "name_zh": "澳大利亚", "group": "D", "fifa_rank": 26},
    "PAR": {"name_en": "Paraguay", "name_zh": "巴拉圭", "group": "D", "fifa_rank": 39},
    "TUR": {"name_en": "Turkey", "name_zh": "土耳其", "group": "D", "fifa_rank": 27},
    # Group E
    "GER": {"name_en": "Germany", "name_zh": "德国", "group": "E", "fifa_rank": 9},
    "CIV": {"name_en": "Ivory Coast", "name_zh": "科特迪瓦", "group": "E", "fifa_rank": 41},
    "ECU": {"name_en": "Ecuador", "name_zh": "厄瓜多尔", "group": "E", "fifa_rank": 24},
    "CUW": {"name_en": "Curacao", "name_zh": "库拉索", "group": "E", "fifa_rank": 82},
    # Group F
    "NED": {"name_en": "Netherlands", "name_zh": "荷兰", "group": "F", "fifa_rank": 7},
    "JPN": {"name_en": "Japan", "name_zh": "日本", "group": "F", "fifa_rank": 18},
    "SWE": {"name_en": "Sweden", "name_zh": "瑞典", "group": "F", "fifa_rank": 43},
    "TUN": {"name_en": "Tunisia", "name_zh": "突尼斯", "group": "F", "fifa_rank": 46},
    # Group G
    "BEL": {"name_en": "Belgium", "name_zh": "比利时", "group": "G", "fifa_rank": 8},
    "EGY": {"name_en": "Egypt", "name_zh": "埃及", "group": "G", "fifa_rank": 32},
    "IRN": {"name_en": "Iran", "name_zh": "伊朗", "group": "G", "fifa_rank": 21},
    "NZL": {"name_en": "New Zealand", "name_zh": "新西兰", "group": "G", "fifa_rank": 86},
    # Group H
    "ESP": {"name_en": "Spain", "name_zh": "西班牙", "group": "H", "fifa_rank": 1},
    "CPV": {"name_en": "Cape Verde", "name_zh": "佛得角", "group": "H", "fifa_rank": 70},
    "URU": {"name_en": "Uruguay", "name_zh": "乌拉圭", "group": "H", "fifa_rank": 12},
    "KSA": {"name_en": "Saudi Arabia", "name_zh": "沙特阿拉伯", "group": "H", "fifa_rank": 60},
    # Group I
    "FRA": {"name_en": "France", "name_zh": "法国", "group": "I", "fifa_rank": 3},
    "NOR": {"name_en": "Norway", "name_zh": "挪威", "group": "I", "fifa_rank": 29},
    "SEN": {"name_en": "Senegal", "name_zh": "塞内加尔", "group": "I", "fifa_rank": 19},
    "IRQ": {"name_en": "Iraq", "name_zh": "伊拉克", "group": "I", "fifa_rank": 58},
    # Group J
    "ARG": {"name_en": "Argentina", "name_zh": "阿根廷", "group": "J", "fifa_rank": 2},
    "AUT": {"name_en": "Austria", "name_zh": "奥地利", "group": "J", "fifa_rank": 22},
    "ALG": {"name_en": "Algeria", "name_zh": "阿尔及利亚", "group": "J", "fifa_rank": 35},
    "JOR": {"name_en": "Jordan", "name_zh": "约旦", "group": "J", "fifa_rank": 64},
    # Group K
    "COL": {"name_en": "Colombia", "name_zh": "哥伦比亚", "group": "K", "fifa_rank": 13},
    "POR": {"name_en": "Portugal", "name_zh": "葡萄牙", "group": "K", "fifa_rank": 6},
    "COD": {"name_en": "DR Congo", "name_zh": "民主刚果", "group": "K", "fifa_rank": 56},
    "UZB": {"name_en": "Uzbekistan", "name_zh": "乌兹别克斯坦", "group": "K", "fifa_rank": 54},
    # Group L
    "ENG": {"name_en": "England", "name_zh": "英格兰", "group": "L", "fifa_rank": 4},
    "CRO": {"name_en": "Croatia", "name_zh": "克罗地亚", "group": "L", "fifa_rank": 10},
    "GHA": {"name_en": "Ghana", "name_zh": "加纳", "group": "L", "fifa_rank": 73},
    "PAN": {"name_en": "Panama", "name_zh": "巴拿马", "group": "L", "fifa_rank": 33},
}

GROUP_ORDER = "ABCDEFGHIJKL"
