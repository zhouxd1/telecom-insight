<template>
  <section class="admin-page branding-page">
    <header class="page-head">
      <div>
        <h1>外观设置</h1>
        <p>配置组织品牌名称、主题色、Logo，并在右侧实时预览。</p>
      </div>
      <button
        v-if="isOrgAdmin"
        type="button"
        class="primary"
        :disabled="saving || loading"
        @click="onSave"
      >
        {{ saving ? "保存中…" : "保存" }}
      </button>
    </header>

    <p v-if="!isOrgAdmin && meLoaded" class="banner error" role="alert">
      仅组织管理员可管理外观设置。
    </p>
    <p v-if="error" class="banner error" role="alert">{{ error }}</p>
    <p v-if="note" class="banner ok">{{ note }}</p>

    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="!isOrgAdmin" class="empty">无权编辑组织外观。</div>

    <div v-else class="branding-layout">
      <form class="branding-form table-card" @submit.prevent="onSave">
        <fieldset class="block">
          <legend>品牌文案</legend>
          <label>
            <span>产品名称</span>
            <input v-model="form.product_name" type="text" maxlength="80" required />
          </label>
          <label>
            <span>副标题</span>
            <input v-model="form.tagline" type="text" maxlength="160" />
          </label>
        </fieldset>

        <fieldset class="block">
          <legend>预设主题</legend>
          <div class="preset-row" role="group" aria-label="预设主题">
            <button
              v-for="p in presetOptions"
              :key="p.id"
              type="button"
              class="preset-btn"
              :class="{ active: form.preset_id === p.id }"
              @click="applyPreset(p.id)"
            >
              <span class="swatch" :style="{ background: p.swatch }" />
              {{ p.label }}
            </button>
          </div>
        </fieldset>

        <fieldset class="block">
          <legend>色彩模式</legend>
          <label>
            <span>模式</span>
            <select v-model="form.color_mode">
              <option value="light">浅色</option>
              <option value="dark">深色</option>
              <option value="system">跟随系统</option>
            </select>
          </label>
        </fieldset>

        <fieldset class="block">
          <legend>颜色</legend>
          <div class="color-grid">
            <label v-for="field in colorFields" :key="field.key">
              <span>{{ field.label }}</span>
              <div class="color-row">
                <input
                  type="color"
                  :value="displayColor(field.key)"
                  :aria-label="field.label"
                  @input="onColorPicker(field.key, ($event.target as HTMLInputElement).value)"
                />
                <input
                  type="text"
                  class="hex"
                  :value="displayColor(field.key)"
                  :placeholder="field.placeholder"
                  maxlength="7"
                  @change="onColorHex(field.key, ($event.target as HTMLInputElement).value)"
                />
                <button
                  v-if="form[field.key]"
                  type="button"
                  class="ghost"
                  @click="clearColor(field.key)"
                >
                  重置
                </button>
              </div>
            </label>
          </div>
        </fieldset>

        <fieldset class="block">
          <legend>Logo</legend>
          <div class="asset-row">
            <img
              v-if="logoPreview"
              :src="logoPreview"
              alt="Logo 预览"
              class="asset-preview"
            />
            <div class="asset-actions">
              <label class="file-btn">
                <span>上传 Logo</span>
                <input
                  type="file"
                  accept="image/png,image/svg+xml,image/webp"
                  :disabled="uploadingLogo"
                  @change="onLogoFile"
                />
              </label>
              <button
                type="button"
                class="danger"
                :disabled="uploadingLogo || !form.logo_src"
                @click="onDeleteLogo"
              >
                删除上传
              </button>
            </div>
          </div>
        </fieldset>

        <fieldset class="block">
          <legend>Favicon（可选）</legend>
          <div class="asset-row">
            <img
              v-if="faviconPreview"
              :src="faviconPreview"
              alt="Favicon 预览"
              class="asset-preview favicon"
            />
            <div class="asset-actions">
              <label class="file-btn">
                <span>上传 Favicon</span>
                <input
                  type="file"
                  accept="image/png,image/svg+xml,image/webp,image/x-icon,image/vnd.microsoft.icon"
                  :disabled="uploadingFavicon"
                  @change="onFaviconFile"
                />
              </label>
              <button
                type="button"
                class="danger"
                :disabled="uploadingFavicon || !form.favicon_src"
                @click="onDeleteFavicon"
              >
                删除上传
              </button>
            </div>
          </div>
        </fieldset>
      </form>

      <aside class="preview-panel table-card" aria-label="实时预览">
        <h2>实时预览</h2>
        <div ref="previewRoot" class="preview-root" :data-theme="previewMode">
          <div class="mini-topbar">
            <img :src="logoPreview" alt="" class="mini-logo" />
            <div class="mini-brand">
              <strong>{{ form.product_name || "产品名称" }}</strong>
              <span>{{ form.tagline || "副标题" }}</span>
            </div>
          </div>
          <div class="mini-login">
            <div class="mini-login-card">
              <img :src="logoPreview" alt="" class="mini-hero-logo" />
              <h3>{{ form.product_name || "产品名称" }}</h3>
              <p>{{ form.tagline || "副标题" }}</p>
              <div class="mini-field" />
              <div class="mini-field" />
              <button type="button" class="mini-cta" tabindex="-1">进入工作台</button>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, onMounted, onUnmounted, reactive, ref, watch, type Ref } from "vue";
