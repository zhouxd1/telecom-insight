# 元景.智数 — 数据源库表浏览与字段权限设计规格

**日期:** 2026-08-17  
**状态:** 已评审（对话确认）  
**产品:** 元景.智数  
**路线:** 干净室自研；**不复制** SQLBot 源码、提示词或界面实现  
**前置:** Phase 1b 数据源、行级 RLS、白标已交付  
**队列关系:** 与 SSO / 真流式 / 纠错回流并行排队；本规格为独立子系统  

## 1. 目标

交付接近业界 ChatBI 的「看得见库表、控得住字段」能力：

1. **库表浏览**：从工作空间数据源探测 schema / 表 / 列并展示  
2. **字段权限**：工作空间级统一表/列白名单；未授权不可问数  
3. **强制执行**：Prompt 提示 + Guard 路径表级白名单 + **列级拒绝**（引用未授权列则失败）  
4. **外挂 Catalog 服务**：元数据与授权与主 API 解耦，同 Compose 部署，日后可拆仓  

### 1.1 已确认决策

| 项 | 选择 |
|---|---|
| 范围 | 库表浏览 + 字段权限一体交付 |
| 授权挂载 | **工作空间级**统一白名单（非按成员） |
| 问数真相来源 | **实库探测 + 空间授权**；Pack 仅术语/示例/指标 |
| 强制执行 | Prompt + Guard/改写路径强制；未授权列 → **拒绝**（非结果遮罩） |
| 空授权默认 | **拒绝问数**（须先探测并勾选） |
| 架构 | **外挂 Catalog 服务**（方案 3） |

## 2. 架构

```
[Vue 数据源页] → [主 API 鉴权代理] → [Catalog 服务]
                                         ├ introspect（主 API 代传短时连接或受控代理执行）
                                         ├ schema 树缓存
                                         └ workspace grants
[Ask / Session Ask] → 主 API → GET Catalog effective
                   → 空授权则 403
                   → Prompt 附带允许表列
                   → SQL Guard（表白名单=授权表）
                   → 列级校验（未授权列 → SqlGuardError）
                   → 既有 RLS 行过滤
                   → 执行
```

- Catalog：本仓库 `apps/catalog`（FastAPI）+ Compose 服务 `catalog`；内网 HTTP  
- 主 API：保留租户/ACL；对前端只暴露已鉴权的 `/admin/datasources/...` 代理  
- **不**在 Catalog 长期存储数据源明文密码；探测时由主 API 注入短时连接材料或代执行只读元数据 SQL  
- Pack `table_whitelist` **不再**作为 Ask 表结构真相；演示种子通过 Catalog grants 预授权  

### 2.1 与 RLS / 域 ACL 关系

| 层 | 作用 |
|---|---|
| 域 ACL | 能否问该业务域 |
| Catalog 表/列授权 | 域内可用哪些表、哪些列 |
| RLS | 行范围 |

顺序：**域 → 表列授权 → RLS → 执行**。

## 3. 数据模型（Catalog）

建议同 Postgres 使用 schema `catalog`（或独立 DB URL `TI_CATALOG_DATABASE_URL`）。

### 3.1 `catalog_datasource_ref`

| 字段 | 说明 |
|---|---|
| `workspace_id`, `datasource_id` | 关联主系统 |
| `db_type`, `fingerprint` | 类型与配置摘要（无密码） |
| `last_introspected_at` | |

### 3.2 `catalog_table` / `catalog_column`

- table: `schema_name`, `table_name`, `datasource_id`, `refreshed_at`  
- column: `table_id`, `column_name`, `data_type`, `nullable`  

### 3.3 `catalog_ws_table_grant` / `catalog_ws_column_grant`

