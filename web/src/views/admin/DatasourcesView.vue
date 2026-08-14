<template>
  <section class="admin-page">
    <header class="page-head">
      <div>
        <h1>数据源</h1>
        <p>管理当前工作空间的执行库连接；密码只写不回显。</p>
      </div>
      <button type="button" class="primary" @click="openCreate">新建数据源</button>
    </header>

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
          <tr v-for="row in rows" :key="row.id">
            <td>{{ row.name }}</td>
            <td class="mono">{{ row.db_type }}</td>
            <td class="mono">{{ row.host || "—" }}</td>
            <td class="mono">{{ row.database || "—" }}</td>
            <td>
              <span class="pill" :class="{ on: row.is_default }">{{
                row.is_default ? "默认" : "—"
              }}</span>
            </td>
            <td class="mono">{{ formatTime(row.last_ok_at) }}</td>
            <td class="actions">
              <button type="button" @click="onTest(row)">测连</button>
              <button type="button" :disabled="row.is_default" @click="onSetDefault(row)">
                设默认
              </button>
              <button type="button" @click="openEdit(row)">编辑</button>
              <button type="button" class="danger" @click="onDelete(row)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

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
              <option v-for="t in p0Types" :key="t" :value="t">{{ t }}</option>
            </optgroup>
            <optgroup label="P1 即将支持">
              <option v-for="t in p1Types" :key="t" :value="t" disabled>
                {{ t }}（即将支持）
              </option>
            </optgroup>
          </select>
        </label>
        <label>
          <span>主机</span>
          <input v-model="form.host" required />
        </label>
        <label>
          <span>端口</span>
          <input v-model.number="form.port" type="number" min="1" max="65535" />
        </label>
        <label>
          <span>数据库</span>
          <input v-model="form.database" required />
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
            :placeholder="editingId == null ? '' : '••••'"
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
  friendlyError,
  listDatasources,
  setDefaultDatasource,
  testDatasource,
  updateDatasource,
  type Datasource,
} from "../../api";

const p0Types = [
  "postgres",
  "mysql",
  "sqlserver",
  "hive",
  "opengauss",
  "gaussdb",
  "oceanbase_mysql",
  "tidb",
  "kingbase",
  "dameng",
] as const;

const p1Types = ["gbase", "shentong", "polardb", "tdsql"] as const;

const rows = ref<Datasource[]>([]);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const note = ref("");
const dialogOpen = ref(false);
const editingId = ref<number | null>(null);

const form = reactive({
  name: "",
  db_type: "postgres" as string,
  host: "",
  port: null as number | null,
  database: "",
  username: "",
  password: "",
  is_default: false,
});

function formatTime(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
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
  editingId.value = null;
  resetForm();
  dialogOpen.value = true;
}

function openEdit(row: Datasource) {
  editingId.value = row.id;
  form.name = row.name;
  form.db_type = row.db_type;
  form.host = row.host || "";
  form.port = row.port ?? null;
  form.database = row.database || "";
  form.username = row.username || "";
  form.password = "";
  form.is_default = row.is_default;
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
    const payload: {
      name: string;
      db_type: string;
      host: string;
      port: number | null;
      database: string;
      username: string;
      password?: string;
      is_default: boolean;
    } = {
      name: form.name.trim(),
      db_type: form.db_type,
      host: form.host.trim(),
      port: form.port == null || Number.isNaN(Number(form.port)) ? null : Number(form.port),
      database: form.database.trim(),
      username: form.username.trim(),
      is_default: form.is_default,
    };
    if (form.password) {
      payload.password = form.password;
    }
    if (editingId.value == null) {
      await createDatasource(payload);
      note.value = "数据源已创建。";
    } else {
      await updateDatasource(editingId.value, payload);
      note.value = "数据源已更新。";
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
  if (!window.confirm(`确认删除数据源「${row.name}」？`)) return;
  error.value = "";
  note.value = "";
  try {
    await deleteDatasource(row.id);
    note.value = `已删除「${row.name}」。`;
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
      note.value = `测连「${row.name}」成功。`;
    } else {
      error.value = `测连「${row.name}」失败：${result.error || "unknown"}`;
    }
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  }
}

async function onSetDefault(row: Datasource) {
  error.value = "";
  note.value = "";
  try {
    await setDefaultDatasource(row.id);
    note.value = `已将「${row.name}」设为默认。`;
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  }
}

onMounted(() => {
  void refresh();
});
</script>

<style src="./admin-shared.css"></style>