import {
  deleteBrandingFavicon,
  deleteBrandingLogo,
  fetchMe,
  fetchOrgBranding,
  friendlyError,
  updateOrgBranding,
  uploadBrandingFavicon,
  uploadBrandingLogo,
  type BrandingUpdatePayload,
  type MeResponse,
} from "../../api";
import {
  applyBranding,
  resolveBrandingColors,
  resolveEffectiveMode,
  resolvePublicAssetUrl,
  type Branding,
} from "../../branding";
import { BRANDING_PRESETS, type BrandingColorKeys } from "../../brandingPresets";

type ColorFieldKey = BrandingColorKeys;

const COLOR_KEYS: ColorFieldKey[] = [
  "primary",
  "primary_soft",
  "bg",
  "surface",
  "text",
  "muted",
];

const colorFields: { key: ColorFieldKey; label: string; placeholder: string }[] = [
  { key: "primary", label: "主色", placeholder: "#0d9488" },
  { key: "primary_soft", label: "柔和主色", placeholder: "#ecfdf8" },
  { key: "bg", label: "背景", placeholder: "#f5f6f8" },
  { key: "surface", label: "表面", placeholder: "#ffffff" },
  { key: "text", label: "正文", placeholder: "#2c313a" },
  { key: "muted", label: "次要文字", placeholder: "#6b7280" },
];

const presetOptions = [
  { id: "default", label: "默认", swatch: BRANDING_PRESETS.default.light.primary },
  { id: "ocean", label: "海洋", swatch: BRANDING_PRESETS.ocean.light.primary },
  { id: "slate", label: "岩灰", swatch: BRANDING_PRESETS.slate.light.primary },
  { id: "amber", label: "琥珀", swatch: BRANDING_PRESETS.amber.light.primary },
] as const;

const reloadBranding = inject<(() => Promise<void>) | undefined>("reloadBranding");
const shellBranding = inject<Ref<Branding | null> | undefined>("branding");
const meInject = inject<Ref<MeResponse | null> | undefined>("me");

const loading = ref(true);
const saving = ref(false);
const uploadingLogo = ref(false);
const uploadingFavicon = ref(false);
const error = ref("");
const note = ref("");
const meLoaded = ref(false);
const isOrgAdmin = ref(false);
const previewRoot = ref<HTMLElement | null>(null);

const form = reactive({
  product_name: "",
  tagline: "",
  preset_id: "default",
  color_mode: "light",
  primary: "",
  primary_soft: "",
  bg: "",
  surface: "",
  text: "",
  muted: "",
  logo_src: "/logo.svg",
  favicon_src: "/logo.svg",
});

let previewTimer: ReturnType<typeof setTimeout> | null = null;
let noteTimer: ReturnType<typeof setTimeout> | null = null;

