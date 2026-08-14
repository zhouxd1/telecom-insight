# 元景.智数 — Phase 1a 设计规格（ChatBI 工作台 + 模型/术语/示例）

**日期:** 2026-08-14  
**状态:** 已评审（对话确认）  
**产品:** 元景.智数  
**路线:** 干净室自研；能力对齐 SQLBot 产品清单，**不复制**其源码、提示词或界面实现  
**交付波次:** Phase 1a（串行计划中的第一波）；1b（数据源/工作空间/用户权限）另开规格

## 1. 目标

在 P0 问数引擎与三域 Pack 之上，交付「可演示的正式产品感」：

1. 带侧栏的应用壳与 **ChatBI 多轮工作台**（会话、气泡、SQL/表/图卡片、步骤条）  
2. **模型配置**、**术语库**、**SQL 示例（训练）** 三个管理页及对应 API  
3. Ask 流水线改为优先消费库内模型/术语/示例，Pack 作为种子与兜底  

### 1.1 已确认决策

| 项 | 选择 |
|---|---|
| 版权路线 | 干净室 B（非 SQLBot 二次开发） |
| Phase 1 范围 | 1（工作台+模型/术语/示例）+ 2（数据权限台） |
| 推进方式 | 串行 A：先 1a，再 1b |
| 本规格 | **仅 1a** |

## 2. 信息架构

### 2.1 应用壳

- 顶栏：logo（`branding` / `web/public/logo.svg`）+「元景.智数」+ 当前用户  
- 左侧导航：
  - 问数工作台（默认）
  - 模型配置
  - 术语库
  - SQL 示例
  - 1b 占位（禁用或「即将推出」）：数据源、工作空间、用户  

### 2.2 问数工作台

- **左栏：** 会话列表；新建 / 重命名 / 删除；会话绑定业务域（`biz` / `network` / `cs`）  
- **主区：** 多轮气泡；用户消息为文本；助手消息为结构化卡片：
  - 步骤条（理解 → 检索 → SQL → 执行 → 图表）
  - 可折叠 SQL
  - 数据表格
  - ECharts
  - 一句话结论 / 澄清或错误友好文案  
- **底栏：** 当前域推荐问 chips + 输入框（Enter 发送）  

### 2.3 管理页

| 页 | 能力 |
|---|---|
| 模型配置 | OpenAI 兼容：name、base_url、api_key、model、enabled；测连；至多一个 enabled 用于 Ask |
| 术语库 | 按域筛选；CRUD（term / standard / maps_to） |
| SQL 示例 | 按域筛选；CRUD（question / sql） |

表格 + 抽屉/对话框表单；样式自研，不复用 SQLBot 组件库皮肤。

## 3. 数据模型（Postgres）

在现有合成数仓 schemas 之外，使用应用库表（可与 warehouse 同实例不同 schema，例如 `app`，或默认 `public` 前缀 `ti_`）：

| 表 | 主要字段 |
|---|---|
| `ti_chat_session` | id, title, domain, created_at, updated_at |
| `ti_chat_message` | id, session_id, role(user\|assistant\|system), content_json, created_at |
| `ti_ai_model` | id, name, base_url, api_key, model, enabled, created_at, updated_at |
| `ti_term` | id, domain, term, standard, maps_to, created_at, updated_at |
| `ti_sql_example` | id, domain, question, sql, created_at, updated_at |

助手 `content_json` 约定：

```json
{
  "status": "ok|clarify|error",
  "message": "",
  "steps": [{"id": "retrieve", "label": "检索", "state": "done|active|pending"}],
  "sql": "SELECT ...",
  "rows": [],
  "chart": {},
  "narrative": ""
}
```

Seed：启动或迁移脚本可将 Pack 内 terminology/examples 导入库（幂等），便于演示。

## 4. API

鉴权：现有 JWT；除 `/health`、`/auth/login` 外需 Bearer。

### 4.1 会话与问数

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/sessions` | 会话列表 |
| POST | `/sessions` | 新建 `{ title?, domain }` |
| PATCH | `/sessions/{id}` | 更新 title/domain |
| DELETE | `/sessions/{id}` | 删除会话及消息 |
| GET | `/sessions/{id}/messages` | 消息列表 |
| POST | `/sessions/{id}/ask` | `{ question }` → 跑引擎并落库双端消息，返回助手卡片 |

保留 `POST /ask` 作无会话兼容（可选），工作台以 session ask 为准。

### 4.2 管理

| 资源 | 前缀 | 操作 |
|---|---|---|
| 模型 | `/admin/models` | CRUD + `POST /{id}/test` |
| 术语 | `/admin/terms` | CRUD，`?domain=` |
| 示例 | `/admin/examples` | CRUD，`?domain=` |

### 4.3 Ask 装配

1. 加载会话 domain  
2. 启用中的 `ti_ai_model` → `OpenAICompatibleLLM`；若无启用或无 key → `FakeLLM`/示例匹配兜底（与 P0 行为兼容）  
3. 术语：`ti_term`（该域）∪ Pack terminology  
4. 示例：`ti_sql_example`（该域）∪ Pack examples  
5. Schema RAG → SQL 生成 → Guard → Execute → Chart/Narrate  
6. 写入 user/assistant 消息与审计  

## 5. 前端

- Vue 3 + Vite + TS + Vue Router + ECharts（已有）  
- 路由示例：`/login`，`/app/chat`，`/app/models`，`/app/terms`，`/app/examples`  
- 布局组件：`AppShell`；工作台：`ChatWorkspace`（会话列表 + 线程 + Composer）  
- 管理页：列表 + 表单对话框  
- 品牌：全程「元景.智数」+ 自有 logo；禁止 SQLBot 字样与资源  

## 6. 验收标准（1a）

1. 登录后进入带侧栏应用壳，品牌与 logo 正确  
2. 可创建多个会话、多轮提问；历史刷新后仍在（服务端落库）  
3. 助手消息含步骤、SQL（可折）、表、图、结论（或友好错误/澄清）  
4. 模型/术语/示例三页 CRUD 可用；启用模型后问数使用该配置（无 key 时 Demo 兜底仍可用）  
5. 新增术语或示例后，同域后续提问的 Prompt 上下文包含之  
6. 三域 Pack 推荐问与合成库问数回归可用；`pytest` 全绿  
7. 仓库无 SQLBot 源码/样式/提示词拷贝  

## 7. 非目标（1a）

- 数据源管理 UI、工作空间、用户角色/行级权限（**1b**）  
- 嵌入、MCP、审计中心、白标外观后台  
- 流式 token 输出（可用前端步骤动画模拟；真流式可后续加）  
- 从失败问答「一键收录示例」（可手工 CRUD；自动化属增强项）  

## 8. 风险

| 风险 | 缓解 |
|---|---|
| 范围膨胀到 1b | 本规格仅 1a；1b 另开文档 |
| UI 仍显简陋 | 工作台按 ChatBI 布局重做，避免单页表单 |
| 版权污染 | 禁止打开 SQLBot 源码对照实现；只对照本规格能力名 |

## 9. 下一步

1. 用户确认本规格文件  
2. 编写 `docs/superpowers/plans/2026-08-14-phase1a-chat-admin.md` 实现计划  
3. 在 `feature/phase1a` 分支按计划实现并验收  
