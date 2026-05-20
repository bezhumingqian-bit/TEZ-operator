# 边缘云资源运维平台 · Web 前端

> Vue 3 + Vite + Element Plus + Pinia + TypeScript
> 对接后端：FastAPI（项目根 `app/` 目录）
> 当前里程碑：**M1 资源查询**（仅模块 4 已落地，其余为占位）

---

## 30 秒启动

```bash
cd web
cp .env.example .env.local         # 可选：覆盖后端地址
npm install
npm run dev                        # http://127.0.0.1:5173
```

默认会把 `/api/*` 反代到 `http://localhost:8000`（即本机 FastAPI）。

如需改后端地址：

```bash
# .env.local
VITE_API_BASE=http://localhost:8000
```

> 严禁把真实内网域名/IP/固资号写进入仓代码，统一用占位（参见
> `.codebuddy/teams/tez-ops/docs/16-数据安全规则.md`）。

---

## 常用命令

| 命令              | 说明                                               |
| ----------------- | -------------------------------------------------- |
| `npm run dev`     | 本地开发                                            |
| `npm run build`   | 类型检查 + 生产构建，产物在 `dist/`                |
| `npm run preview` | 预览 build 产物                                     |
| `npm run lint`    | ESLint + 自动修复                                   |
| `npm run format`  | Prettier 统一格式化                                 |

---

## 目录结构

```
web/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
├── .env.example
└── src/
    ├── main.ts
    ├── App.vue
    ├── env.d.ts
    ├── router/index.ts          # 5 模块路由
    ├── stores/app.ts            # 全局状态 + 最近查询
    ├── api/
    │   ├── client.ts            # axios 实例 + 错误拦截
    │   └── hosts.ts             # 主机查询接口封装
    ├── types/host.ts            # TS 类型，对齐 app/schemas/host.py
    ├── components/
    │   ├── AppHeader.vue        # 顶部栏
    │   ├── AppSidebar.vue       # 左侧导航（5 模块）
    │   ├── HostCard.vue         # 单台主机详情卡
    │   ├── HostTable.vue        # 主机列表（zone 列表用）
    │   ├── BatchTable.vue       # 批量查询结果
    │   └── PlaceholderView.vue  # M2-M4 占位
    ├── views/
    │   ├── HostSearch.vue       # M1 主战场（单条/批量/Zone）
    │   ├── Dashboard.vue        # M4 占位
    │   ├── WorkOrder.vue        # M3 占位
    │   ├── People.vue           # M2 占位
    │   └── Knowledge.vue        # M2 占位
    └── styles/global.css
```

---

## 后端接口契约（W3）

| 方法 | 路径                             | 用途                           | 状态           |
| ---- | -------------------------------- | ------------------------------ | -------------- |
| GET  | `/api/v1/hosts/search?q=...`     | 单条（固资号/IP/Zone 自动识别） | ✅ 已就绪       |
| GET  | `/api/v1/hosts/{asset_id}`       | 详情（含历史）                  | ✅ 已就绪       |
| POST | `/api/v1/hosts/batch_search`     | 批量（最多 100）                | ✅ 已就绪       |
| GET  | `/api/v1/zones/{zone}/hosts`     | Zone 列母机                     | ✅ 已就绪       |
| GET  | `/api/v1/hosts/export?asset_ids=...` | 导出 Excel               | ⏳ W3 后端在做 |

字段类型详见 `src/types/host.ts`，与后端 `app/schemas/host.py` 一一对应。

---

## 5 模块状态

| 模块                  | 路由           | 状态     |
| --------------------- | -------------- | -------- |
| 1 · 运维驾驶舱        | `/dashboard`   | M4 上线  |
| 2 · 工单流转          | `/workorder`   | M3 上线  |
| 3 · 接口人路由器      | `/people`      | M2 上线  |
| **4 · 资源查询** (本期) | `/hosts`       | ✅ M1     |
| 5 · 知识中枢          | `/knowledge`   | M2 上线  |

---

## 数据安全（必读）

- 任何前端代码、注释、占位文案 **不允许出现真实数据**：
  - 真实固资号 → 占位 `TYSV00000001`
  - 真实 IP → 占位 `10.0.0.5`
  - 真实接口人 → 占位 `alice` / `bob` / `carol`
  - 真实客户 → 占位 `customer_a` / `customer_b`
  - 真实 Zone → 占位 `zone_a` / `zone_b` / `zone_c`
- 不要在用户可见文案里出现项目内部代号，统一用「**边缘云资源运维平台**」。
- 后端 URL 全部走 `import.meta.env.VITE_API_BASE`，严禁硬编码。
- 提交前 pre-commit 钩子会扫描敏感模式，若被拦截请脱敏后再提交。

详见仓库根目录文档 `.codebuddy/teams/tez-ops/docs/16-数据安全规则.md`。

---

## 已知遗留 / 后续待办

- [ ] 「联系负责人」按钮 → 等 M2 接口人路由器接入
- [ ] 「创建工单」按钮 → 等 M3 工单流接入
- [ ] 「导出 Excel」 → 等 W3 后端 `GET /api/v1/hosts/export`
- [ ] Zone 列表下拉占位 zone_a/b/c → 后端补 `GET /api/v1/zones` 后改为远程加载
- [ ] Element Plus 当前为完整引入，W4 评估按需打包
- [ ] 鉴权 / 用户中心 → M2 接入 OA 单点