- 工作空间级；列授权必须属于已授权表（或保存时自动含表）  
- **无任何 grant → effective 为空 → Ask 拒绝**  
- 仅有表 grant、无列 grant：视为该表**零列**可用（仍拒绝涉及该表的列引用）— 或保存 UX 要求勾表时至少勾一列；**定为：勾选表时默认勾选当前探测到的全部列，管理员可取消部分列**  

## 4. API

### 4.1 Catalog 内网

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/introspect` | body: workspace_id, datasource_id, 短时连接材料；刷新表列 |
| GET | `/v1/workspaces/{id}/schema?datasource_id=` | 树 + 授权标记 |
| PUT | `/v1/workspaces/{id}/grants` | 批量表/列授权 |
| GET | `/v1/workspaces/{id}/effective?datasource_id=` | Ask 用精简白名单；可按当前默认源 |

### 4.2 主 API（对前端）

| 方法 | 路径 | 权限 |
|---|---|---|
| POST | `/admin/datasources/{id}/introspect` | 可管理数据源（org_admin 等既有规则） |
| GET | `/admin/datasources/{id}/schema` | 空间成员只读；写授权仅 admin |
| PUT | `/admin/datasources/{id}/grants` | org_admin |
| （内部） | Ask 调 Catalog `effective` | — |

替换/充实现有空实现 `connectors.introspect_schema`：真实探测逻辑放 Catalog（或主 API 共享 `apps/engine` 探测模块供 Catalog 调用，避免双份方言）。

### 4.3 列级强制

- 解析 SQL 中引用的列（投影、WHERE、GROUP BY、ORDER BY、JOIN 条件）  
- 不在 effective 列白名单内 → `SqlGuardError` / Ask error，**不静默剥离**  
- 无法安全解析列引用 → 拒绝（与 RLS 保守策略一致）  

## 5. 前端

- 数据源列表行操作：「刷新结构」「字段授权」  
- 抽屉/子页：树形勾选（表 + 列），显示类型；保存 grants  
- Flat 2.0；仅 org_admin 可写  
- Ask 失败文案：引导至数据源授权  

## 6. 种子与演示

- Compose 增加 `catalog` 服务与卷/库  
- 种子：对演示默认源探测后，预授权 `biz.sub_month`、`biz.channel_day` 及核心列（与现 Pack 演示一致），保证 `demo` 开箱可问  
- README 说明 Catalog 与授权流程  

## 7. 验收标准

1. Postgres 演示库可刷新并看见真实表/列  
2. 清空授权后 Ask → 拒绝并提示  
3. 仅授权部分列时，含未授权列的 SQL → 拒绝；仅授权列可出数  
4. 表列授权与 RLS 可叠加  
5. Pack 不决定表白名单；effective 来自 Catalog  
6. analyst 写 grants → 403  
7. `pytest`（主 API + Catalog）+ `npm run build` 通过  
8. 干净室：无 SQLBot 资源拷贝  

## 8. 非目标

- Catalog 独立账号 / SSO（用主 API 鉴权代理）  
- 跨库联邦、自动推荐授权  
- Hive/全部国产库完整类型映射（P0 以 Postgres 为主；其它族尽力而为或标注降级）  
- 成员级列权限（本期仅空间级；成员级可后续加）  
- 结果集列遮罩模式  

## 9. 风险

| 风险 | 缓解 |
|---|---|
| 外挂服务增加运维面 | 同 Compose、健康检查、主 API 超时降级明确报错 |
| 列引用解析不完整 | 保守拒绝；单表 SELECT 优先测通 |
| 密码传递 | 短时材料 / 主 API 代执行；不落 Catalog 盘 |
| 与旧 Pack 白名单行为差异 | 种子预授权 + README 迁移说明 |

## 10. 下一步

1. 用户审阅本规格文件  
2. 编写 `docs/superpowers/plans/2026-08-17-schema-catalog-field-acl.md` 实现计划  
3. 分支 `feature/schema-catalog` 按计划实现并验收  
4. 队列其他项（SSO 等）仍可穿插，但本子系统独立交付  
