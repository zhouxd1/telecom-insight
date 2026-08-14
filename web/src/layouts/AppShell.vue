<template>
  <div class="shell">
    <header class="topbar">
      <div class="brand">
        <img src="/logo.svg" alt="元景.智数" class="logo" />
        <div class="brand-text">
          <strong>元景.智数</strong>
          <span>{{ me?.org_name || "运营商智能问数" }}</span>
        </div>
        <span v-if="me" class="role-badge" :title="roleLabel">{{ me.org_role }}</span>
      </div>

      <div class="topbar-actions">
        <label class="workspace-switcher">
          <span class="sr-only">工作空间</span>
          <select
            :value="workspaceId ?? ''"
            :disabled="!workspaces.length"
            @change="onWorkspaceChange"
          >
            <option v-if="!workspaces.length" value="" disabled>无可用空间</option>
            <option v-for="ws in workspaces" :key="ws.id" :value="ws.id">
              {{ ws.name }}
            </option>
          </select>
        </label>
        <button type="button" class="logout" @click="logout">退出</button>
      </div>
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
      </aside>

      <main class="content">
        <RouterView :key="workspaceId ?? 'none'" />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, provide, ref, type Ref } from "vue";
import { RouterLink, RouterView, useRouter } from "vue-router";
import {
  clearToken,
  fetchMe,
  getWorkspaceId,
  setWorkspaceId as persistWorkspaceId,
  type MeResponse,
} from "../api";

const router = useRouter();

const me = ref<MeResponse | null>(null);
const workspaceId = ref<number | null>(getWorkspaceId());

const meRef = me as Ref<MeResponse | null>;
provide("me", meRef);
provide("workspaceId", workspaceId);

const workspaces = computed(() => me.value?.workspaces ?? []);

const roleLabel = computed(() => {
  const role = me.value?.org_role;
  if (role === "org_admin") return "组织管理员";
  if (role === "analyst") return "分析师";
  if (role === "viewer") return "只读";
  return role || "";
});

const primaryNav = [
  { to: "/app/chat", label: "问数工作台" },
  { to: "/app/datasources", label: "数据源" },
  { to: "/app/workspaces", label: "工作空间" },
  { to: "/app/users", label: "用户" },
  { to: "/app/models", label: "模型配置" },
  { to: "/app/terms", label: "术语库" },
  { to: "/app/examples", label: "SQL 示例" },
] as const;

async function loadMe() {
  me.value = await fetchMe();
  const list = me.value.workspaces;
  if (!list.length) {
    workspaceId.value = null;
    persistWorkspaceId(null);
    return;
  }
  const current = workspaceId.value;
  const stillValid = current != null && list.some((w) => w.id === current);
  if (!stillValid) {
    workspaceId.value = list[0].id;
    persistWorkspaceId(list[0].id);
  }
}

function onWorkspaceChange(event: Event) {
  const select = event.target as HTMLSelectElement;
  const id = Number(select.value);
  if (!Number.isFinite(id)) return;
  workspaceId.value = id;
  persistWorkspaceId(id);
}

function logout() {
  clearToken();
  persistWorkspaceId(null);
  void router.replace({ name: "login" });
}

onMounted(() => {
  void loadMe();
});
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
  min-width: 0;
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

.role-badge {
  flex-shrink: 0;
  margin-left: 0.15rem;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface-muted);
  color: var(--muted);
  font-size: 0.68rem;
  font-weight: 500;
  padding: 0.15rem 0.45rem;
  letter-spacing: 0.02em;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.workspace-switcher select {
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--text);
  border-radius: var(--radius);
  padding: 0.4rem 0.65rem;
  font-size: 0.82rem;
  font-weight: 500;
  min-width: 9rem;
  max-width: 16rem;
}

.workspace-switcher select:hover:not(:disabled) {
  border-color: var(--line-strong);
}

.workspace-switcher select:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
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

.nav-item:hover {
  background: var(--surface-muted);
}

.nav-item.active {
  background: var(--accent-soft);
  color: var(--accent-ink);
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

  .topbar {
    flex-wrap: wrap;
    height: auto;
    padding: 0.65rem 1rem;
  }

  .workspace-switcher select {
    min-width: 7rem;
  }
}
</style>
