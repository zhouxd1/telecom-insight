# 元景.智数 — 行级权限（RLS）设计规格

**日期:** 2026-08-17  
**状态:** 已评审（对话确认）  
**产品:** 元景.智数  
**路线:** 干净室自研；延续 Phase 1b 租户 / 工作空间 / 域 ACL  
**前置:** Phase 1b、白标已交付  
**后续队列（本规格不覆盖）:** SSO → 真流式 → 纠错回流  

## 1. 目标

为工作空间成员提供可配置的**行级数据过滤**，使问数结果仅包含授权行，且不可仅靠 Prompt 绕过。

本期包含：

1. 独立策略表 `ti_rls_policy`，策略挂在 **工作空间成员** 上  
2. 谓词形态：表白名单列 + `in` / `eq`（值列表）  
3. **Prompt 提示 + SQL Guard 路径强制改写**  
4. 组织级开关 `rls_admin_bypass`（`org_admin` 是否跳过行过滤）  
5. 成员管理内嵌策略 UI + 列目录 API  

### 1.1 已确认决策

| 项 | 选择 |
|---|---|
| 过滤表达 | 可配置谓词（非仅固定 region/channel 枚举） |
| 挂载点 | 工作空间成员（`ti_workspace_member`） |
| 强制执行 | Prompt 提示 + Guard 改写（非仅 Prompt、非库原生 POLICY） |
| 谓词复杂度 | 列 + `IN` / `=` |
| 管理员绕过 | 组织级可配置开关（默认建议开启绕过） |
| 存储形态 | **独立策略表**（非成员 JSON 字段） |

## 2. 架构

Ask 路径：

1. 解析 `X-Workspace-Id` → 当前成员与域 ACL（既有）  
2. 若用户为 `org_admin` 且该组织 `rls_admin_bypass=true` → 跳过 RLS  
3. 否则加载该 `member_id` 下全部 `ti_rls_policy`  
4. 将策略摘要注入 LLM Prompt（帮助生成合规 SQL）  
5. LLM 产出 SQL → 既有 SQL Guard（只读 / 表白名单）  
6. **RLS rewriter**：对 SQL 中出现的、且存在策略的表注入行条件  
7. 再次校验 / 执行 → 返回结果；steps 中可展示改写后 SQL  

跨库统一走应用层改写，不依赖 Postgres `POLICY` 等库原生能力。

### 2.1 谓词合并规则

- **同一表同一列** 多条策略：条件 **OR**  
- **同一表不同列**：条件 **AND**  
- 多表：各自独立注入；未出现在 SQL 中的表不注入  

示例：`region IN ('华东') OR region IN ('华北')` 可规范为 `region IN ('华东','华北')`；再与 `channel = '营业厅'` AND。

### 2.2 改写策略（实现约束）

- 仅对 Guard 表白名单内、且策略命中的 `(schema, table)` 改写  
- 优先：为引用该表的查询包裹/追加安全的 `AND ( ... )`；复杂 SQL（多 JOIN、子查询）需可测的保守行为：  
  - 能安全定位表引用则注入；  
  - 无法安全改写则 **拒绝执行（403/422）** 并提示，禁止静默放行  
- 字面量仅允许策略中的字符串值经转义后写入，禁止拼接用户自由文本为标识符  

## 3. 数据模型

### 3.1 `ti_org` 新增

| 字段 | 说明 |
|---|---|
| `rls_admin_bypass` | `bool`，默认 `true`（管理员绕过行过滤） |

### 3.2 表 `ti_rls_policy`

| 字段 | 说明 |
|---|---|
| `id` | PK |
| `workspace_id` | FK → `ti_workspace` |
| `member_id` | FK → `ti_workspace_member` |
| `domain` | `biz` / `network` / `cs` |
| `schema_name` | 如 `biz` |
| `table_name` | 如 `sub_month` |
| `column_name` | 如 `region` |
| `op` | `in` \| `eq` |
| `values` | JSON 字符串数组；`eq` 时长度必须为 1 |
| `created_at` / `updated_at` | |

