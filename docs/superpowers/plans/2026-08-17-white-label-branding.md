# White-Label Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver org-level white-label theming — product name, logo/favicon (upload + URL), CSS color tokens, light/dark/system mode, built-in presets, and an org_admin Appearance page with live preview.

**Architecture:** Store theme in `ti_org_branding` (1:1 with `ti_org`). Resolve effective colors from `preset_id` + optional field overrides. Serve uploads from `data/branding/{org_id}/` via `/media/branding/...`. Frontend `applyBranding()` writes CSS variables and `data-theme` on `<html>`.

**Tech Stack:** FastAPI, SQLModel, python-multipart, Vue 3 + existing Flat 2.0 tokens, pytest.

**Spec:** `docs/superpowers/specs/2026-08-17-white-label-branding-design.md`

**Clean-room:** Never open or copy SQLBot-main.

**Branch:** `feature/white-label` from latest `main`.

**Git author (do not git config):** `GIT_AUTHOR_NAME=zhouxd1` `GIT_AUTHOR_EMAIL=zhouxd1@users.noreply.github.com` (same for committer).

---

## File map

| Path | Responsibility |
|---|---|
| `apps/api/models_db.py` | Add `TiOrgBranding` |
| `apps/api/branding_presets.py` | Built-in preset light/dark color maps |
| `apps/api/branding_resolve.py` | Merge preset + overrides → public DTO fields |
| `apps/api/media_store.py` | Save/delete branding files under `data/branding/` |
| `apps/api/routes_branding.py` | default/me branding + upload + media |
| `apps/api/schemas.py` | BrandingOut, BrandingUpdate |
| `apps/api/init_db.py` | Seed default branding for demo org |
| `apps/api/settings.py` | `branding_data_dir` |
| `apps/api/main.py` | Include router; mount media if needed |
| `docker/docker-compose.yml` | Volume for branding data |
| `web/src/branding.ts` | `applyBranding`, resolve logo URL, types |
| `web/src/api.ts` | Branding API helpers |
| `web/src/views/admin/BrandingView.vue` | Appearance admin UI |
| `web/src/layouts/AppShell.vue` | Apply branding; nav link for org_admin |
| `web/src/views/LoginView.vue` | Default branding on mount |
| `web/src/router/index.ts` | `/app/branding` |
| `web/src/styles.css` | Ensure tokens overridable; dark `[data-theme=dark]` baseline |
| `tests/test_branding.py` | CRUD, ACL, upload, resolve |
| `.gitignore` | `data/branding/` local uploads (keep dir via `.gitkeep` if useful) |

---

### Task 1: Branch + model + presets + resolve

**Files:**
- Create: `apps/api/branding_presets.py`, `apps/api/branding_resolve.py`
- Modify: `apps/api/models_db.py`, `apps/api/init_db.py`
- Create: `tests/test_branding_resolve.py`

- [ ] **Step 1: Create branch**

```bash
git checkout main
git pull
git checkout -b feature/white-label
```

- [ ] **Step 2: Failing test**

```python
# tests/test_branding_resolve.py
from apps.api.branding_resolve import resolve_branding_colors
from apps.api.branding_presets import PRESETS

def test_default_preset_has_primary():
    assert "default" in PRESETS
    colors = resolve_branding_colors(preset_id="default", color_mode="light", overrides={})
    assert colors["primary"].startswith("#")

def test_override_primary_wins():
    colors = resolve_branding_colors(
        preset_id="default", color_mode="light", overrides={"primary": "#112233"}
    )
    assert colors["primary"] == "#112233"
```

- [ ] **Step 3: Run — expect FAIL**

Run: `pytest tests/test_branding_resolve.py -v`

- [ ] **Step 4: Implement presets + resolve + model**

`branding_presets.py` — dict `PRESETS[preset_id]["light"|"dark"]` with keys `primary`, `primary_soft`, `bg`, `surface`, `text`, `muted` for: `default`, `ocean`, `slate`, `amber`.

`branding_resolve.py`:

```python
def resolve_branding_colors(*, preset_id: str, color_mode: str, overrides: dict) -> dict[str, str]:
    mode = "dark" if color_mode == "dark" else "light"
    # system resolved on client; server returns light base + mode flag
    base = PRESETS.get(preset_id, PRESETS["default"])[mode]
    out = dict(base)
    for k in ("primary", "primary_soft", "bg", "surface", "text", "muted"):
        v = overrides.get(k)
        if v:
            out[k] = v
    return out
```

`TiOrgBranding` fields per spec; add to `_MODELS`.

`seed_tenant_bootstrap`: after org create, upsert `TiOrgBranding` for demo org with `product_name=元景.智数`, `tagline=运营商智能问数`, `preset_id=default`, `color_mode=light`.