const draftBranding = computed((): Branding => ({
  product_name: form.product_name.trim() || "元景.智数",
  tagline: form.tagline.trim(),
  logo_src: form.logo_src || "/logo.svg",
  favicon_src: form.favicon_src || "/logo.svg",
  preset_id: form.preset_id || "default",
  color_mode: form.color_mode || "light",
  colors: {},
  primary: form.primary.trim() || null,
  primary_soft: form.primary_soft.trim() || null,
  bg: form.bg.trim() || null,
  surface: form.surface.trim() || null,
  text: form.text.trim() || null,
  muted: form.muted.trim() || null,
}));

const previewMode = computed(() => resolveEffectiveMode(form.color_mode));

const effectiveColors = computed(() =>
  resolveBrandingColors(draftBranding.value, previewMode.value),
);

const logoPreview = computed(() => resolvePublicAssetUrl(form.logo_src || "/logo.svg"));
const faviconPreview = computed(() =>
  resolvePublicAssetUrl(form.favicon_src || "/logo.svg"),
);

function displayColor(key: ColorFieldKey): string {
  const raw = form[key].trim() || effectiveColors.value[key];
  return normalizeHex(raw) || "#000000";
}

function normalizeHex(value: string): string {
  const v = value.trim();
  if (/^#[0-9a-fA-F]{6}$/.test(v)) return v.toLowerCase();
  if (/^#[0-9a-fA-F]{3}$/.test(v)) {
    const r = v[1];
    const g = v[2];
    const b = v[3];
    return `#${r}${r}${g}${g}${b}${b}`.toLowerCase();
  }
  return "";
}

function onColorPicker(key: ColorFieldKey, value: string) {
  form[key] = normalizeHex(value) || value;
}

function onColorHex(key: ColorFieldKey, value: string) {
  const hex = normalizeHex(value);
  if (hex) form[key] = hex;
}

function clearColor(key: ColorFieldKey) {
  form[key] = "";
}

function applyPreset(id: string) {
  form.preset_id = id;
  for (const key of COLOR_KEYS) {
    form[key] = "";
  }
}

function applyPreviewScoped() {
  const el = previewRoot.value;
  if (!el) return;
  const colors = effectiveColors.value;
  el.style.setProperty("--accent", colors.primary);
  el.style.setProperty("--accent-soft", colors.primary_soft);
  el.style.setProperty("--accent-ink", colors.primary);
  el.style.setProperty("--bg", colors.bg);
  el.style.setProperty("--surface", colors.surface);
  el.style.setProperty("--text", colors.text);
  el.style.setProperty("--ink", colors.text);
  el.style.setProperty("--muted", colors.muted);
}

function schedulePreview() {
  if (previewTimer) clearTimeout(previewTimer);
  previewTimer = setTimeout(() => {
    applyPreviewScoped();
  }, 80);
}

function showNote(msg: string) {
  note.value = msg;
  if (noteTimer) clearTimeout(noteTimer);
  noteTimer = setTimeout(() => {
    note.value = "";
  }, 3200);
}

function hydrate(b: Branding) {
  form.product_name = b.product_name || "";
  form.tagline = b.tagline || "";
  form.preset_id = b.preset_id || "default";
  form.color_mode = b.color_mode || "light";
  form.primary = (b.primary || "").trim();
  form.primary_soft = (b.primary_soft || "").trim();
  form.bg = (b.bg || "").trim();
  form.surface = (b.surface || "").trim();
  form.text = (b.text || "").trim();
  form.muted = (b.muted || "").trim();
  form.logo_src = b.logo_src || "/logo.svg";
  form.favicon_src = b.favicon_src || "/logo.svg";
}

/** Keep unsaved draft fields; only refresh asset URLs from server response. */
function mergeAssetsFrom(saved: Branding) {
  form.logo_src = saved.logo_src || "/logo.svg";
  form.favicon_src = saved.favicon_src || "/logo.svg";
}

function buildUpdatePayload(): BrandingUpdatePayload {
  return {
    product_name: form.product_name.trim(),
    tagline: form.tagline.trim(),
    preset_id: form.preset_id,
    color_mode: form.color_mode,
    primary: form.primary.trim() || null,
    primary_soft: form.primary_soft.trim() || null,
    bg: form.bg.trim() || null,
    surface: form.surface.trim() || null,
    text: form.text.trim() || null,
    muted: form.muted.trim() || null,
  };
}

async function syncShell(b: Branding) {
  applyBranding(b);
  if (shellBranding) {
    shellBranding.value = b;
  } else if (reloadBranding) {
    await reloadBranding();
  }
}

/** Shell logo/favicon from server assets + current draft theme/copy. */
function shellBrandingFromDraft(savedAssets: Branding): Branding {
  return {
    ...draftBranding.value,
    logo_src: savedAssets.logo_src || draftBranding.value.logo_src,
    favicon_src: savedAssets.favicon_src || draftBranding.value.favicon_src,
  };
}

async function resolveAdminAccess() {
  try {
    const role = meInject?.value?.org_role ?? (await fetchMe()).org_role;
    isOrgAdmin.value = role === "org_admin";
  } catch (err) {
    error.value = friendlyError(err);
    isOrgAdmin.value = false;
  } finally {
    meLoaded.value = true;
  }
}

async function refresh() {
  if (!isOrgAdmin.value) {
    loading.value = false;
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const b = await fetchOrgBranding();
    hydrate(b);
    await nextTick();
    applyPreviewScoped();
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  if (!isOrgAdmin.value) return;
  saving.value = true;
  error.value = "";
  try {
    const saved = await updateOrgBranding(buildUpdatePayload());
    hydrate(saved);
    await syncShell(saved);
    showNote("外观已保存并应用。");
    await nextTick();
    applyPreviewScoped();
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    saving.value = false;
  }
}

async function onLogoFile(event: Event) {
  if (!isOrgAdmin.value) return;
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  uploadingLogo.value = true;
  error.value = "";
  try {
    const saved = await uploadBrandingLogo(file);
    mergeAssetsFrom(saved);
    await syncShell(shellBrandingFromDraft(saved));
    showNote("Logo 已上传。");
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    uploadingLogo.value = false;
  }
}

async function onDeleteLogo() {
  if (!isOrgAdmin.value) return;
  if (!window.confirm("确认删除已上传的 Logo？")) return;
  uploadingLogo.value = true;
  error.value = "";
  try {
    const saved = await deleteBrandingLogo();
    mergeAssetsFrom(saved);
    await syncShell(shellBrandingFromDraft(saved));
    showNote("Logo 已删除。");
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    uploadingLogo.value = false;
  }
}

async function onFaviconFile(event: Event) {
  if (!isOrgAdmin.value) return;
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  uploadingFavicon.value = true;
  error.value = "";
  try {
    const saved = await uploadBrandingFavicon(file);
    mergeAssetsFrom(saved);
    await syncShell(shellBrandingFromDraft(saved));
    showNote("Favicon 已上传。");
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    uploadingFavicon.value = false;
  }
}

async function onDeleteFavicon() {
  if (!isOrgAdmin.value) return;
  if (!window.confirm("确认删除已上传的 Favicon？")) return;
  uploadingFavicon.value = true;
  error.value = "";
  try {
    const saved = await deleteBrandingFavicon();
    mergeAssetsFrom(saved);
    await syncShell(shellBrandingFromDraft(saved));
    showNote("Favicon 已删除。");
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    uploadingFavicon.value = false;
  }
}

watch(draftBranding, () => schedulePreview(), { deep: true });

onMounted(async () => {
  await resolveAdminAccess();
  if (isOrgAdmin.value) {
    await refresh();
  } else {
    loading.value = false;
  }
});

onUnmounted(() => {
  if (previewTimer) clearTimeout(previewTimer);
  if (noteTimer) clearTimeout(noteTimer);
});
</script>

<style src="./admin-shared.css"></style>

<style scoped>
.branding-page {
  max-width: 1180px;
}

.branding-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(280px, 0.85fr);
  gap: 1rem;
  align-items: start;
}

.branding-form {
  display: grid;
  gap: 0;
  padding: 0.35rem 0;
  overflow: hidden;
}

.block {
  margin: 0;
  padding: 1rem 1.1rem 1.15rem;
  border: 0;
  border-bottom: 1px solid var(--line);
  display: grid;
  gap: 0.75rem;
}

.block:last-child {
  border-bottom: 0;
}

.block legend {
  padding: 0;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--muted);
  letter-spacing: 0.02em;
}

