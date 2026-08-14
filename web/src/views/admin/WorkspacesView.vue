<template>
  <section class="admin-page">
    <header class="page-head">
      <div>
        <h1>工作空间</h1>
        <p>组织下的空间列表；可创建、归档，并管理成员角色与业务域。</p>
      </div>
      <button
        type="button"
        class="primary"
        :disabled="!isOrgAdmin"
        @click="openCreate"
      >
        新建工作空间
      </button>
    </header>

    <p v-if="!isOrgAdmin && meLoaded" class="banner error" role="alert">
      仅组织管理员可创建/归档工作空间并管理成员。
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
                statusLabel(row.status)
              }}</span>
            </td>
            <td class="mono">{{ formatTime(row.created_at) }}</td>
            <td class="actions">
              <button type="button" :disabled="!isOrgAdmin" @click="openMembers(row)">
                成员
              </button>
              <button
                type="button"
                class="danger"
                :disabled="!isOrgAdmin || row.status === 'archived'"
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
          <input v-model="createName" required maxlength="120" />
        </label>
        <div class="modal-actions">
          <button type="button" class="ghost" @click="closeCreate">取消</button>
          <button type="submit" class="primary" :disabled="saving">
            {{ saving ? "创建中…" : "创建" }}
          </button>
        </div>
      </form>
    </div>

    <div v-if="membersOpen" class="modal-backdrop" @click.self="closeMembers">
      <div class="modal modal-wide">
        <h2>成员 — {{ membersWorkspace?.name }}</h2>

        <p v-if="membersError" class="banner error" role="alert">{{ membersError }}</p>

        <div class="table-card nested">
          <div v-if="membersLoading" class="empty">加载中…</div>
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
                <td>{{ roleLabel(m.role) }}</td>
                <td>{{ domainsLabel(m.domains) }}</td>
                <td class="actions">
                  <button type="button" class="danger" @click="onRemoveMember(m)">移除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <form class="add-member" @submit.prevent="onAddMember">
          <h3>添加成员</h3>
          <label>
            <span>用户</span>
            <select v-model.number="memberForm.user_id" required>
              <option disabled :value="0">选择用户</option>
              <option
                v-for="u in addableUsers"
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
              <option value="org_admin">组织管理员</option>
              <option value="analyst">分析师</option>
              <option value="viewer">只读</option>
            </select>
          </label>
          <fieldset class="domain-set">
            <legend>业务域</legend>
            <label v-for="d in domainOptions" :key="d.id" class="check">
              <input v-model="memberForm.domains" type="checkbox" :value="d.id" />
              <span>{{ d.label }}</span>
            </label>
          </fieldset>
          <div class="modal-actions">
            <button type="button" class="ghost" @click="closeMembers">关闭</button>
            <button type="submit" class="primary" :disabled="memberSaving || !addableUsers.length">
              {{ memberSaving ? "添加中…" : "添加" }}
            </button>
          </div>
        </form>
      </div>
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
const orgUsers = ref<OrgUser[]>([]);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const note = ref("");
const meLoaded = ref(false);
const isOrgAdmin = ref(false);

const createOpen = ref(false);
const createName = ref("");

const membersOpen = ref(false);
const membersWorkspace = ref<Workspace | null>(null);
const members = ref<WorkspaceMember[]>([]);
const membersLoading = ref(false);
const membersError = ref("");
const memberSaving = ref(false);

const memberForm = reactive({
  user_id: 0,
  role: "analyst",
  domains: ["biz", "network", "cs"] as string[],
});

const addableUsers = computed(() => {
  const taken = new Set(members.value.map((m) => m.user_id));
  return orgUsers.value.filter((u) => u.enabled && !taken.has(u.id));
});

function statusLabel(status: string): string {
  if (status === "active") return "活跃";
  if (status === "archived") return "已归档";
  return status;
}

function roleLabel(role: string): string {
  if (role === "org_admin") return "组织管理员";
  if (role === "analyst") return "分析师";
  if (role === "viewer") return "只读";
  return role;
}

function domainsLabel(domains: string[]): string {
  if (!domains?.length) return "—";
  return domains
    .map((id) => domainOptions.find((d) => d.id === id)?.label ?? id)
    .join("、");
}

function userLabel(userId: number): string {
  const u = orgUsers.value.find((x) => x.id === userId);
  if (!u) return `#${userId}`;
  return u.display_name ? `${u.display_name}（${u.username}）` : u.username;
}

function formatTime(value?: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
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
  if (!isOrgAdmin.value) return;
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
    const name = createName.value.trim();
    await createWorkspace({ name });
    createOpen.value = false;
    note.value = `已创建工作空间「${name}」`;
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    saving.value = false;
  }
}

async function onArchive(row: Workspace) {
  if (!isOrgAdmin.value) return;
  if (!window.confirm(`确认归档工作空间「${row.name}」？`)) return;
  error.value = "";
  note.value = "";
  try {
    await archiveWorkspace(row.id);
    note.value = `已归档「${row.name}」`;
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  }
}

async function openMembers(row: Workspace) {
  if (!isOrgAdmin.value) return;
  membersWorkspace.value = row;
  membersOpen.value = true;
  membersError.value = "";
  memberForm.user_id = 0;
  memberForm.role = "analyst";
  memberForm.domains = ["biz", "network", "cs"];
  membersLoading.value = true;
  try {
    const [memberRows, users] = await Promise.all([
      listMembers(row.id),
      listUsers(),
    ]);
    members.value = memberRows;
    orgUsers.value = users;
  } catch (err) {
    membersError.value = friendlyError(err);
  } finally {
    membersLoading.value = false;
  }
}

function closeMembers() {
  membersOpen.value = false;
  membersWorkspace.value = null;
}

async function onAddMember() {
  if (!membersWorkspace.value || !memberForm.user_id) return;
  memberSaving.value = true;
  membersError.value = "";
  try {
    await addMember(membersWorkspace.value.id, {
      user_id: memberForm.user_id,
      role: memberForm.role,
      domains: [...memberForm.domains],
    });
    members.value = await listMembers(membersWorkspace.value.id);
    memberForm.user_id = 0;
    note.value = "已添加成员";
  } catch (err) {
    membersError.value = friendlyError(err);
  } finally {
    memberSaving.value = false;
  }
}

async function onRemoveMember(m: WorkspaceMember) {
  if (!membersWorkspace.value) return;
  if (!window.confirm(`确认移除 ${userLabel(m.user_id)}？`)) return;
  membersError.value = "";
  try {
    await removeMember(membersWorkspace.value.id, m.user_id);
    members.value = await listMembers(membersWorkspace.value.id);
    note.value = "已移除成员";
  } catch (err) {
    membersError.value = friendlyError(err);
  }
}

onMounted(() => {
  void loadMe().then(() => refresh());
});
</script>

<style src="./admin-shared.css"></style>
<style scoped>
.modal-wide {
  width: min(640px, 100%);
}

.nested {
  max-height: 240px;
  margin-bottom: 0.75rem;
}

.add-member {
  display: grid;
  gap: 0.7rem;
}

.add-member h3 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--ink);
}

.domain-set {
  margin: 0;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem 1rem;
}

.domain-set legend {
  padding: 0 0.25rem;
  font-size: 0.78rem;
  color: var(--muted);
  font-weight: 500;
}

.domain-set .check {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.domain-set .check input {
  width: auto;
}

.domain-set .check span {
  font-size: 0.85rem;
  color: var(--text);
}
</style>
