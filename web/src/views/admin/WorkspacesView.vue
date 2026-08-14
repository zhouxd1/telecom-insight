<template>
  <section class="admin-page">
    <header class="page-head">
      <div>
        <h1>工作空间</h1>
        <p>管理组织下的工作空间与成员（角色 / 业务域）。</p>
      </div>
      <button
        v-if="isOrgAdmin"
        type="button"
        class="primary"
        @click="openCreate"
      >
        新建工作空间
      </button>
    </header>

    <p v-if="!isOrgAdmin && meLoaded" class="banner ok">
      当前账号非组织管理员，仅可查看已加入的工作空间。
    </p>
    <p v-if="error" class="banner error" role="alert">{{ error }}</p>
    <p v-if="note" class="banner ok">{{ note }}</p>

    <div class="table-card">
      <div v-if="loading" class="empty">加载中…</div>
      <div v-else-if="!rows.length" class="empty">暂无工作空间。</div>
      <table v-else>
        <thead>
          <tr>
            <th>名称</th>
            <th>状态</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td>{{ row.name }}</td>
            <td>
              <span class="pill" :class="{ on: row.status === 'active' }">{{
                row.status === "active" ? "活跃" : "已归档"
              }}</span>
            </td>
            <td class="mono">{{ formatTime(row.created_at) }}</td>
            <td class="actions">
              <button
                v-if="isOrgAdmin"
                type="button"
                @click="openMembers(row)"
              >
                成员
              </button>
              <button
                v-if="isOrgAdmin && row.status === 'active'"
                type="button"
                class="danger"
                @click="onArchive(row)"
              >
                归档
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="createOpen" class="modal-backdrop" @click.self="closeCreate">
      <form class="modal" @submit.prevent="onCreate">
        <h2>新建工作空间</h2>
        <label>
          <span>名称</span>
          <input v-model="createName" required />
        </label>
        <div class="modal-actions">
          <button type="button" class="ghost" @click="closeCreate">取消</button>
          <button type="submit" class="primary" :disabled="saving">
            {{ saving ? "创建中…" : "创建" }}
          </button>
        </div>
      </form>
    </div>

    <div v-if="memberOpen" class="drawer-backdrop" @click.self="closeMembers">
      <aside class="drawer" role="dialog" aria-label="工作空间成员">
        <header class="drawer-head">
          <div>
            <h2>成员 · {{ memberWorkspace?.name }}</h2>
            <p>添加用户并设置角色与业务域权限。</p>
          </div>
          <button type="button" class="ghost" @click="closeMembers">关闭</button>
        </header>

        <p v-if="memberError" class="banner error" role="alert">{{ memberError }}</p>

        <form class="member-form" @submit.prevent="onAddMember">
          <label>
            <span>用户</span>
            <select v-model.number="memberForm.user_id" required>
              <option :value="0" disabled>选择用户</option>
              <option
                v-for="u in availableUsers"
                :key="u.id"
                :value="u.id"
              >
                {{ u.display_name || u.username }}（{{ u.username }}）
              </option>
            </select>
          </label>
          <label>
            <span>角色</span>
            <select v-model="memberForm.role" required>
              <option value="org_admin">org_admin</option>
              <option value="analyst">analyst</option>
              <option value="viewer">viewer</option>
            </select>
          </label>
          <fieldset class="domains">
            <legend>业务域</legend>
            <label v-for="d in domainOptions" :key="d.id" class="check">
              <input v-model="memberForm.domains" type="checkbox" :value="d.id" />
              <span>{{ d.label }}</span>
            </label>
          </fieldset>
          <button type="submit" class="primary" :disabled="memberSaving || !memberForm.user_id">
            {{ memberSaving ? "添加中…" : "添加成员" }}
          </button>
        </form>

        <div class="table-card member-table">
          <div v-if="memberLoading" class="empty">加载中…</div>
          <div v-else-if="!members.length" class="empty">暂无成员。</div>
          <table v-else>
            <thead>
              <tr>
                <th>用户</th>
                <th>角色</th>
                <th>业务域</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in members" :key="m.id">
                <td>{{ userLabel(m.user_id) }}</td>
                <td>{{ m.role }}</td>
                <td>{{ (m.domains || []).map(domainLabel).join("、") || "—" }}</td>
                <td class="actions">
                  <button type="button" class="danger" @click="onRemoveMember(m)">移除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  addMember,
  archiveWorkspace,
  createWorkspace,
  fetchMe,
  friendlyError,
  listMembers,
  listUsers,
  listWorkspaces,
  removeMember,
  type OrgUser,
  type Workspace,
  type WorkspaceMember,
} from "../../api";

const domainOptions = [
  { id: "biz", label: "经营" },
  { id: "network", label: "网络" },
  { id: "cs", label: "客服" },
] as const;

