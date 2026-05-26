# 腾讯文档写入 Skill 开发记录（2026-05-26）

## 已完成

### 1. 腾讯文档自动化写入 Skill (`app/skills/tencent_doc_skill.py`)
- **搬迁记录**：15列全部正确写入（直接调用 Skill 时验证通过）
- **投放记录**：11列全部正确写入（直接调用 Skill 时验证通过）
- **操作方式**：Formula Bar 方案（点击公式栏→type输入→Tab跳下一列）
- **中文字符**：通过 Formula Bar（DOM元素）输入，Canvas 上 keyboard.type 只能输入 ASCII
- **单元格内换行**：文本中的 `\n` 用 `Alt+Enter` 实现
- **数据验证列（下拉单选）**：直接输入精确匹配选项文本即可通过验证
- **安全检查**：写入前确认目标行A列为空，非空则中止（防覆盖）

### 2. 工单流转 → OnePage 同步
- 工单提交（create_order）时自动触发异步推送（asyncio.create_task）
- 不阻塞 HTTP 请求，前端秒返回
- 支持搬迁（migration）和投放（host_deploy）两种类型

### 3. 前端改动
- 工单类型精简为搬迁+投放
- 投放需求类型下拉8选项（匹配腾讯文档数据验证）
- 搬迁交付类型加 TEZ裸金属
- 投放加"投放流程重装"字段（3选项）
- 工单详情弹窗展示 detail 字段 + 支持编辑
- 成本一览页面 `/cost`

## 遗留问题（待下次修复）

### P0: 前端提单 detail 传空问题
- **现象**：通过前端提单时，后端收到的 detail 有时为空（`{}`）
- **根因**：之前 `npm run build` 因 vue-tsc 报错没有生成新的 dist，一直用的5月21日旧代码
- **修复状态**：已用 `npx vite build` 重新构建了最新 dist，但因 git pre-commit 拦截未提交
- **下一步**：确认 dist 被正确 serve（刷新浏览器 Cmd+Shift+R），重新测试前端提单

### P1: npm run build 被 vue-tsc 阻断
- `package.json` 中 build 命令包含 `vue-tsc --noEmit`，有 TS 错误就不生成 dist
- 需要修复 TS 错误或改 build 命令跳过类型检查：`"build": "vite build"`
- 当前 TS 错误是 `CircleClose` 未使用等无害警告

### P2: 后台推送浏览器冲突
- Playwright persistent context 不能并发使用
- 如果有其他测试脚本正在用浏览器，推送会失败
- 建议加一个 asyncio.Lock 确保串行执行

## 关键技术要点

### 腾讯文档操作快捷键（Mac）
| 功能 | Playwright 键 |
|------|-------------|
| 移至工作表结尾 | `Meta+End` |
| 移至工作表开头 | `Meta+Home` |
| 向上增加行 | `Alt+Shift+Equal` |
| 删除行 | `Alt+Shift+Minus` |
| 选中行 | `Shift+Space` |
| 编辑单元格 | `F2` |
| 单元格内换行 | `Alt+Enter` |
| 快捷键面板 | `Meta+/` |

### 写入流程
```
1. Cmd+End → 跳到最后有数据的单元格
2. Home → 回到A列
3. 检查A列是否有数据（等待formula bar加载）
4. 有数据 → ArrowDown（末尾则 Alt+Shift+= 插入新行）
5. 安全检查：确认A列为空
6. 逐列：formula_bar.click() → keyboard.type(value) → Tab
7. 验证：Cmd+End → Home → 读取 formula bar
```

### 字段映射
**搬迁记录 Tab 顺序**：A日期 B需求 C紧急 D预期 E前可用区 F前机房 G目的机房 H目的可用区 I数量 J型号 K固资 L交付类型 M重装 N交付模块 O备注

**投放记录 Tab 顺序**：A日期 B紧急 C类型 D固资 E数量 F重装 G设备类型 H关联需求 I搬迁单 J可用区 K备注

### 前端 detail 字段名 → 推送字段名映射
```
source_zone → from_zone
source_idc → from_idc
target_idc → to_idc
zone → to_zone
asset_ids → assets
device_count → quantity
vs_type → device_model
demand_type → type
```