.block label {
  display: grid;
  gap: 0.3rem;
}

.block label > span {
  font-size: 0.78rem;
  color: var(--muted);
  font-weight: 500;
}

.block input[type="text"],
.block select {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 0.5rem 0.7rem;
  background: var(--surface);
  color: var(--text);
  font-size: 0.86rem;
}

.block input:focus,
.block select:focus {
  outline: none;
  border-color: var(--accent);
}

.preset-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.preset-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--text);
  border-radius: var(--radius);
  padding: 0.4rem 0.7rem;
  font-size: 0.82rem;
  font-weight: 500;
}

.preset-btn:hover {
  background: var(--surface-muted);
}

.preset-btn.active {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent-ink);
}

.swatch {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}

.color-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem 1rem;
}

.color-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.color-row input[type="color"] {
  width: 2.1rem;
  height: 2.1rem;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  cursor: pointer;
}

.color-row .hex {
  flex: 1;
  min-width: 0;
  font-family: var(--mono);
  font-size: 0.8rem;
}

.asset-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.asset-preview {
  width: 48px;
  height: 48px;
  object-fit: contain;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface-muted);
  padding: 0.25rem;
}

.asset-preview.favicon {
  width: 32px;
  height: 32px;
}

.asset-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
}

.file-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 0.35rem 0.65rem;
  font-size: 0.8rem;
  font-weight: 500;
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
}

