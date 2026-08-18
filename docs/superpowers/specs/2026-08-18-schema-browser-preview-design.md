# 元景.智数 — 数据源库表浏览、结构元数据与样例预览

**日期:** 2026-08-18  
**状态:** 对话确认，待用户审阅本文件  
**产品:** 元景.智数  
**路线:** 干净室自研；**不复制** SQLBot 源码、提示词或界面实现  
**前置:** Schema Catalog 与字段 ACL 已交付（`2026-08-17-schema-catalog-field-acl-design.md`）  

## 1. 目标

在现有 Catalog 探测/授权之上，把「看得见库表」做成可点选的浏览体验：

1. 点数据源进入该库的表树  
2. 点表后右侧展示**完整列/表元数据**，并可勾选字段授权  
3. 同一右侧可预览样例数据（只读 LIMIT）  

问数强制规则不变：空授权拒绝；未授权列拒绝；RLS 仍生效。

### 1.1 已确认决策

| 项 | 选择 |
|---|---|
| 入口 | **方案 A**：侧栏不新增「库表」；数据源列表点一行进入浏览，可返回列表 |
| 浏览+授权 | **合一**：左表树，右「结构 \| 数据」；结构页勾选即授权 |
| 谁能进 | 空间成员可看结构与预览；仅 `org_admin` 能改勾选 |
| 未授权表/列 | 结构与预览**仍可见**；Ask 仍按 Catalog effective 拒绝 |
| 结构内容 | 表级 + 列级探测元数据（见 §3）；本期不做索引/外键树 |
| 预览执行 | 主 API 连真实库只读 `SELECT` + `LIMIT`；Catalog **不**存样例、**不**存密码 |
| 预览行过滤 | 套现有 RLS；`org_admin` 旁路与问数相同 |

## 2. 界面

### 2.1 数据源列表

- 保留测连、设默认、新建/编辑/删除  
- 行可点击进入浏览态（键盘可聚焦）；操作列按钮不触发进入浏览  
- 「刷新结构」「字段授权」从列表操作中移除或降为浏览态工具条（刷新保留；授权改为结构页勾选，不再单独弹层）  

### 2.2 浏览态

```
[← 返回列表]  默认数据源 · postgres
[刷新结构]

[ schema 分组表树 ]  |  [ 结构 | 数据 ]
                     |  表头：schema.table
```

- 左：按 `schema_name` 分组，列出 `table_name`  
- 未探测过：空态文案引导「刷新结构」  
- 右默认「结构」；切「数据」时按当前表拉预览  
- 成员：勾选控件 disabled，仍展示 granted 状态  
- `org_admin`：勾表默认全列（与现授权 UX 一致）；保存即 `PUT grants`  

## 3. 元数据模型

在现有 `cat_table` / `cat_column`（及 schema API JSON）上扩展，探测时写入快照。缺省字段存空串/`null`，UI 显示「—」。

### 3.1 表级

| 字段 | 说明 |
|---|---|
| `schema_name`, `table_name` | 已有 |
| `table_kind` | `table` / `view` / 其它探测值 |
| `table_comment` | 表注释（Postgres `obj_description` 等） |
| `refreshed_at` | 已有 |

### 3.2 列级

| 字段 | 说明 |
|---|---|
| `column_name`, `data_type`, `nullable` | 已有；`data_type` 展示完整类型（含长度/精度，如 `character varying(32)`） |
| `ordinal_position` | 列顺序 |
| `column_default` | 默认值原文 |
| `is_primary_key` | 是否主键列 |
| `column_comment` | 列注释 |

Postgres 优先填全；其它 `db_type` 尽力而为。刷新结构会替换该数据源快照（授权行仍按现逻辑保留，不随列注释覆盖而清空，除非产品另改——**本期不因刷新而清空 grants**）。

## 4. API

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/admin/datasources/{id}/schema` | 空间成员 | 树 + 授权标记 + §3 元数据 |
| PUT | `/admin/datasources/{id}/grants` | `org_admin`（现 `_require_ds_manage`） | 不变 |
| POST | `/admin/datasources/{id}/introspect` | `org_admin` | 探测写入扩展字段 |
| GET | `/admin/datasources/{id}/preview` | 空间成员 | query: `schema`, `table`, `limit`（默认 50，最大 200） |

### 4.1 Preview 行为

- 表必须存在于该数据源 Catalog 快照，否则 404  
- 列清单来自快照（含未授权列）；用引擎标识符引用规则拼 `SELECT`，**禁止**客户端传入 SQL  
- `LIMIT n`；超过 n 条则 `truncated: true`  
- 连接失败：与 Ask 类似的错误文案（不 500 堆栈）  
- Catalog 不可用：现网 503  
- 套 `load_rls_predicates` + `apply_rls`（与 Ask 同一套）；执行前仍走只读 guard（单表 SELECT）  
- 响应：`{ columns: [...], rows: [...], truncated: bool }`  

## 5. 与 Ask / 授权关系

- Pack 仍不是表白名单真相  
- 预览**不**检查 Catalog `effective.empty`  
- Ask **仍**空授权 403、未授权列拒绝  
- 种子 grants、Compose Catalog health 行为不变  

## 6. 验收

1. 点数据源行进入浏览；返回回到列表  
2. 刷新后可见 biz/network/cs 表；点 `biz.sub_month` 结构表含类型/可空/默认/主键/注释（有则显示）  
3. 切「数据」看到最多 50 行；`analyst1` 受 RLS（华东）  
4. `demo` 可勾选保存；`analyst` 勾选不可改，PUT 403  
5. 未授权列仍可在结构/预览中看到；Ask 引用未授权列仍失败  
6. `pytest` + `npm run build` 通过  
7. 干净室：无 SQLBot 资源拷贝  

## 7. 非目标

- 侧栏独立「库表」页（方案 B，已否决）  
- 索引 / 外键 / ER 图  
- 成员级列权限  
- 结果集列遮罩  
- 在 Catalog 持久化样例行  
- 可写 SQL 控制台  

## 8. 风险

| 风险 | 缓解 |
|---|---|
| 预览泄露未授权列 | 已确认产品选择：浏览放开、问数收紧；README 写明 |
| 标识符注入 | 仅允许快照内 schema/table/column；引用而非拼接用户字符串为 SQL 片段 |
| 大表预览 | LIMIT 上限 200 + statement timeout（沿用执行器） |
| 非 PG 元数据不全 | UI 缺省「—」，不阻塞浏览 |
