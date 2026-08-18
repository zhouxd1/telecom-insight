<template>
  <section class="admin-page" :class="{ browsing: !!browsing }">
    <template v-if="browsing">
      <p v-if="error" class="banner error" role="alert">{{ error }}</p>
      <p v-if="note" class="banner ok">{{ note }}</p>
      <DatasourceBrowser
        :ds="browsing"
        :is-org-admin="isOrgAdmin"
        @back="browsing = null"
        @note="onBrowserNote"
        @error="onBrowserError"
      />
    </template>

    <template v-else>
      <header class="page-head">
        <div>
          <h1>数据源</h1>
          <p>管理当前工作空间的执行库连接；点击一行进入库表浏览。</p>
        </div>
        <button type="button" class="primary" :disabled="!isOrgAdmin" @click="openCreate">
          新建数据源
        </button>
      </header>

      <p v-if="!isOrgAdmin && meLoaded" class="banner error" role="alert">
        成员可点击数据源行浏览结构与样例数据；仅组织管理员可新建/编辑数据源、刷新结构与保存字段授权。
      </p>
      <p v-if="error" class="banner error" role="alert">{{ error }}</p>
      <p v-if="note" class="banner ok">{{ note }}</p>

      <div class="table-card">
        <div v-if="loading" class="empty">加载中…</div>
        <div v-else-if="!rows.length" class="empty">暂无数据源，点击右上角新建。</div>
        <table v-else>
          <thead>
            <tr>
              <th>名称</th>
              <th>类型</th>
              <th>主机</th>
              <th>数据库</th>
              <th>默认</th>
              <th>最近成功</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in rows"
              :key="row.id"
              class="clickable-row"
              role="button"
              tabindex="0"
              @click="openBrowser(row)"
              @keydown="onRowKeydown($event, row)"
            >
              <td>{{ row.name }}</td>
              <td class="mono">{{ row.db_type }}</td>
              <td class="mono">{{ formatHost(row) }}</td>
              <td class="mono">{{ row.database || "—" }}</td>
              <td>
                <span class="pill" :class="{ on: row.is_default }">{{
                  row.is_default ? "默认" : "—"
                }}</span>
              </td>
              <td class="mono">{{ formatTime(row.last_ok_at) }}</td>
              <td class="actions" @click.stop @keydown.stop>
                <button type="button" @click="onTest(row)">测连</button>
                <button
                  type="button"
                  :disabled="!isOrgAdmin || row.is_default"
                  @click="onSetDefault(row)"
                >
                  设默认
                </button>
                <button type="button" :disabled="!isOrgAdmin" @click="openEdit(row)">编辑</button>
                <button
                  type="button"
                  class="danger"
                  :disabled="!isOrgAdmin"
                  @click="onDelete(row)"
                >
                  删除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <div v-if="dialogOpen" class="modal-backdrop" @click.self="closeDialog">
      <form class="modal" @submit.prevent="onSave">
        <h2>{{ editingId == null ? "新建数据源" : "编辑数据源" }}</h2>
        <label>
          <span>名称</span>
          <input v-model="form.name" required />
        </label>
        <label>
          <span>数据库类型</span>
          <select v-model="form.db_type" required>
            <optgroup label="P0 支持">
              <option v-for="t in p0Types" :key="t.id" :value="t.id">{{ t.label }}</option>
            </optgroup>
            <optgroup label="P1 即将支持">
              <option v-for="t in p1Types" :key="t.id" :value="t.id" disabled>
                {{ t.label }}（即将支持）
              </option>
            </optgroup>
          </select>
        </label>
        <label>
          <span>主机</span>
          <input v-model="form.host" placeholder="localhost" />
        </label>
        <label>
          <span>端口</span>
          <input v-model.number="form.port" type="number" min="1" max="65535" placeholder="可选" />
        </label>
        <label>
          <span>数据库</span>
          <input v-model="form.database" />
        </label>
        <label>
          <span>用户名</span>
          <input v-model="form.username" autocomplete="off" />
        </label>
        <label>
          <span>密码</span>
          <input
            v-model="form.password"
            type="password"
            autocomplete="new-password"
            :placeholder="editingId == null ? '' : '留空则不修改'"
          />
        </label>
        <label class="check">
          <input v-model="form.is_default" type="checkbox" />
          <span>设为空间默认数据源</span>
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
  createDatasource,
  deleteDatasource,
  fetchMe,
  friendlyError,
  listDatasources,
  setDefaultDatasource,
  testDatasource,
  updateDatasource,
  type Datasource,
} from "../../api";
import DatasourceBrowser from "./DatasourceBrowser.vue";

