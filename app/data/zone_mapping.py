"""Zone 可用区完整信息（从边缘计算可用区推荐表 + 07文档提取）。

提供：
- ZONE_IDC_MAPPING: 节点→机房管理单元映射
- ZONE_INFO: 节点完整信息（region/城市/运营商/架构/状态/机型/来源ECM）
"""

# TEZ 节点完整信息
ZONE_INFO: list[dict] = [
    # ─── 华北（Region: 北京）───
    {"zone": "北京边缘一区（电信）", "city": "北京", "isp": "电信", "idc": "北京电信兆维EIC1-30G-V", "arch": "10G", "region": "北京", "status": "已开区", "models": "S5nt、IT5c", "ipv6": True, "ecm_source": "北京八区"},
    {"zone": "北京边缘二区（移动）", "city": "北京", "isp": "移动", "idc": "北京移动信息港EIC1-30G-V", "arch": "10G", "region": "北京", "status": "已开区", "models": "S5nt、IT5c", "ipv6": False, "ecm_source": "北京六区"},
    {"zone": "石家庄边缘二区", "city": "石家庄", "isp": "三通", "idc": "石家庄电信纺织基地OC3-160G-MY", "arch": "25G", "region": "北京", "status": "已开区", "models": "SN3ne、IT5、BMD3c/3s", "ipv6": True, "ecm_source": "石家庄四区"},
    {"zone": "太原边缘二区（移动）", "city": "太原", "isp": "移动", "idc": "太原移动泽信街EIC1-30G-V", "arch": "10G", "region": "北京", "status": "已开区", "models": "S5nt、IT5c", "ipv6": False, "ecm_source": "太原四区"},
    {"zone": "天津边缘一区（电信）", "city": "天津", "isp": "电信", "idc": "天津电信广兴路EIC1-30G-V", "arch": "10G", "region": "北京", "status": "已开区", "models": "S5nt、IT5c", "ipv6": False, "ecm_source": "天津三区"},
    {"zone": "天津边缘二区（移动）", "city": "天津", "isp": "移动", "idc": "天津移动工业园EIC1-30G-V", "arch": "10G", "region": "北京", "status": "开区中", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": "天津四区"},
    {"zone": "天津边缘三区（联通）", "city": "天津", "isp": "联通", "idc": "天津联通空港EIC1-30G-V", "arch": "10G", "region": "北京", "status": "开区中", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": "天津二区"},
    {"zone": "呼和浩特边缘三区（联通）", "city": "呼和浩特", "isp": "联通", "idc": "呼和浩特联通金川开发区EIC1-30G-V", "arch": "10G", "region": "北京", "status": "开区中", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": "呼和浩特二区"},
    {"zone": "呼和浩特边缘二区（移动）", "city": "呼和浩特", "isp": "移动", "idc": "呼和浩特移动和林格尔县EIC1-30G-V", "arch": "10G", "region": "北京", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": "呼和浩特三区"},
    # ─── 东北（Region: 北京）───
    {"zone": "沈阳边缘二区（电信）", "city": "沈阳", "isp": "电信", "idc": "沈阳电信开发区EIC1-30G-V", "arch": "10G", "region": "北京", "status": "已开区", "models": "S5nt、IT5c", "ipv6": True, "ecm_source": "TEZ新建"},
    {"zone": "沈阳边缘一区", "city": "沈阳", "isp": "三通", "idc": "沈阳联通云鼎OC2-160G-MY", "arch": "10G", "region": "北京", "status": "已开区", "models": "S5nt、IT5c", "ipv6": True, "ecm_source": "沈阳四区"},
    {"zone": "哈尔滨边缘一区", "city": "哈尔滨", "isp": "三通", "idc": "哈尔滨联通南岗EIC3-160G-MY", "arch": "25G", "region": "北京", "status": "已开区", "models": "SN3ne、IT5、BMD3c/3s", "ipv6": True, "ecm_source": "字节独占"},
    # ─── 华东（Region: 上海）───
    {"zone": "济南边缘一区", "city": "济南", "isp": "三通", "idc": "济南移动孙村OC16-160G-MY", "arch": "25G", "region": "上海", "status": "已开区", "models": "SN3ne、IT5、BMD3c/3s", "ipv6": True, "ecm_source": "济南五区"},
    {"zone": "济南边缘三区（联通）", "city": "济南", "isp": "联通", "idc": "济南联通担山屯EIC1-30G-V", "arch": "10G", "region": "上海", "status": "已开区", "models": "S5nt、IT5c", "ipv6": True, "ecm_source": "济南二区"},
    {"zone": "南昌边缘一区", "city": "南昌", "isp": "三通", "idc": "南昌电信孺子路OC2-160G-MY", "arch": "10G", "region": "上海", "status": "已开区", "models": "S5nt、IT5c", "ipv6": True, "ecm_source": "南昌六区"},
    {"zone": "南昌边缘三区（联通）", "city": "南昌", "isp": "联通", "idc": "南昌联通新建区EIC1-30G-V", "arch": "10G", "region": "上海", "status": "待启动", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": "南昌四区"},
    {"zone": "无锡边缘一区", "city": "无锡", "isp": "三通", "idc": "无锡移动健康路OC5-160G-MV", "arch": "10G", "region": "上海", "status": "已下线", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": "无锡一区"},
    {"zone": "无锡边缘二区", "city": "无锡", "isp": "三通", "idc": "无锡电信净慧东道OC1-160G-MY", "arch": "25G", "region": "上海", "status": "已开区", "models": "SN3ne、IT5、BMD3c/3s", "ipv6": False, "ecm_source": "无锡二区"},
    {"zone": "上海边缘三区（联通）", "city": "上海", "isp": "联通", "idc": "上海联通周浦EIC1-30G-V", "arch": "10G", "region": "上海", "status": "开区中", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "南京边缘一区（电信）", "city": "南京", "isp": "电信", "idc": "南京电信吉山EIC1-30G-V", "arch": "10G", "region": "上海", "status": "已开区", "models": "S5nt、IT5c", "ipv6": True, "ecm_source": "南京三区"},
    {"zone": "南京边缘二区（移动）", "city": "南京", "isp": "移动", "idc": "南京移动学府EIC1-30G-V", "arch": "10G", "region": "上海", "status": "已开区", "models": "S5nt、IT5c", "ipv6": True, "ecm_source": "南京二区"},
    {"zone": "常州边缘一区（电信）", "city": "常州", "isp": "电信", "idc": "常州电信锦绣路EIC1-60G-V", "arch": "25G", "region": "上海", "status": "已开区", "models": "SN3ne、IT5、BMD3c/3s", "ipv6": True, "ecm_source": "TEZ新建"},
    {"zone": "宁波边缘一区", "city": "宁波", "isp": "三通", "idc": "宁波电信镇海OC13-160G-MY", "arch": "25G", "region": "上海", "status": "已开区", "models": "SN3ne、IT5、BMD3c/3s", "ipv6": True, "ecm_source": "宁波六区"},
    {"zone": "宁波边缘二区（移动）", "city": "宁波", "isp": "移动", "idc": "宁波移动鄞州区EIC2-30G-V", "arch": "10G", "region": "上海", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "宁波边缘三区（电信）", "city": "宁波", "isp": "电信", "idc": "宁波电信镇海EIC1-30G-V", "arch": "10G", "region": "上海", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "金华边缘一区（电信）", "city": "金华", "isp": "电信", "idc": "金华电信婺城区EIC1-60G-V", "arch": "25G", "region": "上海", "status": "已开区", "models": "SN3ne、IT5、BMD3c/3s", "ipv6": None, "ecm_source": ""},
    {"zone": "合肥边缘一区", "city": "合肥", "isp": "三通", "idc": "合肥电信繁华大道OC3-160G-MY", "arch": "10G", "region": "上海", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "蚌埠边缘一区（电信）", "city": "蚌埠", "isp": "电信", "idc": "蚌埠电信胜利东路EIC1-60G-V", "arch": "25G", "region": "上海", "status": "已开区", "models": "SN3ne、IT5、BMD3c/3s", "ipv6": None, "ecm_source": "小鹿独占"},
    {"zone": "池州边缘一区（电信）", "city": "池州", "isp": "电信", "idc": "池州电信长江路EIC1-60G-V", "arch": "25G", "region": "上海", "status": "已开区", "models": "SN3ne、IT5、BMD3c/3s", "ipv6": None, "ecm_source": "小鹿独占"},
    {"zone": "福州边缘一区", "city": "福州", "isp": "三通", "idc": "福州电信信息园EIC3-160G-MU", "arch": "25G", "region": "上海", "status": "已开区", "models": "SN3ne、IT5、BMD3c/3s", "ipv6": None, "ecm_source": "福州一区"},
    # ─── 华中（Region: 广州）───
    {"zone": "郑州边缘一区", "city": "郑州", "isp": "三通", "idc": "郑州联通高新区OC30-160G-MV", "arch": "10G", "region": "广州", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": "郑州三区"},
    {"zone": "郑州边缘三区（联通）", "city": "郑州", "isp": "联通", "idc": "郑州联通高新区EIC1-30G-V", "arch": "10G", "region": "广州", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": "郑州二区"},
    {"zone": "武汉边缘一区", "city": "武汉", "isp": "三通", "idc": "武汉电信火凤凰OC3-160G-MU", "arch": "10G", "region": "广州", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": "武汉五区"},
    {"zone": "武汉边缘三区（联通）", "city": "武汉", "isp": "联通", "idc": "武汉联通科技城EIC1-30G-V", "arch": "10G", "region": "广州", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "长沙边缘一区", "city": "长沙", "isp": "三通", "idc": "长沙电信望城区OC6-160G-MY", "arch": "10G", "region": "广州", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": "长沙二区"},
    # ─── 华南（Region: 广州）───
    {"zone": "广州边缘二区（联通）", "city": "广州", "isp": "联通", "idc": "广州联通龙荣路EIC1-30G-V", "arch": "10G", "region": "广州", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "广州边缘三区（电信）", "city": "广州", "isp": "电信", "idc": "广州电信东涌EIC1-30G-V", "arch": "10G", "region": "广州", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "广州边缘四区（移动）", "city": "广州", "isp": "移动", "idc": "广州移动旗锐EIC1-60G-V", "arch": "25G", "region": "广州", "status": "已开区", "models": "SN3ne、IT5、BMD3c/3s", "ipv6": None, "ecm_source": ""},
    {"zone": "广州边缘六区（移动）", "city": "广州", "isp": "移动", "idc": "广州移动南基EIC1-30G-V", "arch": "10G", "region": "广州", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "东莞边缘一区", "city": "东莞", "isp": "三通", "idc": "东莞移动志享OC7-160G-MU", "arch": "10G", "region": "广州", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": "东莞四区"},
    {"zone": "海口边缘二区（移动）", "city": "海口", "isp": "移动", "idc": "海口移动南一环路EIC1-30G-V", "arch": "10G", "region": "广州", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "南宁边缘一区（电信）", "city": "南宁", "isp": "电信", "idc": "南宁电信朋云路EIC1-30G-V", "arch": "10G", "region": "广州", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "南宁边缘二区（移动）", "city": "南宁", "isp": "移动", "idc": "南宁移动罗赖路EIC1-30G-V", "arch": "10G", "region": "广州", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "南宁边缘三区（联通）", "city": "南宁", "isp": "联通", "idc": "南宁联通五象EIC1-30G-V", "arch": "10G", "region": "广州", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    # ─── 西南（Region: 成都）───
    {"zone": "成都边缘一区（联通）", "city": "成都", "isp": "联通", "idc": "成都联通天府EIC1-30G-V", "arch": "10G", "region": "成都", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "成都边缘二区（移动）", "city": "成都", "isp": "移动", "idc": "成都移动西云EIC1-30G-V", "arch": "10G", "region": "成都", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "成都边缘三区（电信）", "city": "成都", "isp": "电信", "idc": "成都电信西区EIC1-30G-V", "arch": "10G", "region": "成都", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "重庆边缘一区", "city": "重庆", "isp": "三通", "idc": "重庆移动水土OC13-160G-MV", "arch": "10G", "region": "成都", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "重庆边缘二区（联通）", "city": "重庆", "isp": "联通", "idc": "重庆联通云福路EIC5-60G-V电信", "arch": "25G", "region": "成都", "status": "已开区", "models": "SN3ne、IT5、BMD3c/3s", "ipv6": None, "ecm_source": ""},
    {"zone": "贵阳边缘二区（电信）", "city": "贵阳", "isp": "电信", "idc": "贵阳电信黔中大道EIC1-30G-V", "arch": "10G", "region": "成都", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "昆明边缘一区（电信）", "city": "昆明", "isp": "电信", "idc": "昆明电信经开EIC1-30G-V", "arch": "10G", "region": "成都", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "昆明边缘二区（移动）", "city": "昆明", "isp": "移动", "idc": "昆明移动龙泉EIC1-30G-V", "arch": "10G", "region": "成都", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "昆明边缘三区（联通）", "city": "昆明", "isp": "联通", "idc": "昆明联通大屯路EIC1-30G-V", "arch": "10G", "region": "成都", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    # ─── 西北（Region: 北京）───
    {"zone": "西安边缘一区", "city": "西安", "isp": "三通", "idc": "西安电信咸新区OC3-160G-MY", "arch": "10G", "region": "北京", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "银川边缘二区（移动）", "city": "银川", "isp": "移动", "idc": "银川移动开发区EIC1-30G-V", "arch": "10G", "region": "北京", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "中卫边缘一区", "city": "中卫", "isp": "三通", "idc": "中卫联通沙坡头区EIC3-20G-ECM", "arch": "10G", "region": "北京", "status": "已开区", "models": "S5nt、IT5c", "ipv6": None, "ecm_source": ""},
    {"zone": "中卫边缘二区（移动）", "city": "中卫", "isp": "移动", "idc": "中卫移动云基地EIC1-60G-V联通", "arch": "25G", "region": "北京", "status": "已开区", "models": "SN3ne、IT5、BMD3c/3s", "ipv6": None, "ecm_source": ""},
]

# 快速查找映射（兼容旧接口）
ZONE_IDC_MAPPING: dict[str, str] = {item["zone"]: item["idc"] for item in ZONE_INFO}

# zone → 完整信息
ZONE_DETAIL_MAP: dict[str, dict] = {item["zone"]: item for item in ZONE_INFO}

# 星云地域映射（从星云平台截图整理）
NEBULA_REGION_MAP: dict[str, str] = {
    # 华北地区(北京)
    "沈阳边缘一区": "华北地区(北京)",
    "石家庄边缘二区": "华北地区(北京)",
    "沈阳边缘二区（电信）": "华北地区(北京)",
    "哈尔滨边缘一区": "华北地区(北京)",
    "太原边缘二区（移动）": "华北地区(北京)",
    "北京边缘一区（电信）": "华北地区(北京)",
    "北京边缘二区（移动）": "华北地区(北京)",
    "天津边缘一区（电信）": "华北地区(北京)",
    # 华东地区(上海)
    "济南边缘一区": "华东地区(上海)",
    "南昌边缘一区": "华东地区(上海)",
    "宁波边缘一区": "华东地区(上海)",
    "合肥边缘一区": "华东地区(上海)",
    "无锡边缘二区": "华东地区(上海)",
    "宁波边缘二区（移动）": "华东地区(上海)",
    "池州边缘一区（电信）": "华东地区(上海)",
    "常州边缘一区（电信）": "华东地区(上海)",
    "金华边缘一区（电信）": "华东地区(上海)",
    "蚌埠边缘一区（电信）": "华东地区(上海)",
    "福州边缘一区": "华东地区(上海)",
    "济南边缘三区（联通）": "华东地区(上海)",
    "南京边缘一区（电信）": "华东地区(上海)",
    "上海边缘三区（联通）": "华东地区(上海)",
    "南京边缘二区（移动）": "华东地区(上海)",
    "宁波边缘三区（电信）": "华东地区(上海)",
    # 华南地区(广州)
    "武汉边缘一区": "华南地区(广州)",
    "长沙边缘一区": "华南地区(广州)",
    "东莞边缘一区": "华南地区(广州)",
    "郑州边缘一区": "华南地区(广州)",
    "广州边缘二区（联通）": "华南地区(广州)",
    "南宁边缘一区（电信）": "华南地区(广州)",
    "南宁边缘二区（移动）": "华南地区(广州)",
    "南宁边缘三区（联通）": "华南地区(广州)",
    "广州边缘三区（电信）": "华南地区(广州)",
    "广州边缘四区（移动）": "华南地区(广州)",
    "郑州边缘三区（联通）": "华南地区(广州)",
    "广州边缘六区（移动）": "华南地区(广州)",
    "武汉边缘三区（联通）": "华南地区(广州)",
    "海口边缘二区（移动）": "华南地区(广州)",
    # 西南地区(成都)
    "昆明边缘一区（电信）": "西南地区(成都)",
    "昆明边缘二区（移动）": "西南地区(成都)",
    "中卫边缘一区": "西南地区(成都)",
    "贵阳边缘二区（电信）": "西南地区(成都)",
    "成都边缘三区（电信）": "西南地区(成都)",
    "重庆边缘二区（联通）": "西南地区(成都)",
}

# 把 nebula_region 补充到 ZONE_INFO 中
for item in ZONE_INFO:
    item["nebula_region"] = NEBULA_REGION_MAP.get(item["zone"], "")

# 重建 ZONE_DETAIL_MAP（含 nebula_region）
ZONE_DETAIL_MAP = {item["zone"]: item for item in ZONE_INFO}
