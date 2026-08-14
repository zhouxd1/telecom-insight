<template>
  <div class="shell">
    <header class="topbar">
      <div class="brand">
        <img src="/logo.svg" alt="元景.智数" class="logo" />
        <div class="brand-text">
          <strong>元景.智数</strong>
          <span>运营商智能问数</span>
        </div>
      </div>
      <button type="button" class="logout" @click="logout">退出</button>
    </header>

    <div class="body">
      <aside class="sidenav" aria-label="主导航">
        <p class="nav-group">工作区</p>
        <RouterLink
          v-for="item in primaryNav"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          active-class="active"
        >
          <span class="nav-bar" aria-hidden="true" />
          {{ item.label }}
        </RouterLink>

        <p class="nav-group">即将推出</p>
        <button
          v-for="item in comingSoon"
          :key="item"
          type="button"
          class="nav-item disabled"
          disabled
          :title="`${item} · 即将推出`"
        >
          <span class="nav-bar muted" aria-hidden="true" />
          <span>{{ item }}</span>
          <em>即将推出</em>
        </button>
      </aside>

      <main class="content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { RouterLink, RouterView, useRouter } from "vue-router";
import { clearToken } from "../api";

const router = useRouter();

const primaryNav = [
  { to: "/app/chat", label: "问数工作台" },
  { to: "/app/models", label: "模型配置" },
  { to: "/app/terms", label: "术语库" },
  { to: "/app/examples", label: "SQL 示例" },
] as const;

const comingSoon = ["数据源", "工作空间", "用户"] as const;

function logout() {
  clearToken();
  void router.replace({ name: "login" });
}
</script>

<style scoped>
.shell {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: grid;
  grid-template-rows: 56px 1fr;
  background: var(--bg);
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0 1.5rem;
  border-bottom: 1px solid var(--line);
  background: var(--surface);
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.logo {
  width: 28px;
  height: 28px;
}

.brand-text {
  display: grid;
  line-height: 1.2;
  gap: 0.1rem;
}

.brand-text strong {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--ink);
  letter-spacing: 0.02em;
}

.brand-text span {
  font-size: 0.72rem;
  color: var(--muted);
  font-weight: 400;
}

.logout {
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--text);
  border-radius: var(--radius);
  padding: 0.4rem 0.85rem;
  font-size: 0.82rem;
  font-weight: 500;
  transition: background 120ms ease, border-color 120ms ease;
}

.logout:hover {
  background: var(--surface-muted);
  border-color: var(--line-strong);
}

.body {
  display: grid;
  grid-template-columns: 200px 1fr;
  min-height: 0;
}

.sidenav {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 1.25rem 0.75rem;
  background: var(--surface);
  border-right: 1px solid var(--line);
}

.nav-group {
  margin: 0.85rem 0.65rem 0.4rem;
  font-size: 0.68rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 500;
}

.nav-group:first-child {
  margin-top: 0;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.55rem 0.75rem;
  border-radius: var(--radius);
  text-decoration: none;
  color: var(--text);
  border: 0;
  background: transparent;
  text-align: left;
  font-size: 0.88rem;
  font-weight: 500;
  transition: background 120ms ease, color 120ms ease;
}

.nav-item:hover:not(.disabled) {
  background: var(--surface-muted);
}

.nav-item.active {
  background: var(--accent-soft);
  color: var(--accent-ink);
}

.nav-item.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.nav-item em {
  margin-left: auto;
  font-style: normal;
  font-size: 0.65rem;
  color: var(--muted);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 0.08rem 0.35rem;
  font-weight: 500;
}

.nav-bar {
  width: 3px;
  height: 14px;
  border-radius: 1px;
  background: transparent;
  flex-shrink: 0;
}

.nav-item.active .nav-bar {
  background: var(--accent);
}

.nav-bar.muted {
  background: var(--line-strong);
}

.content {
  min-width: 0;
  min-height: 0;
  background: var(--bg);
}

@media (max-width: 900px) {
  .body {
    grid-template-columns: 1fr;
  }

  .sidenav {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem;
    padding: 0.75rem;
  }

  .nav-group {
    width: 100%;
    margin: 0.25rem 0.4rem;
  }
}
</style>