- [ ] **Step 5: pytest + commit**

```bash
pytest tests/test_branding_resolve.py tests/test_tenant_models.py -v
git add apps/api/models_db.py apps/api/branding_presets.py apps/api/branding_resolve.py apps/api/init_db.py tests/test_branding_resolve.py
git commit -m "feat: add org branding model and preset resolver"
```

---

### Task 2: Branding API (GET/PUT) + ACL

**Files:**
- Create: `apps/api/routes_branding.py`
- Modify: `apps/api/schemas.py`, `apps/api/main.py`, `apps/api/settings.py`
- Create: `tests/test_branding.py`

- [ ] **Step 1: Tests**

```python
def test_default_branding_public(client_with_seed):
    r = client_with_seed.get("/branding/default")
    assert r.status_code == 200
    body = r.json()
    assert body["product_name"]
    assert body["colors"]["primary"]

def test_org_admin_can_update_branding(authenticated_client):
    # headers from demo org_admin
    r = authenticated_client.put(
        "/orgs/me/branding",
        json={"product_name": "测试智数", "preset_id": "ocean", "primary": "#0066aa"},
    )
    assert r.status_code == 200
    assert r.json()["product_name"] == "测试智数"
    assert r.json()["colors"]["primary"] == "#0066aa"

def test_analyst_cannot_put_branding(client_analyst_headers):
    r = client_analyst_headers.put("/orgs/me/branding", json={"product_name": "X"})
    assert r.status_code == 403
```

Reuse/extend conftest helpers; create analyst user via `/admin/users` if needed.

- [ ] **Step 2: Schemas**

```python
class BrandingOut(BaseModel):
    org_id: int | None = None
    product_name: str
    tagline: str
    logo_url: str | None = None
    logo_path: str | None = None
    logo_src: str  # resolved absolute path for clients: media URL or logo_url or /logo.svg
    favicon_src: str
    preset_id: str
    color_mode: str
    primary: str | None = None
    # ... optional override fields echoed
    colors: dict[str, str]  # resolved

class BrandingUpdate(BaseModel):
    product_name: str | None = None
    tagline: str | None = None
    logo_url: str | None = None
    favicon_url: str | None = None
    preset_id: str | None = None
    color_mode: str | None = None
    primary: str | None = None
    primary_soft: str | None = None
    bg: str | None = None
    surface: str | None = None
    text: str | None = None
    muted: str | None = None
```

- [ ] **Step 3: Routes**

- `GET /branding/default` — load branding for first/demo org or hardcoded defaults via resolve  
- `GET /orgs/me/branding` — current user's org  
- `PUT /orgs/me/branding` — `require_org_admin`; validate `preset_id` in PRESETS; validate hex `^#[0-9A-Fa-f]{6}$` when set; validate `color_mode` in light|dark|system  

Wire router in `main.py`.

- [ ] **Step 4: pytest + commit** `feat: add org branding get and update APIs`

---

### Task 3: Upload logo/favicon + media serve

**Files:**
- Create: `apps/api/media_store.py`
- Modify: `apps/api/routes_branding.py`, `apps/api/settings.py`, `docker/docker-compose.yml`, `.gitignore`
- Extend: `tests/test_branding.py`

- [ ] **Step 1: Settings**

```python
branding_data_dir: str = "data/branding"
```

Compose api service:

```yaml
environment:
  TI_BRANDING_DATA_DIR: /app/data/branding
volumes:
  - branding_data:/app/data/branding
```

Add volume `branding_data`. Gitignore `data/branding/**` but allow `data/branding/.gitkeep`.

- [ ] **Step 2: media_store**

```python
ALLOWED = {".png": b"\x89PNG", ".webp": b"RIFF", ".svg": None}  # svg: check content-type + no <script>

def save_branding_file(org_id: int, kind: str, filename: str, data: bytes) -> str:
    # kind in logo|favicon; return relative path like "{org_id}/logo.png"
    ...

def branding_file_abs(data_dir: Path, org_id: int, name: str) -> Path:
    # resolve and ensure under data_dir / str(org_id)
    ...
```

Reject if size > 512_000; reject path `..`.

- [ ] **Step 3: Upload endpoints + GET media**

`POST /orgs/me/branding/logo` with `UploadFile`; set `logo_path`; return BrandingOut.  
`DELETE /orgs/me/branding/logo` clears `logo_path` (keep `logo_url`).  
`GET /media/branding/{org_id}/{filename}` FileResponse with safe join.

Test with tiny PNG bytes:

```python
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)
```

- [ ] **Step 4: pytest + commit** `feat: add branding logo upload and media route`

---

### Task 4: Frontend applyBranding + login/shell wiring

