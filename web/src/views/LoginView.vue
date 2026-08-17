<template>
  <main class="login-page">
    <section class="login-card">
      <div class="hero-brand">
        <div class="logo-block">
          <img :src="logoSrc" :alt="productName" class="hero-logo" />
        </div>
        <h1>{{ productName }}</h1>
        <p>{{ tagline }}</p>
      </div>

      <form class="login-form" @submit.prevent="onSubmit">
        <label>
          <span>账号</span>
          <input v-model="username" type="text" autocomplete="username" placeholder="demo" />
        </label>
        <label>
          <span>密码</span>
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            placeholder="demo123"
          />
        </label>

        <p v-if="error" class="error" role="alert">{{ error }}</p>

        <button type="submit" :disabled="loading">
          {{ loading ? "登录中…" : "进入工作台" }}
        </button>
      </form>

      <p class="hint">演示账号 demo / demo123</p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { fetchDefaultBranding, friendlyError, login } from "../api";
import {
  applyBranding,
  DEFAULT_BRANDING,
  resolveMediaUrl,
  type Branding,
} from "../branding";

const router = useRouter();
const username = ref("demo");
const password = ref("demo123");
const loading = ref(false);
const error = ref("");
const branding = ref<Branding>({ ...DEFAULT_BRANDING });

const productName = computed(() => branding.value.product_name || DEFAULT_BRANDING.product_name);
const tagline = computed(() => branding.value.tagline || DEFAULT_BRANDING.tagline);
const logoSrc = computed(() =>
  resolveMediaUrl(branding.value.logo_src || DEFAULT_BRANDING.logo_src),
);

async function loadBranding() {
  try {
    const data = await fetchDefaultBranding();
    branding.value = data;
    applyBranding(data);
  } catch {
    branding.value = { ...DEFAULT_BRANDING };
    applyBranding(DEFAULT_BRANDING);
  }
}

async function onSubmit() {
  error.value = "";
  loading.value = true;
  try {
    await login(username.value.trim(), password.value);
    await router.replace({ name: "chat" });
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadBranding();
});
</script>

<style scoped>
.login-page {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 2.5rem 1.25rem;
  background: var(--bg);
}

.login-card {
  width: min(400px, 100%);
  padding: 2.5rem 2rem 2rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--line);
  background: var(--surface);
  box-shadow: var(--shadow);
}

.hero-brand {
  text-align: center;
  margin-bottom: 2rem;
}

.logo-block {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  margin-bottom: 1rem;
  border-radius: var(--radius);
  background: var(--accent-soft);
  border: 1px solid var(--line);
}

.hero-logo {
  width: 32px;
  height: 32px;
}

.hero-brand h1 {
  margin: 0;
  font-size: 1.65rem;
  letter-spacing: 0.04em;
  color: var(--ink);
  font-weight: 600;
}

.hero-brand p {
  margin: 0.4rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
  font-weight: 400;
}

.login-form {
  display: grid;
  gap: 1rem;
}

label {
  display: grid;
  gap: 0.4rem;
}

label span {
  font-size: 0.8rem;
  color: var(--muted);
  font-weight: 500;
}

input {
  width: 100%;
  padding: 0.7rem 0.85rem;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  outline: none;
  transition: border-color 120ms ease;
}

input:focus {
  border-color: var(--accent);
}

button[type="submit"] {
  margin-top: 0.35rem;
  border: 1px solid var(--accent);
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
  background: var(--accent-soft);
  color: var(--accent-ink);
  font-weight: 600;
  font-size: 0.9rem;
  transition: background 120ms ease, opacity 120ms ease, border-color 120ms ease;
}

button[type="submit"]:hover:not(:disabled) {
  background: color-mix(in srgb, var(--accent-soft) 72%, var(--accent) 28%);
  border-color: var(--accent-ink);
}

button[type="submit"]:disabled {
  opacity: 0.55;
  cursor: wait;
}

.error {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}

.hint {
  margin: 1.25rem 0 0;
  text-align: center;
  color: var(--muted);
  font-size: 0.78rem;
}
</style>
