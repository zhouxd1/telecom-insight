# TelecomInsight — 运营商智能问数设计规格

**日期:** 2026-08-14  
**状态:** 已评审（对话确认）  
**产品暂名:** TelecomInsight（可改）  
**范围:** P0 干净室自研 MVP（A+B：自研产品壳 + 宽松许可 LLM 编排库）

## 1. 背景与目标

基于对开源 SQLBot 产品形态的调研，打造**完全自有版权**的运营商垂直智能问数产品：通用问数引擎 + 可安装的运营商行业包，面向多家运营商交付，长期具备运营闭环。

**不做：** 在 SQLBot 源码上改皮去 Logo 作为闭源自有产品（违反其 GPLv3 + Logo/版权附加条款）。

**要做：** 新仓库干净室实现；SQLBot 仅作能力参考，不复制代码、提示词或前端实现。

### 1.1 已确认决策

| 项 | 选择 |
|---|---|
| 产品定位 | 行业通用产品化（可面向移动/电信/联通等配置交付） |
| 业务覆盖 | 综合门户：经营 / 网络 / 客服，按业务域切换 |
| 版权策略 | 干净室自研（路径 B） |
| 实现策略 | 精益 MVP + 宽松许可组件（A+B） |
| P0 数据 | 合成演示库（非生产数仓） |
| 长期能力 | 能运营（反馈、训练、口径管理）——放入 P2 |

## 2. 干净室与合规纪律

1. 仓库路径与 `SQLBot-main` 物理分离；禁止从 SQLBot 复制粘贴任何源码、提示词、UI 资源。
2. 实现阶段不对照 SQLBot 源码编写；可保留「产品能力清单」级参考（对话问数、术语、示例校准等**能力名**）。
3. 提示词、表结构、文案、品牌全部重写。
4. 第三方依赖优先 MIT / Apache-2.0；维护依赖许可证清单。
5. 本产品默认采用自有开源许可（建议 Apache-2.0），与 SQLBot 许可证无衍生关系。

## 3. 架构

### 3.1 逻辑分层

```
Web 门户（域切换 / 对话 / 结果）
        │
API（鉴权 / 会话）
        │
Ask Engine（LangChain 编排的自研流水线）
        │
   ┌────┼────┬─────────┬──────────┐
   ▼    ▼    ▼         ▼          ▼
Industry  Schema   SQL Guard  Executor   Chart
Packs     RAG      + Generate  (合成仓)   + Narrate
```

### 3.2 组件职责

| 组件 | 职责 |
|---|---|
| 门户层 | 自有品牌 UI、业务域切换、对话与表/图展示 |
| Ask Engine | 意图与缺参澄清 → 加载域 Pack → Schema RAG → 生成 SQL → 护栏 → 执行 → 结论与图表 |
| Industry Packs | 按域提供术语、指标口径、schema 说明、Few-shot、推荐问、seed |
| 合成数仓 | PostgreSQL，按域 schema 隔离演示数据 |
| Ops（P2） | 反馈回流、Few-shot 管理、指标口径版本 |

### 3.3 分期

| 阶段 | 内容 |
|---|---|
| **P0（本规格）** | 干净室引擎 + 三域 Pack + 合成库 + 对话问数 UI + Compose 一键起 |
| **P1** | 白标皮肤、工作空间/租户隔离、域级权限 |
| **P2** | 用户纠错回流、Few-shot 管理后台、指标口径版本管理 |

## 4. 问数流水线（P0）

1. **Domain Context** — 根据当前业务域加载对应 Pack。  
2. **Schema RAG** — embedding + 关键词检索相关表/字段说明。  
3. **SQL Generate** — LLM（OpenAI 兼容）生成只读 SQL，受术语、口径、Few-shot 约束。  
4. **SQL Guard** — 仅允许单条 `SELECT`；禁止多语句与写操作；表名必须在域白名单。  
5. **Execute** — 在合成仓执行；限行、超时。  
6. **Narrate + Chart** — 一句话结论 + 表格 + 至少一种图（折线/柱状等）。

### 4.1 错误处理

- Guard 失败：友好提示「无法安全执行」，可触发改写重试；不向用户暴露堆栈。  
- 超时/超行：截断并提示缩小时间范围或维度。  
- 缺时间/地域/指标：返回澄清问题。  
- 访问域外表：拒绝。  
- 审计：记录问题、生成 SQL、执行是否成功（P0 落库或本地日志）。

## 5. Industry Pack 结构

每个业务域一份可版本化内容包：

```
packs/<domain>/
  manifest.yaml      # 域名、版本、引擎兼容版本
  terminology.yaml   # 术语 → 标准说法 / 字段映射
  metrics.yaml       # 指标名、口径说明、可用维度、口径 SQL 片段
  schema/            # DDL + 字段业务说明
  examples.yaml      # 问法 → 参考 SQL（Few-shot）
  recommended.yaml   # 推荐问
  seed/              # 合成数据脚本
```

### 5.1 P0 三域（合成指标范围）

| 域 | 示例主题 |
|---|---|
| 经营 `biz` | 用户规模、ARPU、套餐收入、渠道发展 |
| 网络 `network` | 小区流量、接通率、告警数、忙时占用 |
| 客服 `cs` | 工单量、投诉类型、满意度、重复投诉 |

## 6. 技术选型

| 层 | 选型 |
|---|---|
| 后端 | Python 3.11、FastAPI、SQLModel/SQLAlchemy |
| LLM 编排 | LangChain（MIT 等宽松许可组件） |
| 大模型 | OpenAI 兼容 API（百炼 / DeepSeek / 本地等可配置） |
| Embedding | 可配置云 API 或开源小模型 |
| 合成仓 | PostgreSQL（默认可改为 DuckDB） |
| 前端 | Vue 3、Vite、TypeScript、ECharts |
| P0 鉴权 | 简单 JWT / 单租户演示账号 |
| 部署 | Docker Compose：web + api + postgres + seed |

### 6.1 仓库布局

```
telecom-insight/
  apps/
    api/           # FastAPI 入口、鉴权
    engine/        # 问数流水线（自研）
    packs/         # Pack 加载器
  packs/
    biz/
    network/
    cs/
  web/             # Vue 门户
  docker/
  docs/
  LICENSE          # 建议 Apache-2.0
```

## 7. P0 验收标准

1. 三域各不少于 8 条推荐问；点选或手输均可得到合理结果。  
2. 故意写操作 / 注入式多语句 SQL 被拦截。  
3. 成功问答同时具备：表格、至少一种图、一句话结论。  
4. `docker compose up` 可启动完整演示环境并完成 seed。  
5. 仓库无 SQLBot 源码拷贝；依赖许可证列表可查。

## 8. 明确非目标（P0）

- 对接真实运营商生产数仓  
- 多租户计费与复杂 RBAC  
- 白标换肤管理后台  
- 完整「越问越准」运营中台（属 P2）

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 干净室执行不严导致版权污染 | 独立仓库、禁止粘贴、依赖审计、实现时不打开 SQLBot 源码 |
| Text-to-SQL 效果不足 | 强依赖 Pack 内 Few-shot 与口径；P0 用固定演示问法保底 |
| 范围膨胀到 P2 | 严格按分期；本规格仅交付 P0 |

## 10. 下一步

本规格用户书面确认后，使用 writing-plans 编写 P0 实现计划，并在 `telecom-insight` 仓库落地实现。