**Files:**
- Create: `web/src/branding.ts`
- Modify: `web/src/api.ts`, `web/src/views/LoginView.vue`, `web/src/layouts/AppShell.vue`, `web/src/styles.css`

- [ ] **Step 1: branding.ts**

```ts
export type Branding = {
  product_name: string;
  tagline: string;
  logo_src: string;
  favicon_src: string;
  preset_id: string;
  color_mode: string;
  colors: Record<string, string>;
  // optional override echoes
};

const VAR_MAP: Record<string, string> = {
  primary: "--accent",
  primary_soft: "--accent-soft",
  bg: "--bg",
  surface: "--surface",
  text: "--text",
  muted: "--muted",
};

export function applyBranding(b: Branding) {
  const root = document.documentElement;
  const mode =
    b.color_mode === "system"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : b.color_mode;
  root.dataset.theme = mode;
  for (const [k, cssVar] of Object.entries(VAR_MAP)) {
    if (b.colors[k]) root.style.setProperty(cssVar, b.colors[k]);
  }
  if (b.colors.primary) {
    root.style.setProperty("--accent-ink", b.colors.primary);
  }
  // favicon link
  let link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
  if (link) link.href = b.favicon_src || "/logo.svg";
}
```

- [ ] **Step 2: api.ts** — `fetchDefaultBranding`, `fetchOrgBranding`, `updateOrgBranding`, `uploadBrandingLogo`, `deleteBrandingLogo`

- [ ] **Step 3: LoginView** — onMounted fetch default branding, apply, bind `product_name` / `tagline` / `logo_src` in template

- [ ] **Step 4: AppShell** — after `fetchMe`, fetch org branding (or from me if attached), apply; show `product_name` in brand text; use `logo_src` for img

- [ ] **Step 5: styles.css** — add `[data-theme="dark"]` token overrides for baseline dark (bg/surface/text/line) so mode switch works even before custom colors

- [ ] **Step 6: `npm run build` + commit** `feat: apply org branding on login and app shell`

---

### Task 5: Appearance admin page

**Files:**
- Create: `web/src/views/admin/BrandingView.vue`
- Modify: `web/src/router/index.ts`, `web/src/layouts/AppShell.vue`
- Reuse: `admin-shared.css`

- [ ] **Step 1: Route** `{ path: "branding", name: "branding", component: BrandingView }`

- [ ] **Step 2: Nav** — show「外观」 only when `me.org_role === 'org_admin'`

- [ ] **Step 3: BrandingView UI**
  - Load GET branding into form
  - Preset buttons: default/ocean/slate/amber → set `preset_id` and clear color overrides (or keep overrides — prefer clear on preset click then user can retune)
  - Color mode select
  - Color inputs (type=color or hex text) for primary, bg, surface, text, muted
  - Logo file input + preview; upload on choose; delete button
  - product_name / tagline inputs
  - Live preview panel: mini login card + mini topbar using current form state via `applyBranding` on change (debounce) **or** scoped preview using inline styles on preview only (prefer preview-scoped so admin chrome not thrash — apply to `.preview-root` CSS variables)
  - Save → PUT then `applyBranding` globally

- [ ] **Step 4: `npm run build` + commit** `feat: add org appearance admin page`

---

### Task 6: Docs, compose volume, acceptance tests

**Files:**
- Modify: `README.md`
- Extend: `tests/test_branding.py` (two-org isolation if feasible)
- Verify: full pytest + build

- [ ] **Step 1: README** — document Appearance page, `TI_BRANDING_DATA_DIR`, volume

- [ ] **Step 2: Isolation test** — create second org via direct DB insert in test (or skip if no multi-org API); assert branding rows independent. Minimal: two `TiOrgBranding` rows different `product_name` via session in unit test.

- [ ] **Step 3:**

```bash
pytest -v
cd web && npm run build
```

- [ ] **Step 4: commit** `docs: white-label acceptance notes`

- [ ] **Step 5: Spec checklist** — tick §7 items in PR/description when finishing branch

---

## Self-review (plan vs spec)

| Spec item | Task |
|---|---|
| ti_org_branding + seed | 1 |
| presets + color resolve | 1 |
| GET/PUT branding + org_admin ACL | 2 |
| Logo upload + media + delete | 3 |
| applyBranding login/shell | 4 |
| Appearance page + nav | 5 |
| dark/system mode | 4–5 |
| Compose volume / README | 3, 6 |
| pytest + build | 2–6 |
| Fonts excluded | — |

**Type names locked:** `TiOrgBranding`, `BrandingOut`, `BrandingUpdate`, `PRESETS`, `resolve_branding_colors`, `applyBranding`, `logo_src`.

---
