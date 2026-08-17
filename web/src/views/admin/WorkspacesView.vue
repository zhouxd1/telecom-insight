<template>
  <section class="admin-page">
    <header class="page-head">
      <div>
        <h1>工作空间</h1>
        <p>组织下的空间列表；可创建、归档，并管理成员角色与业务域。</p>
      </div>
      <div class="head-actions">
        <label v-if="isOrgAdmin" class="bypass-toggle" title="组织管理员提问时是否跳过行级过滤">
          <input
            v-model="rlsAdminBypass"
            type="checkbox"
            :disabled="bypassSaving"
            @change="onBypassChange"
          />
          <span>管理员绕过行过滤</span>
        </label>
        <button
          type="button"
          class="primary"
          :disabled="!isOrgAdmin"
          @click="openCreate"
        >
          新建工作空间
        </button>
      </div>
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
              <template v-for="m in members" :key="m.id">
                <tr>
                  <td>{{ userLabel(m.user_id) }}</td>
                  <td>{{ roleLabel(m.role) }}</td>
                  <td>{{ domainsLabel(m.domains) }}</td>
                  <td class="actions">
                    <button type="button" @click="toggleRls(m)">
                      {{ rlsExpandedId === m.id ? "收起行权限" : "行权限" }}
                    </button>
                    <button type="button" class="danger" @click="onRemoveMember(m)">移除</button>
                  </td>
                </tr>
                <tr v-if="rlsExpandedId === m.id" class="rls-row">
                  <td colspan="4">
                    <div class="rls-panel">
                      <p v-if="rlsError" class="banner error" role="alert">{{ rlsError }}</p>
                      <div v-if="rlsLoading" class="empty rls-empty">加载行权限…</div>
                      <div v-else-if="!rlsPolicies.length" class="empty rls-empty">暂无行权限策略。</div>
                      <ul v-else class="rls-list">
                        <li v-for="p in rlsPolicies" :key="p.id">
                          <span class="rls-meta">
                            {{ domainLabel(p.domain) }} ·
                            {{ p.schema_name }}.{{ p.table_name }}.{{ p.column_name }}
                            {{ p.op === "eq" ? "=" : "∈" }}
                            {{ p.values.join("、") }}
                          </span>
                          <button
                            type="button"
                            class="danger"
                            :disabled="rlsSaving"
                            @click="onDeleteRls(p)"
                          >
                            删除
                          </button>
                        </li>
                      </ul>

                      <form class="rls-form" @submit.prevent="onAddRls(m)">
                        <h3>添加行权限</h3>
                        <div class="rls-fields">
                          <label>
                            <span>业务域</span>
                            <select v-model="rlsForm.domain" required @change="onRlsDomainChange">
                              <option
                                v-for="d in domainOptions"
                                :key="d.id"
                                :value="d.id"
                              >
                                {{ d.label }}
                              </option>
                            </select>
                          </label>
                          <label>
                            <span>列</span>
                            <select v-model="rlsForm.columnKey" required :disabled="!rlsColumns.length">
                              <option disabled value="">
                                {{ rlsColumns.length ? "选择列" : "该域无可过滤列" }}
                              </option>
                              <option
                                v-for="c in rlsColumns"
                                :key="columnKey(c)"
                                :value="columnKey(c)"
                              >
                                {{ c.label }}（{{ c.schema_name }}.{{ c.table_name }}.{{ c.column_name }}）
                              </option>
                            </select>
                          </label>
                          <label>
                            <span>运算符</span>
                            <select v-model="rlsForm.op" required>
                              <option value="in">in（多值）</option>
                              <option value="eq">eq（等于）</option>
                            </select>
                          </label>
                          <label>
                            <span>取值</span>
                            <input
                              v-model="rlsForm.valuesText"
                              required
                              :placeholder="rlsForm.op === 'eq' ? '单个值' : '逗号分隔，如 华东,华南'"
                            />
                          </label>
                        </div>
                        <div class="modal-actions">
                          <button
                            type="submit"
                            class="primary"
                            :disabled="rlsSaving || !rlsForm.columnKey"
                          >
                            {{ rlsSaving ? "保存中…" : "添加策略" }}
                          </button>
                        </div>
                      </form>
                    </div>
                  </td>
                </tr>
              </template>
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
  createMemberRls,
  createWorkspace,
  deleteRlsPolicy,
  fetchMe,
  fetchRlsColumns,
  fetchRlsSettings,
  friendlyError,
  listMemberRls,
  listMembers,
  listUsers,
  listWorkspaces,
  removeMember,
  updateRlsSettings,
  type OrgUser,
  type RlsColumn,
  type RlsPolicy,
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

