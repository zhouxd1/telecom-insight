# 元景.智数 — Phase 1b 设计规格（租户 / 工作空间 / 用户 / 多库数据源）

**日期:** 2026-08-14  
**状态:** 已评审（对话确认）  
**产品:** 元景.智数  
**路线:** 干净室自研；能力对齐业界 ChatBI 产品清单，**不复制** SQLBot 源码、提示词或界面实现  
**前置:** Phase 1a（ChatBI 工作台 + 模型/术语/示例）已交付  
**交付方式:** 一整包 1b（方案 1）

## 1. 目标

在 1a 之上交付可演示的多租户问数台：

1. **组织 → 工作空间 → 成员** 隔离边界  
2. **用户三角色** + **域级权限**（经营 / 网络 / 客服）  
3. **可切换执行库**的数据源管理；Ask 打到工作空间绑定库  
4. **多数据库类型**（国际主流 + Hive + 国产 P0），同协议族复用连接与 Guard  

### 1.1 已确认决策

| 项 | 选择 |
|---|---|
| 数据源深度 | 可切换执行库 + schema 探测（非仅登记） |
| 工作空间 | 完整租户：组织 → 工作空间 → 成员 |
| 用户权限 | 角色 + 工作空间授权 + 域级可见性；**不行级过滤** |
| 交付方式 | 一整包 1b |
| 角色模型 | 三档：`org_admin` / `analyst` / `viewer` |
| 多库 | P0 清单见 §3；P1 占位 |

## 2. 信息架构与角色

### 2.1 导航

侧栏启用原「即将推出」项：

| 入口 | 说明 |
|---|---|
| 问数工作台 | 顶栏「当前工作空间」切换；会话属当前空间；域下拉 = 有权域 |
| 数据源 | 空间内 CRUD、测连、设默认、类型选择 |
| 工作空间 | 组织下空间列表、创建/归档；成员邀请与角色/域 |
| 用户 | 组织用户账号、org 角色；启用/禁用 |
| 模型 / 术语 / 示例 | 资源归属当前工作空间（1a 数据迁移进默认空间） |

顶栏：logo · 当前组织/空间 · 用户与角色徽标 · 退出。

### 2.2 角色

| 角色 | 能力 |
|---|---|
| `org_admin` | 管组织、空间、用户、全部域；数据源与管理写全开 |
| `analyst` | 问数；管理/查看**有权域**的术语与示例；不可管用户与成员 |
| `viewer` | 只读会话历史与结果；不可 `POST .../ask`、不可新建会话提问；管理写接口 403 |

域权限挂在工作空间成员关系上；`org_admin` 视为全部域（`biz` / `network` / `cs`）。

## 3. 多数据库支持

### 3.1 P0（本期必做）

| db_type | protocol_family | 说明 |
|---|---|---|
| `postgres` | `postgres` | 现有 Compose 演示库 |
| `mysql` | `mysql` | |
| `sqlserver` | `mssql` | |
| `hive` | `hive` | HiveServer2 / JDBC；限 SELECT |
| `opengauss` | `postgres` | |
| `gaussdb` | `postgres` | |
| `oceanbase_mysql` | `mysql` | OceanBase MySQL 模式 |
| `tidb` | `mysql` | |
| `kingbase` | `postgres` | 人大金仓 |
| `dameng` | `dm` | 达梦 |

### 3.2 P1（UI 占位，「即将支持」不可设为执行默认）

南大通用 GBase、神通、PolarDB、TDSQL 等；可后续复用 MySQL/PG 协议子集。

### 3.3 引擎约定

- `ti_datasource` 存 `db_type` + 连接字段；运行时映射 `protocol_family`  
- 同族复用：连接工厂、introspect、SELECT-only Guard、超时  
- Ask Prompt 按 `db_type` / 方言注入说明；**不做**跨库联邦与写入类 SQL  
- 自动化：至少 Postgres + MySQL + Hive 有测连/执行路径测试；其余 P0 驱动冒烟或可跳过式集成标记  

## 4. 数据模型

应用表（`ti_*`，与数仓可同实例）：

| 表 | 要点 |
|---|---|
| `ti_org` | id, name, created_at |
| `ti_workspace` | id, org_id, name, status(`active`\|`archived`), created_at |
| `ti_user` | id, org_id, username, password_hash, display_name, org_role(`org_admin`\|`analyst`\|`viewer`), enabled |
| `ti_workspace_member` | workspace_id, user_id, role(`org_admin`\|`analyst`\|`viewer`), domains(JSON 数组) |
| `ti_datasource` | id, workspace_id, name, db_type, host, port, database, username, password_enc, extra_json(JDBC 参数等), is_default, last_ok_at, last_error |
| 既有表加 `workspace_id` | `ti_chat_session`、`ti_ai_model`、`ti_term`、`ti_sql_example` |
| 可选 | `ti_chat_session.datasource_id` 覆盖空间默认 |

**角色生效规则（消除歧义）**

- `ti_user.org_role`：组织级能力——能否管理用户、创建/归档工作空间、查看组织下全部空间  
- `ti_workspace_member.role` + `domains`：空间内问数与资源写权限  
- 若 `org_role == org_admin`：视为可进入组织下任意空间；空间内等同 `org_admin` 且 `domains` 为全部三域（无需依赖成员行，但种子仍写入成员行便于列表展示）  
- 否则：必须是目标空间成员；有效角色与域以成员行为准  
- Ask / 管理写：先校验空间成员（或 org_admin），再按有效角色限制 `viewer` 只读  

