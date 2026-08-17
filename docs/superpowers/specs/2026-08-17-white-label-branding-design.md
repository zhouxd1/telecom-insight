# 元景.智数 — 白标主题系统设计规格

**日期:** 2026-08-17  
**状态:** 已评审（对话确认）  
**产品:** 元景.智数  
**路线:** 干净室自研；延续 Flat 2.0 与 Phase 1b 租户模型  
**前置:** Phase 1b（组织 / 工作空间 / 用户 / 多库数据源）已交付  

## 1. 目标

为每个**组织**提供可配置的完整外观（白标），使售卖给不同运营商时呈现各自品牌，而无需改代码发版。

本期包含：

1. 品牌身份：产品名、副标题、Logo、favicon（上传优先，URL 兜底）  
2. 色彩：主色 / 柔和主色 / 背景 / 表面 / 正文 / 次要文字（CSS 变量）  
3. 深浅色：`light` / `dark` / `system`  
4. 预设主题包：内置若干套可一键套用，再微调  
5. `org_admin` 外观管理页 + 实时预览  

### 1.1 已确认决策

| 项 | 选择 |
|---|---|
| 深度 | 完整主题系统（非仅配置文件） |
| 作用域 | **组织级**一套皮肤（非工作空间、非仅全局） |
| 可调项 | 品牌 + 色彩 + 深浅色 + 预设包（**字体后置**） |
| Logo | 本地上传 + URL 兜底 |
| 实现 | CSS 变量 + `ti_org_branding` 表 |

## 2. 信息架构

- 侧栏新增「外观」或「品牌设置」，**仅 `org_admin` 可见**  
- 其它角色只消费主题，不能修改  
- 登录前无组织上下文 → 使用 `/branding/default`（平台/演示组织默认）  
- 登录后按用户 `org_id` 加载组织主题并应用到文档根节点  
- 不按工作空间拆分皮肤  

## 3. 数据模型

### 3.1 表 `ti_org_branding`

与 `ti_org` 一对一：

| 字段 | 类型/说明 |
|---|---|
| `org_id` | PK，FK → `ti_org.id` |
| `product_name` | 默认「元景.智数」 |
| `tagline` | 副标题，如「运营商智能问数」 |
| `logo_url` | 可选外链 |
| `logo_path` | 上传相对路径；展示时优先于 `logo_url` |
| `favicon_url` / `favicon_path` | 同上 |
| `preset_id` | 内置包 id，如 `default` / `ocean` / `slate` / `amber` |
| `color_mode` | `light` \| `dark` \| `system` |
| `primary` / `primary_soft` / `bg` / `surface` / `text` / `muted` | hex 字符串；空则用 preset |
| `updated_at` | |

### 3.2 资源存储

- 目录：`data/branding/{org_id}/`（Compose 可挂 volume）  
- 允许 MIME：`image/png`、`image/svg+xml`、`image/webp`  
- 单文件 ≤ 512KB；校验 Content-Type + 基础魔数/扩展名  
- 对外 URL：`/media/branding/{org_id}/{filename}`（防路径穿越）  

### 3.3 种子

演示组织写入默认 branding：现有 `logo.svg` + Flat 2.0 青绿 token；`preset_id=default`，`color_mode=light`。

### 3.4 CSS 变量映射

| 字段 / 语义 | CSS 变量（示例） |
|---|---|
| primary | `--accent` |
| primary_soft | `--accent-soft`、`--accent-ink`（可由 primary 派生或存库） |
| bg / surface / text / muted | `--bg`、`--surface`、`--ink`/`--text`、`--muted` |
| color_mode | `html[data-theme=light\|dark]` |

暗色：preset 提供 dark 基线；用户自定义的 `primary` 等覆盖在对应模式上。

## 4. API

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/branding/default` | 登录页默认主题 | 公开 |
| GET | `/orgs/me/branding` | 当前组织主题 | 登录 |
| PUT | `/orgs/me/branding` | 更新文案 / 色 / mode / preset / URL 字段 | `org_admin` |
| POST | `/orgs/me/branding/logo` | multipart 上传 Logo | `org_admin` |
| POST | `/orgs/me/branding/favicon` | 上传 favicon | `org_admin` |
| DELETE | `/orgs/me/branding/logo` | 清除上传 Logo | `org_admin` |
| GET | `/media/branding/{org_id}/{file}` | 静态资源 | 可读（可选鉴权或仅已登录） |

可选：`GET /auth/me` 附带精简 `branding` 摘要以减少首屏往返。

非 `org_admin` 的写操作 → 403。

## 5. 前端

- `applyBranding(theme)`：写入 CSS 变量与 `data-theme`  
- 登录页：挂载时拉 `/branding/default`  
- AppShell / 登录成功后：拉组织 branding 并应用；保存外观后立即应用  
- **外观页**：预设选择、色板、mode、Logo/favicon 上传、实时预览（登录条 + 顶栏缩略）  
- 替换硬编码产品名与固定 `/logo.svg`（保留默认资源作兜底）  
- 延续 Flat 2.0：模块化卡片、统一圆角、弱阴影；仅 token 可变  

路由示例：`/app/branding` 或 `/app/appearance`。

## 6. 内置预设（最少）

| preset_id | 意向 |
|---|---|
| `default` | 现有青绿 Flat 2.0 |
| `ocean` | 偏蓝主色 |
| `slate` | 中性灰蓝 |
| `amber` | 暖色强调（克制，避免大红大紫） |

每套含 light / dark 基线色。

## 7. 验收标准

1. `org_admin` 可改产品名、副标题、主色等；组织主题在登录后稳定生效  
2. 预设一键套用后可微调；`color_mode` light/dark/system 生效  
3. Logo 上传后顶栏与登录相关展示更新；删除上传后回退 URL 或默认 Logo  
4. `analyst` / `viewer` 无外观写入口；写 API 403  
5. 两组织主题互不影响（测试或种子第二组织）  
6. Flat 2.0 结构保持；`pytest` 覆盖 branding CRUD / 权限 / 上传校验；`npm run build` 通过  
7. 干净室：无 SQLBot 资源拷贝  

## 8. 非目标

- 自定义字体包 / 字体上传  
- 工作空间级皮肤  
- 邮件模板白标、打印模板  
- 复杂多组织账号主题缓存策略（按 org 重载即可）  
- SSO 登录页按域名自动解析组织（可后续加）  

## 9. 风险

| 风险 | 缓解 |
|---|---|
| SVG 上传 XSS | 限制/消毒或仅 PNG/WebP 生产默认；SVG 需严格校验 |
| 暗色与自定义色对比度差 | 预览提示；预设保证可读基线 |
| 媒体目录未挂 volume 丢文件 | Compose volume + README |

## 10. 下一步

1. 用户审阅本规格文件  
2. 编写 `docs/superpowers/plans/2026-08-17-white-label-branding.md` 实现计划  
3. 在 `feature/white-label` 分支按计划实现并验收  
