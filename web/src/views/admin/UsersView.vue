<template>
  <section class="admin-page">
    <header class="page-head">
      <div>
        <h1>用户</h1>
        <p>管理组织账号、角色与启用状态。</p>
      </div>
      <button
        v-if="isOrgAdmin"
        type="button"
        class="primary"
        @click="openCreate"
      >
        新建用户
      </button>
    </header>

    <p v-if="!isOrgAdmin && meLoaded" class="banner error" role="alert">
      仅组织管理员（org_admin）可管理用户。
    </p>
    <p v-if="error" class="banner error" role="alert">{{ error }}</p>
    <p v-if="note" class="banner ok">{{ note }}</p>

    <div class="table-card">
      <div v-if="!isOrgAdmin && meLoaded" class="empty">无权限查看用户列表。</div>
      <div v-else-if="loading" class="empty">加载中…</div>
      <div v-else-if="!rows.length" class="empty">暂无用户。</div>
      <table v-else>
        <thead>
          <tr>
            <th>用户名</th>
            <th>显示名</th>
            <th>组织角色</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td>{{ row.username }}</td>
            <td>{{ row.display_name || "—" }}</td>
            <td>{{ roleLabel(row.org_role) }}</td>
            <td>
              <span class="pill" :class="{ on: row.enabled }">{{
                row.enabled ? "启用" : "停用"
              }}</span>
            </td>
            <td class="actions">
              <button type="button" :disabled="!isOrgAdmin" @click="openEdit(row)">
                编辑
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="dialogOpen" class="modal-backdrop" @click.self="closeDialog">
      <form class="modal" @submit.prevent="onSave">
        <h2>{{ editingId == null ? "新建用户" : "编辑用户" }}</h2>
        <label>
          <span>用户名</span>
          <input
            v-model="form.username"
            required
            :disabled="editingId != null"
            autocomplete="off"
          />
        </label>
        <label>
          <span>密码</span>
          <input
            v-model="form.password"
            type="password"
            autocomplete="new-password"
            :required="editingId == null"
            :placeholder="editingId == null ? '' : '••••'"
          />
        </label>
        <label>
          <span>显示名</span>
          <input v-model="form.display_name" />
        </label>
        <label>
          <span>组织角色</span>
          <select v-model="form.org_role" required>
            <option value="org_admin">org_admin（组织管理员）</option>
            <option value="analyst">analyst（分析师）</option>
            <option value="viewer">viewer（只读）</option>
          </select>
        </label>
        <label class="check">
          <input v-model="form.enabled" type="checkbox" />
          <span>启用账号</span>
        </label>
        <div class="modal-actions">
          <button type="button" class="ghost" @click="closeDialog">取消</button>
          <button type="submit" class="primary" :disabled="saving">
            {{ saving ? "保存中…" : "保存" }}
          </button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import {
  createUser,
  fetchMe,
  friendlyError,
  listUsers,
  updateUser,
  type OrgUser,
} from "../../api";

const rows = ref<OrgUser[]>([]);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const note = ref("");
const meLoaded = ref(false);
const isOrgAdmin = ref(false);
const dialogOpen = ref(false);
const editingId = ref<number | null>(null);

const form = reactive({
  username: "",
  password: "",
  display_name: "",
  org_role: "analyst",
  enabled: true,
});

function roleLabel(role: string): string {
  if (role === "org_admin") return "org_admin";
  if (role === "analyst") return "analyst";
  if (role === "viewer") return "viewer";
  return role;
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
  if (!isOrgAdmin.value) {
    rows.value = [];
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    rows.value = await listUsers();
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    loading.value = false;
  }
}

function resetForm() {
  form.username = "";
  form.password = "";
  form.display_name = "";
  form.org_role = "analyst";
  form.enabled = true;
}

function openCreate() {
  editingId.value = null;
  resetForm();
  dialogOpen.value = true;
}

function openEdit(row: OrgUser) {
  editingId.value = row.id;
  form.username = row.username;
  form.password = "";
  form.display_name = row.display_name || "";
  form.org_role = row.org_role;
  form.enabled = row.enabled;
  dialogOpen.value = true;
}

function closeDialog() {
  dialogOpen.value = false;
}

async function onSave() {
  saving.value = true;
  error.value = "";
  note.value = "";
  try {
    if (editingId.value == null) {
      await createUser({
        username: form.username.trim(),
        password: form.password,
        display_name: form.display_name.trim(),
        org_role: form.org_role,
        enabled: form.enabled,
      });
      note.value = "用户已创建。";
    } else {
      const payload: {
        display_name: string;
        org_role: string;
        enabled: boolean;
        password?: string;
      } = {
        display_name: form.display_name.trim(),
        org_role: form.org_role,
        enabled: form.enabled,
      };
      if (form.password) {
        payload.password = form.password;
      }
      await updateUser(editingId.value, payload);
      note.value = "用户已更新。";
    }
    dialogOpen.value = false;
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await loadMe();
  await refresh();
});
</script>

<style src="./admin-shared.css"></style>