const p0Types = [
  { id: "postgres", label: "PostgreSQL" },
  { id: "mysql", label: "MySQL" },
  { id: "sqlserver", label: "SQL Server" },
  { id: "hive", label: "Hive" },
  { id: "opengauss", label: "openGauss" },
  { id: "gaussdb", label: "GaussDB" },
  { id: "oceanbase_mysql", label: "OceanBase MySQL" },
  { id: "tidb", label: "TiDB" },
  { id: "kingbase", label: "人大金仓 Kingbase" },
  { id: "dameng", label: "达梦 Dameng" },
] as const;

const p1Types = [
  { id: "gbase", label: "GBase" },
  { id: "shentong", label: "神通" },
  { id: "polardb", label: "PolarDB" },
  { id: "tdsql", label: "TDSQL" },
] as const;

const rows = ref<Datasource[]>([]);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const note = ref("");
const dialogOpen = ref(false);
const editingId = ref<number | null>(null);
const meLoaded = ref(false);
const isOrgAdmin = ref(false);
const browsing = ref<Datasource | null>(null);

const form = reactive({
  name: "",
  db_type: "postgres",
  host: "",
  port: null as number | null,
  database: "",
  username: "",
  password: "",
  is_default: false,
});

function formatHost(row: Datasource): string {
  if (!row.host) return "—";
  return row.port != null ? `${row.host}:${row.port}` : row.host;
}

function formatTime(value?: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function openBrowser(row: Datasource) {
  error.value = "";
  note.value = "";
  browsing.value = row;
}

function onRowKeydown(event: KeyboardEvent, row: Datasource) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    openBrowser(row);
  }
}

function onBrowserNote(message: string) {
  error.value = "";
  note.value = message;
}

function onBrowserError(message: string) {
  note.value = "";
  error.value = message;
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
    rows.value = await listDatasources();
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    loading.value = false;
  }
}

function resetForm() {
  form.name = "";
  form.db_type = "postgres";
  form.host = "";
  form.port = null;
  form.database = "";
  form.username = "";
  form.password = "";
  form.is_default = false;
}

function openCreate() {
  if (!isOrgAdmin.value) return;
  editingId.value = null;
  resetForm();
  dialogOpen.value = true;
}

function openEdit(row: Datasource) {
  if (!isOrgAdmin.value) return;
  editingId.value = row.id;
  form.name = row.name;
  form.db_type = row.db_type;
  form.host = row.host;
  form.port = row.port ?? null;
  form.database = row.database;
  form.username = row.username;
  form.password = "";
  form.is_default = row.is_default;
  dialogOpen.value = true;
}

function closeDialog() {
  dialogOpen.value = false;
}

async function onSave() {
  if (!isOrgAdmin.value) return;
  saving.value = true;
  error.value = "";
  note.value = "";
  try {
    const portValue =
      form.port == null || Number.isNaN(Number(form.port)) ? null : Number(form.port);
    const payload = {
      name: form.name.trim(),
      db_type: form.db_type,
      host: form.host.trim(),
      port: portValue,
      database: form.database.trim(),
      username: form.username.trim(),
      is_default: form.is_default,
    };
    if (editingId.value == null) {
      await createDatasource({
        ...payload,
        password: form.password || undefined,
      });
      note.value = `已创建数据源「${payload.name}」`;
    } else {
      const patch: Parameters<typeof updateDatasource>[1] = { ...payload };
      if (form.password) {
        patch.password = form.password;
      }
      await updateDatasource(editingId.value, patch);
      note.value = `已更新数据源「${payload.name}」`;
    }
    dialogOpen.value = false;
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    saving.value = false;
  }
}

async function onDelete(row: Datasource) {
  if (!isOrgAdmin.value) return;
  if (!window.confirm(`确认删除数据源「${row.name}」？`)) return;
  error.value = "";
  note.value = "";
  try {
    await deleteDatasource(row.id);
    note.value = `已删除「${row.name}」`;
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  }
}

async function onTest(row: Datasource) {
  error.value = "";
  note.value = "";
  try {
    const result = await testDatasource(row.id);
    if (result.ok) {
      note.value = `测连「${row.name}」成功`;
    } else {
      error.value = `测连「${row.name}」失败：${result.error || "unknown"}`;
    }
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  }
}

async function onSetDefault(row: Datasource) {
  if (!isOrgAdmin.value) return;
  error.value = "";
  note.value = "";
  try {
    await setDefaultDatasource(row.id);
    note.value = `已将「${row.name}」设为默认`;
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  }
}

onMounted(() => {
  void loadMe().then(() => refresh());
});
</script>

<style src="./admin-shared.css"></style>
<style scoped>
.admin-page.browsing {
  max-width: 1280px;
}

.clickable-row {
  cursor: pointer;
}

.clickable-row:hover td {
  background: var(--surface-muted);
}

.clickable-row:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}
</style>