const rows = ref<Workspace[]>([]);
const users = ref<OrgUser[]>([]);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const note = ref("");
const meLoaded = ref(false);
const isOrgAdmin = ref(false);

const createOpen = ref(false);
const createName = ref("");

const memberOpen = ref(false);
const memberWorkspace = ref<Workspace | null>(null);
const members = ref<WorkspaceMember[]>([]);
const memberLoading = ref(false);
const memberSaving = ref(false);
const memberError = ref("");

const memberForm = reactive({
  user_id: 0,
  role: "analyst",
  domains: ["biz", "network", "cs"] as string[],
});

const availableUsers = computed(() => {
  const memberIds = new Set(members.value.map((m) => m.user_id));
  return users.value.filter((u) => u.enabled && !memberIds.has(u.id));
});

function domainLabel(id: string): string {
  return domainOptions.find((d) => d.id === id)?.label ?? id;
}

function userLabel(userId: number): string {
  const u = users.value.find((x) => x.id === userId);
  if (!u) return `#${userId}`;
  return u.display_name ? `${u.display_name}（${u.username}）` : u.username;
}

function formatTime(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
}

async function loadMe() {
  try {
    const me = await fetchMe();
    isOrgAdmin.value = me.org_role === "org_admin";
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    meLoaded.value = true;
  }
}

async function refresh() {
  loading.value = true;
  error.value = "";
  try {
    rows.value = await listWorkspaces();
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  createName.value = "";
  createOpen.value = true;
}

function closeCreate() {
  createOpen.value = false;
}

async function onCreate() {
  saving.value = true;
  error.value = "";
  note.value = "";
  try {
    await createWorkspace({ name: createName.value.trim() });
    createOpen.value = false;
    note.value = "工作空间已创建。";
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    saving.value = false;
  }
}

async function onArchive(row: Workspace) {
  if (!window.confirm(`确认归档工作空间「${row.name}」？`)) return;
  error.value = "";
  note.value = "";
  try {
    await archiveWorkspace(row.id);
    note.value = `已归档「${row.name}」。`;
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  }
}

async function openMembers(row: Workspace) {
  memberWorkspace.value = row;
  memberOpen.value = true;
  memberError.value = "";
  memberForm.user_id = 0;
  memberForm.role = "analyst";
  memberForm.domains = ["biz", "network", "cs"];
  memberLoading.value = true;
  try {
    const [memberRows, userRows] = await Promise.all([
      listMembers(row.id),
      listUsers(),
    ]);
    members.value = memberRows;
    users.value = userRows;
  } catch (err) {
    memberError.value = friendlyError(err);
  } finally {
    memberLoading.value = false;
  }
}

function closeMembers() {
  memberOpen.value = false;
  memberWorkspace.value = null;
}

async function onAddMember() {
  if (!memberWorkspace.value || !memberForm.user_id) return;
  memberSaving.value = true;
  memberError.value = "";
  try {
    await addMember(memberWorkspace.value.id, {
      user_id: memberForm.user_id,
      role: memberForm.role,
      domains: [...memberForm.domains],
    });
    members.value = await listMembers(memberWorkspace.value.id);
    memberForm.user_id = 0;
    note.value = "成员已添加。";
  } catch (err) {
    memberError.value = friendlyError(err);
  } finally {
    memberSaving.value = false;
  }
}

async function onRemoveMember(m: WorkspaceMember) {
  if (!memberWorkspace.value) return;
  if (!window.confirm(`确认移除成员 ${userLabel(m.user_id)}？`)) return;
  memberError.value = "";
  try {
    await removeMember(memberWorkspace.value.id, m.user_id);
    members.value = await listMembers(memberWorkspace.value.id);
    note.value = "成员已移除。";
  } catch (err) {
    memberError.value = friendlyError(err);
  }
}

onMounted(async () => {
  await loadMe();
  await refresh();
});
</script>

<style src="./admin-shared.css"></style>
<style scoped>
.drawer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: flex;
  justify-content: flex-end;
  background: rgba(26, 29, 36, 0.28);
}

.drawer {
  width: min(440px, 100%);
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 1.25rem;
  background: var(--surface);
  border-left: 1px solid var(--line);
  box-shadow: var(--shadow);
  overflow: auto;
}

.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.drawer-head h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--ink);
}

.drawer-head p {
  margin: 0.3rem 0 0;
  color: var(--muted);
  font-size: 0.82rem;
}

.member-form {
  display: grid;
  gap: 0.65rem;
  padding: 0.85rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface-muted);
}

.member-form label {
  display: grid;
  gap: 0.3rem;
}

.member-form label > span,
.domains legend {
  font-size: 0.78rem;
  color: var(--muted);
  font-weight: 500;
}

.member-form select {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 0.5rem 0.65rem;
  background: var(--surface);
  color: var(--text);
}

.domains {
  border: 0;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0.35rem;
}

.domains .check {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.member-table {
  flex: 1;
}
</style>