const rlsAdminBypass = ref(true);
const bypassSaving = ref(false);

const createOpen = ref(false);
const createName = ref("");

const membersOpen = ref(false);
const membersWorkspace = ref<Workspace | null>(null);
const members = ref<WorkspaceMember[]>([]);
const membersLoading = ref(false);
const membersError = ref("");
const memberSaving = ref(false);

const rlsExpandedId = ref<number | null>(null);
const rlsPolicies = ref<RlsPolicy[]>([]);
const rlsColumns = ref<RlsColumn[]>([]);
const rlsLoading = ref(false);
const rlsSaving = ref(false);
const rlsError = ref("");

const rlsForm = reactive({
  domain: "biz",
  columnKey: "",
  op: "in",
  valuesText: "",
});

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

function domainLabel(id: string): string {
  return domainOptions.find((d) => d.id === id)?.label ?? id;
}

function domainsLabel(domains: string[]): string {
  if (!domains?.length) return "—";
  return domains.map((id) => domainLabel(id)).join("、");
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

function columnKey(c: Pick<RlsColumn, "schema_name" | "table_name" | "column_name">): string {
  return `${c.schema_name}|${c.table_name}|${c.column_name}`;
}

function parseColumnKey(key: string): {
  schema_name: string;
  table_name: string;
  column_name: string;
} | null {
  const parts = key.split("|");
  if (parts.length !== 3) return null;
  return { schema_name: parts[0], table_name: parts[1], column_name: parts[2] };
}

function parseValues(text: string, op: string): string[] | null {
  const values = text
    .split(/[,，]/)
    .map((v) => v.trim())
    .filter(Boolean);
  if (!values.length) return null;
  if (op === "eq" && values.length !== 1) return null;
  return values;
}

function resetRlsForm() {
  rlsForm.domain = "biz";
  rlsForm.columnKey = "";
  rlsForm.op = "in";
  rlsForm.valuesText = "";
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

async function loadBypass() {
  if (!isOrgAdmin.value) return;
  try {
    const settings = await fetchRlsSettings();
    rlsAdminBypass.value = settings.rls_admin_bypass;
  } catch (err) {
    error.value = friendlyError(err);
  }
}

async function onBypassChange() {
  if (!isOrgAdmin.value) return;
  bypassSaving.value = true;
  error.value = "";
  note.value = "";
  try {
    const settings = await updateRlsSettings({
      rls_admin_bypass: rlsAdminBypass.value,
    });
    rlsAdminBypass.value = settings.rls_admin_bypass;
    note.value = settings.rls_admin_bypass
      ? "已开启：组织管理员绕过行过滤"
      : "已关闭：组织管理员也应用行过滤";
  } catch (err) {
    error.value = friendlyError(err);
    try {
      const settings = await fetchRlsSettings();
      rlsAdminBypass.value = settings.rls_admin_bypass;
    } catch {
      /* keep UI as-is */
    }
  } finally {
    bypassSaving.value = false;
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
  rlsExpandedId.value = null;
  rlsPolicies.value = [];
  rlsError.value = "";
  resetRlsForm();
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
  rlsExpandedId.value = null;
  rlsPolicies.value = [];
  rlsError.value = "";
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
    if (rlsExpandedId.value === m.id) {
      rlsExpandedId.value = null;
      rlsPolicies.value = [];
    }
    members.value = await listMembers(membersWorkspace.value.id);
    note.value = "已移除成员";
  } catch (err) {
    membersError.value = friendlyError(err);
  }
}

async function loadRlsColumnsForDomain(domain: string) {
  try {
    rlsColumns.value = await fetchRlsColumns(domain);
    if (!rlsColumns.value.some((c) => columnKey(c) === rlsForm.columnKey)) {
      rlsForm.columnKey = rlsColumns.value[0] ? columnKey(rlsColumns.value[0]) : "";
    }
  } catch (err) {
    rlsColumns.value = [];
    rlsForm.columnKey = "";
    rlsError.value = friendlyError(err);
  }
}

async function onRlsDomainChange() {
  rlsError.value = "";
  await loadRlsColumnsForDomain(rlsForm.domain);
}

async function toggleRls(m: WorkspaceMember) {
  if (!membersWorkspace.value || !isOrgAdmin.value) return;
  if (rlsExpandedId.value === m.id) {
    rlsExpandedId.value = null;
    rlsPolicies.value = [];
    rlsError.value = "";
    return;
  }
  rlsExpandedId.value = m.id;
  rlsError.value = "";
  resetRlsForm();
  rlsLoading.value = true;
  try {
    const [policies] = await Promise.all([
      listMemberRls(membersWorkspace.value.id, m.id),
      loadRlsColumnsForDomain(rlsForm.domain),
    ]);
    rlsPolicies.value = policies;
  } catch (err) {
    rlsPolicies.value = [];
    rlsError.value = friendlyError(err);
  } finally {
    rlsLoading.value = false;
  }
}

async function onAddRls(m: WorkspaceMember) {
  if (!membersWorkspace.value) return;
  const col = parseColumnKey(rlsForm.columnKey);
  const values = parseValues(rlsForm.valuesText, rlsForm.op);
  if (!col) {
    rlsError.value = "请选择列";
    return;
  }
  if (!values) {
    rlsError.value =
      rlsForm.op === "eq" ? "eq 需要恰好一个取值" : "请填写至少一个取值（逗号分隔）";
    return;
  }
  rlsSaving.value = true;
  rlsError.value = "";
  try {
    await createMemberRls(membersWorkspace.value.id, m.id, {
      domain: rlsForm.domain,
      schema_name: col.schema_name,
      table_name: col.table_name,
      column_name: col.column_name,
      op: rlsForm.op,
      values,
    });
    rlsPolicies.value = await listMemberRls(membersWorkspace.value.id, m.id);
    rlsForm.valuesText = "";
    note.value = "已添加行权限策略";
  } catch (err) {
    rlsError.value = friendlyError(err);
  } finally {
    rlsSaving.value = false;
  }
}

async function onDeleteRls(p: RlsPolicy) {
  if (!membersWorkspace.value) return;
  if (!window.confirm("确认删除该行权限策略？")) return;
  rlsSaving.value = true;
  rlsError.value = "";
  try {
    await deleteRlsPolicy(membersWorkspace.value.id, p.id);
    rlsPolicies.value = await listMemberRls(membersWorkspace.value.id, p.member_id);
    note.value = "已删除行权限策略";
  } catch (err) {
    rlsError.value = friendlyError(err);
  } finally {
    rlsSaving.value = false;
  }
}

onMounted(() => {
  void loadMe().then(async () => {
    await Promise.all([refresh(), loadBypass()]);
  });
});
</script>

<style src="./admin-shared.css"></style>
<style scoped>
.page-head .head-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
}

.bypass-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.82rem;
  color: var(--text);
  cursor: pointer;
  user-select: none;
}