约束：`column_name` 必须属于该域列目录；`values` 非空；创建/更新时校验域与成员 `domains` 交集（可选收紧：策略域须在成员已授权域内）。

### 3.3 列目录

`GET /domains/{domain_id}/rls-columns` 返回可过滤列，来源：

- Pack 表白名单中的表  
- Pack `metrics.yaml` 的 `dimensions` 与 schema 中实际列的交集（演示期可硬编码/从 seed schema 解析的安全子集）  
- 至少覆盖：`biz.sub_month.region`、`biz.channel_day.channel`；network/cs 有明确维度列则一并登记，否则该域可返回空列表  

## 4. API

| 方法 | 路径 | 权限 |
|---|---|---|
| GET | `/workspaces/{id}/members/{mid}/rls` | 空间可读（至少 org_admin；成员本人可读自己的可选） |
| POST | `/workspaces/{id}/members/{mid}/rls` | `org_admin` |
| PUT | `/workspaces/{id}/rls/{policy_id}` | `org_admin` |
| DELETE | `/workspaces/{id}/rls/{policy_id}` | `org_admin` |
| GET / PATCH | `/orgs/me/rls-settings` | GET：登录；PATCH：`org_admin`（`rls_admin_bypass`） |
| GET | `/domains/{id}/rls-columns` | 登录 |

写操作非 `org_admin` → 403。非法列/空 values/错误 op → 400。

## 5. 前端

- 工作空间成员管理中嵌入「行级策略」面板（列表 + 添加/编辑/删除），仅 `org_admin` 可见可写  
- 添加流：域 → 表/列（列目录）→ `in`/`eq` → 值 → 保存  
- 组织设置入口（可挂用户/组织相关页或工作空间旁）：`rls_admin_bypass` 开关  
- 不做独立巨型「RLS 中心」页（YAGNI）  
- 延续 Flat 2.0 与现有 admin 样式  

## 6. 种子与演示

- 默认组织 `rls_admin_bypass=true`  
- 为演示 analyst 成员（若无则种子创建）写入示例策略：`biz.sub_month.region` `in` `['华东']`  
- `demo` org_admin 可关 bypass 自测受限行为  

## 7. 验收标准

1. 无策略成员：问数行为与现网一致  
2. 持有 `region IN ('华东')` 的 analyst：结果仅含华东；steps 可见改写后 SQL  
3. `rls_admin_bypass=true` 时 org_admin 全量；设为 `false` 后若其成员亦有策略则同样受限  
4. 非法列 / 非白名单表 → 400；analyst 写策略 → 403  
5. Prompt 含策略摘要；即使模型未写过滤条件，Guard 路径仍注入  
6. 无法安全改写的 SQL → 拒绝执行，不静默放行  
7. `pytest` 覆盖改写合并规则、ACL、bypass；`npm run build` 通过  
8. 干净室：无 SQLBot 资源拷贝  

## 8. 非目标

- 原始 SQL 谓词片段、`BETWEEN` / `LIKE` 等扩展运算符（可后续加）  
- 库原生 RLS / 按会话 SET 变量  
- 用户级或角色模板级策略（仅成员级）  
- SSO、真流式、纠错回流（队列后续项）  
- 跨工作空间策略继承  

## 9. 风险

| 风险 | 缓解 |
|---|---|
| 复杂 SQL 改写不完整 | 保守拒绝；单表/简单 JOIN 优先测通 |
| 标识符注入 | 列/表仅允许目录枚举；值参数化或严格转义 |
| 与域 ACL 混淆 | 文档与 UI 明确：域控制「能否问该域」，RLS 控制「域内哪些行」 |

## 10. 下一步

1. 用户审阅本规格文件  
2. 编写 `docs/superpowers/plans/2026-08-17-row-level-security.md` 实现计划  
3. 在 `feature/rls`（或等价）分支按计划实现并验收  
4. 完成后进入队列下一项：SSO  