**规则**

- 登录查 `ti_user`（不再仅用环境变量单账号；种子保留 `demo` / `demo123`）  
- JWT：`sub=user_id`，声明 `org_id`；当前空间由请求头 `X-Workspace-Id` 传递并校验成员资格  
- 密码：`password_enc` 用应用密钥加密，列表/详情**不明文**回显  
- Ask 执行：会话绑定源 > 空间默认源；无可用源或测连失败 → 友好 `error`，不误连其它库  
- 域：会话 `domain` ∉ 成员 `domains`（且非 org 全域管理员）→ 403  

**种子与迁移**

- 1 组织「演示运营商」、1 工作空间「默认」、1 数据源指向现有 Compose Postgres、三域全开  
- `demo` 用户为 `org_admin` 并加入默认空间  
- 现有 1a 会话/模型/术语/示例回填 `workspace_id` 到默认空间  

## 5. API

### 5.1 鉴权

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/login` | 校验 `ti_user`，返回 JWT |
| GET | `/auth/me` | 当前用户、org、角色、可访问工作空间摘要 |

除 `/health`、`/auth/login` 外需 Bearer。需空间上下文的接口要求 `X-Workspace-Id`。

### 5.2 租户与成员

| 前缀 | 能力 | 权限 |
|---|---|---|
| `/orgs/me` | 当前组织 | 登录用户 |
| `/workspaces` | 列表（我加入的）/ 创建 / 归档 | 创建/归档：`org_admin` |
| `/workspaces/{id}/members` | 成员 CRUD；`role` + `domains[]` | `org_admin` |
| `/admin/users` | 组织用户 CRUD、启用/禁用、org_role | `org_admin` |

### 5.3 数据源

| 操作 | 说明 |
|---|---|
| CRUD `/admin/datasources` | 空间隔离；密码只写不读明文 |
| `POST /{id}/test` | 测连并更新 `last_ok_at` / `last_error` |
| `POST /{id}/default` | 设空间默认（同空间唯一） |
| `POST /{id}/introspect` | 可选；拉取 schema 摘要缓存 |

P1 `db_type` 拒绝设为默认或返回明确错误。

### 5.4 既有资源

`/sessions`、`/admin/models|terms|examples`、`/domains`：

- 全部按 `workspace_id` 过滤  
- 写操作与 Ask：校验角色 + 域权限  
- `viewer`：允许 GET 会话/消息；禁止 POST ask / 新建提问会话 / 管理写  

### 5.5 Ask 装配（相对 1a）

1. 解析用户 + 工作空间 + 成员（角色、domains）  
2. 校验会话 domain  
3. 解析数据源 → 按 `protocol_family` 建连接  
4. Schema RAG：introspect 缓存或对目标库探测（白名单 schema）  
5. 模型 / 术语 / 示例：仅当前空间；术语/示例再按域过滤  
6. LLM（按方言提示）→ Guard（族方言 SELECT-only）→ Execute → 图表/叙述 → 落库  

## 6. 前端

- 延续 Flat 2.0：浅色卡片、统一圆角、弱阴影、克制青绿；无深色主按钮/深色用户气泡（已与 1a 后样式对齐）  
- 工作空间切换器；请求统一带 `Authorization` + `X-Workspace-Id`  
- 数据源页：类型下拉（P0 可选、P1 禁用提示）、测连、设默认、脱敏  
- 工作空间页：列表 + 成员抽屉（角色 + 域多选）  
- 用户页：组织用户表 + 表单  
- 问数台：`viewer` 隐藏新建对话与发送区；无默认数据源时空态引导  

路由示例：`/app/datasources`、`/app/workspaces`、`/app/users`（在现有 `/app/*` 下）。

## 7. 验收标准

1. 种子 `demo`（org_admin）可登录；默认组织/空间/Postgres 数据源可用；三域问数回归  
2. 可建第二工作空间并绑定数据源；Ask 打到对应库  
3. `analyst` 仅见有权域；调整 `domains` 后行为立即变化  
4. `viewer` 能看历史，不能提问/新建会话提问  
5. 非成员访问他人空间 → 403；密码不明文回显  
6. 模型/术语/示例按空间隔离  
7. P0 多库：登记与测连路径可用；PG + MySQL + Hive 至少具备自动化或文档化集成验证；其余 P0 冒烟  
8. `pytest` 覆盖鉴权、三角色、域权限、数据源默认切换、空间隔离  
9. 仓库无 SQLBot 源码/样式/提示词拷贝  

## 8. 非目标（1b）

- 行级数据过滤  
- SSO / LDAP / 邀请邮件  
- 白标外观后台、审计中心、嵌入、MCP  
- 真流式 token 输出  
- 跨库联邦查询、写入/DDL  
- P1 国产库完整问数（仅占位）  

## 9. 风险

| 风险 | 缓解 |
|---|---|
| 多驱动依赖膨胀 | 协议族复用；可选依赖/懒加载；CI 对非核心库标记 skip |
| Hive/达梦环境难测 | 接口契约测试 + 可选手动/外部 JDBC；文档写明验证矩阵 |
| 1a 数据无 workspace | 启动迁移脚本幂等回填默认空间 |
| 范围过大 | 严格按 P0 清单；P1 仅 UI 占位 |

## 10. 下一步

1. 用户审阅本规格文件  
2. 编写 `docs/superpowers/plans/2026-08-14-phase1b-tenant-datasource.md` 实现计划  
3. 在 `feature/phase1b` 分支按计划实现并验收  
