<template>
  <div class="shell">
    <header class="topbar">
      <div class="brand">
        <img src="/logo.svg" alt="元景.智数" class="logo" />
        <div class="brand-text">
          <strong>元景.智数</strong>
          <span>电信域 ChatBI</span>
        </div>
      </div>
      <button type="button" class="logout" @click="logout">退出登录</button>
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
          <span class="nav-dot" aria-hidden="true" />
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
          <span class="nav-dot muted" aria-hidden="true" />
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
  grid-template-rows: auto 1fr;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.7rem 1.25rem;
  border-bottom: 1px solid rgba(232, 241, 240, 0.12);
  background: linear-gradient(90deg, #07151d 0%, #0b1f2a 55%, #0d2a30 100%);
  color: #e8f5f2;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.logo {
  width: 36px;
  height: 36px;
  filter: drop-shadow(0 4px 12px rgba(20, 184, 166, 0.35));
}

.brand-text {
  display: grid;
  line-height: 1.2;
}

.brand-text strong {
  font-size: 1.05rem;
  letter-spacing: 0.04em;
  font-weight: 700;
}

.brand-text span {
  font-size: 0.75rem;
  color: rgba(232, 245, 242, 0.62);
}

.logout {
  border: 1px solid rgba(232, 241, 240, 0.22);
  background: rgba(255, 255, 255, 0.04);
  color: #e8f5f2;
  border-radius: 999px;
  padding: 0.4rem 0.95rem;
  font-size: 0.85rem;
  transition: background 140ms ease, border-color 140ms ease;
}

.logout:hover {
  background: rgba(20, 184, 166, 0.16);
  border-color: rgba(20, 184, 166, 0.45);
}

.body {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: 0;
}

.sidenav {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  padding: 1rem 0.75rem;
  background: rgba(7, 21, 29, 0.92);
  border-right: 1px solid rgba(232, 241, 240, 0.08);
  color: #d7e8e4;
}

.nav-group {
  margin: 0.65rem 0.65rem 0.35rem;
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(215, 232, 228, 0.45);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.62rem 0.7rem;
  border-radius: 10px;
  text-decoration: none;
  color: rgba(232, 245, 242, 0.82);
  border: 0;
  background: transparent;
  text-align: left;
  font-size: 0.92rem;
  transition: background 140ms ease, color 140ms ease;
}

.nav-item:hover:not(.disabled) {
  background: rgba(20, 184, 166, 0.12);
  color: #fff;
}

.nav-item.active {
  background: linear-gradient(135deg, rgba(15, 118, 110, 0.55), rgba(20, 184, 166, 0.28));
  color: #fff;
  box-shadow: inset 0 0 0 1px rgba(20, 184, 166, 0.35);
}

.nav-item.disabled {
  opacity: 0.48;
  cursor: not-allowed;
}

.nav-item em {
  margin-left: auto;
  font-style: normal;
  font-size: 0.68rem;
  color: rgba(232, 245, 242, 0.5);
  border: 1px solid rgba(232, 245, 242, 0.18);
  border-radius: 999px;
  padding: 0.1rem 0.4rem;
}

.nav-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--teal-bright);
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.18);
}

.nav-dot.muted {
  background: rgba(232, 245, 242, 0.35);
  box-shadow: none;
}

.content {
  min-width: 0;
  min-height: 0;
  background: linear-gradient(180deg, #f3f8f7 0%, #e9f1f0 100%);
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
    padding: 0.65rem;
  }

  .nav-group {
    width: 100%;
    margin: 0.2rem 0.4rem;
  }
}
</style>