.bypass-toggle input {
  width: auto;
  margin: 0;
}

.modal-wide {
  width: min(720px, 100%);
  max-height: min(90vh, 860px);
  overflow: auto;
}

.nested {
  max-height: none;
  margin-bottom: 0.75rem;
}

.add-member {
  display: grid;
  gap: 0.7rem;
}

.add-member h3,
.rls-form h3 {
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

.rls-row td {
  background: var(--surface-muted);
  padding: 0.75rem 0.85rem 0.9rem;
}

.rls-panel {
  display: grid;
  gap: 0.65rem;
}

.rls-empty {
  padding: 0.75rem 0.25rem;
}

.rls-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.4rem;
}

.rls-list li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.5rem 0.65rem;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
}

.rls-meta {
  font-size: 0.82rem;
  color: var(--text);
  line-height: 1.4;
}

.rls-form {
  display: grid;
  gap: 0.55rem;
  padding-top: 0.25rem;
}

.rls-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.55rem 0.65rem;
}

.rls-fields label {
  display: grid;
  gap: 0.3rem;
}

.rls-fields label span {
  font-size: 0.78rem;
  color: var(--muted);
  font-weight: 500;
}

.rls-fields select,
.rls-fields input {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 0.45rem 0.6rem;
  background: var(--surface);
  color: var(--text);
  font-size: 0.85rem;
}

@media (max-width: 560px) {
  .rls-fields {
    grid-template-columns: 1fr;
  }
}
</style>
