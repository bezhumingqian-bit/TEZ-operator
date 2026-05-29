"""运维助手 SOP 流程数据。

每个场景包含分步操作指南，关联接口人、平台链接、工单类型。
数据来源：08-资源运营SOP.md + 09-交接清单与权限.md
"""

SOP_FLOWS = [
    {
        "id": "host_fault",
        "title": "母机故障",
        "icon": "🔧",
        "desc": "母机故障排查、上报、处理全流程",
        "steps": [
            {
                "title": "确认故障现象",
                "desc": "登录灯塔/OBS查看告警类型，确认影响范围（子机数量、客户）",
                "links": [{"name": "灯塔告警", "url": "https://obs.woa.com"}],
            },
            {
                "title": "联系值班运维",
                "desc": "通知机房现场确认硬件状态",
                "contacts": ["sagelxxzhao", "cecixxzhang"],
            },
            {
                "title": "提交维修工单",
                "desc": "在工单系统提交维修单，自动通知接口人",
                "action": {"type": "create_order", "order_type": "repair", "label": "提交维修工单"},
            },
            {
                "title": "跟进处理",
                "desc": "硬件故障→联系机房更换；软件故障→重启/重装",
                "links": [
                    {"name": "QFlow报修", "url": "#"},
                    {"name": "ECM重装", "url": "#"},
                ],
                "tips": ["30分钟内未响应 → 升级到 TL", "有 TPC 的机器不能直接重装"],
            },
        ],
    },
    {
        "id": "migration",
        "title": "搬迁服务器",
        "icon": "🚚",
        "desc": "服务器搬迁全流程（出入库→提单→模块转移）",
        "steps": [
            {
                "title": "确认搬迁需求",
                "desc": "明确来源可用区、目标可用区、设备数量和型号",
                "tips": ["确认目标机位 sideband 属性为'否'", "裸金属搬迁需提前修改属性（1天）"],
            },
            {
                "title": "检查前置条件",
                "desc": "确认设备可搬迁状态",
                "tips": ["投放前要清 .backup", "确认 TPC（无TPC无法重装）", "确认模块路径正确"],
                "links": [{"name": "数全通-机位", "url": "#"}],
            },
            {
                "title": "提交搬迁工单",
                "desc": "填写搬迁单，系统自动同步到OnePage搬迁记录",
                "action": {"type": "create_order", "order_type": "migration", "label": "提交搬迁工单"},
            },
            {
                "title": "转移模块",
                "desc": "在搬迁投放维修群让 v_xiaoxyli 转移模块到 TEZ 待上线路径",
                "contacts": ["v_xiaoxyli"],
                "tips": ["目标模块：[N][腾讯云边缘可用区]-[公有云]-[TEZ]-[线下资源][待上线]"],
            },
            {
                "title": "验收",
                "desc": "搬迁完成后确认设备上线状态，更新工单为已完成",
                "links": [{"name": "TCUM查状态", "url": "#"}],
            },
        ],
    },
    {
        "id": "host_deploy",
        "title": "投放母机",
        "icon": "📦",
        "desc": "母机投放上线全流程",
        "steps": [
            {
                "title": "确认投放需求",
                "desc": "明确需求类型（TEZ/ECM）、设备型号、目标可用区",
                "tips": ["确认目标机房有空闲机位"],
            },
            {
                "title": "检查前置条件",
                "desc": "TPC确认、.backup清理、模块路径确认",
                "tips": ["无 TPC 无法重装", "投放前必须清 .backup", "确认机型与目标区域兼容"],
            },
            {
                "title": "提交投放工单",
                "desc": "填写投放单，自动同步到OnePage投放记录",
                "action": {"type": "create_order", "order_type": "host_deploy", "label": "提交投放工单"},
            },
            {
                "title": "重装系统",
                "desc": "根据需要选择是否重装（TEZ需安装tlinux2.2-kvm3.0）",
                "links": [{"name": "ECM重装", "url": "#"}],
            },
            {
                "title": "模块转移 + 上线",
                "desc": "模块转到TEZ待上线 → 上线中 → 现网运营",
                "contacts": ["v_xiaoxyli"],
            },
        ],
    },
    {
        "id": "find_machine",
        "title": "要机器",
        "icon": "🖥️",
        "desc": "找空闲机器/查库存",
        "steps": [
            {
                "title": "查看库存概况",
                "desc": "在本系统「资源查询→节点资源概况」查看各区域空闲机位",
                "action": {"type": "navigate", "path": "/hosts", "label": "查看资源概况"},
            },
            {
                "title": "云霄平台查空闲",
                "desc": "登录云霄查看具体机型的空闲数量",
                "links": [{"name": "云霄平台", "url": "#"}],
            },
            {
                "title": "确认机型可用性",
                "desc": "TEZ主要机型：S5nt(CG3-10G)、SN3ne(MI52-25G)、IT5(MI52-25G)",
                "tips": ["25G机型：S5、IT5、IT3", "10G机型：S5nt", "不充足：IT5C、裸金属"],
            },
            {
                "title": "联系资源运营",
                "desc": "如需预留或调配，联系资源运营接口人",
                "contacts": ["nalexzhao"],
            },
        ],
    },
    {
        "id": "open_zone",
        "title": "开新区",
        "icon": "🌐",
        "desc": "可用区开区全流程",
        "steps": [
            {
                "title": "需求确认",
                "desc": "确认开区需求（客户/区域/机型/数量）",
                "tips": ["需要提前 1.5 个月启动", "确认机房是否有空闲机位"],
            },
            {
                "title": "机位扩容评估",
                "desc": "如果机位不足，启动扩容流程",
                "links": [{"name": "QFlow开区", "url": "#"}],
            },
            {
                "title": "地域系统上线",
                "desc": "在地域系统中创建可用区配置",
                "links": [{"name": "地域系统", "url": "#"}],
            },
            {
                "title": "QCC机型配置",
                "desc": "配置可用区支持的机型",
                "links": [{"name": "QCC", "url": "#"}],
            },
            {
                "title": "野鹤开白",
                "desc": "在野鹤系统为可用区+APPID开白名单",
                "links": [{"name": "野鹤系统", "url": "#"}],
            },
        ],
    },
    {
        "id": "ipv6",
        "title": "IPv6",
        "icon": "🔀",
        "desc": "IPv6 支持评估与实施",
        "steps": [
            {
                "title": "评估母机支持",
                "desc": "确认目标母机是否支持 IPv6（内核/网卡）",
            },
            {
                "title": "VPC 适配",
                "desc": "确认 VPC 网络是否已开启 IPv6",
                "contacts": ["网平接口人"],
            },
            {
                "title": "网平实施",
                "desc": "联系网平团队进行 IPv6 网络配置",
                "tips": ["需要网平侧配合，排期约 1-2 周"],
            },
        ],
    },
    {
        "id": "cost",
        "title": "成本/报价",
        "icon": "💰",
        "desc": "机型成本查询与报价规则",
        "steps": [
            {
                "title": "查看机型成本",
                "desc": "在本系统「成本一览」查看各机型月度成本",
                "action": {"type": "navigate", "path": "/cost", "label": "查看成本表"},
            },
            {
                "title": "报价规则",
                "desc": "九部单独报价，其他人报刊例价。低价底价2折起。",
                "tips": ["大客户报价需单独沟通", "竞价场景看成本比例-竞价列"],
            },
            {
                "title": "月度调账",
                "desc": "多个大客户需要月度调账（ECM导出对齐+手工调整）",
                "tips": ["多个大客户需月度调账（具体清单见运营SOP）"],
            },
        ],
    },
    {
        "id": "machine_transform",
        "title": "机型改造",
        "icon": "⚙️",
        "desc": "机型改造/升级流程",
        "steps": [
            {
                "title": "评估改造需求",
                "desc": "确认改造目标（升级网卡/增加内存/更换硬盘等）",
            },
            {
                "title": "确认兼容性",
                "desc": "确认改造后的规格是否能生产目标机型",
                "tips": ["CG1/CG2 搬过来无法生产 S5nt", "注意 BIOS/网卡固件版本"],
            },
            {
                "title": "执行改造",
                "desc": "联系机房现场执行硬件改造",
                "contacts": ["机房运维"],
            },
            {
                "title": "验证上线",
                "desc": "改造完成后重装系统并验证功能",
                "links": [{"name": "ECM重装", "url": "#"}],
            },
        ],
    },
]