.file-btn:hover {
  background: var(--surface-muted);
}

.file-btn input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.preview-panel {
  padding: 1rem 1.1rem 1.15rem;
  position: sticky;
  top: 0.75rem;
}

.preview-panel h2 {
  margin: 0 0 0.85rem;
  font-size: 0.86rem;
  font-weight: 600;
  color: var(--ink);
}

.preview-root {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--bg);
  color: var(--text);
}

.mini-topbar {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.55rem 0.75rem;
  background: var(--surface);
  border-bottom: 1px solid color-mix(in srgb, var(--muted) 28%, transparent);
}

.mini-logo {
  width: 22px;
  height: 22px;
  object-fit: contain;
}

.mini-brand {
  display: grid;
  gap: 0.05rem;
  line-height: 1.2;
  min-width: 0;
}

.mini-brand strong {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-brand span {
  font-size: 0.65rem;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-login {
  padding: 1.1rem 0.85rem 1.25rem;
  background: var(--bg);
  display: grid;
  place-items: center;
}

.mini-login-card {
  width: 100%;
  max-width: 220px;
  padding: 1rem 0.9rem 1.05rem;
  border-radius: var(--radius-lg);
  background: var(--surface);
  border: 1px solid color-mix(in srgb, var(--muted) 28%, transparent);
  box-shadow: var(--shadow-sm);
  text-align: center;
}

.mini-hero-logo {
  width: 36px;
  height: 36px;
  object-fit: contain;
  margin-bottom: 0.35rem;
}

.mini-login-card h3 {
  margin: 0;
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--ink);
}

.mini-login-card > p {
  margin: 0.25rem 0 0.85rem;
  font-size: 0.72rem;
  color: var(--muted);
}

.mini-field {
  height: 1.55rem;
  margin-bottom: 0.45rem;
  border-radius: var(--radius);
  border: 1px solid color-mix(in srgb, var(--muted) 28%, transparent);
  background: var(--bg);
}

.mini-cta {
  width: 100%;
  margin-top: 0.35rem;
  border: 1px solid var(--accent);
  border-radius: var(--radius);
  background: var(--accent-soft);
  color: var(--accent-ink);
  font-size: 0.78rem;
  font-weight: 600;
  padding: 0.4rem 0.5rem;
  pointer-events: none;
}

@media (max-width: 960px) {
  .branding-layout {
    grid-template-columns: 1fr;
  }

  .preview-panel {
    position: static;
  }

  .color-grid {
    grid-template-columns: 1fr;
  }
}
</style>
