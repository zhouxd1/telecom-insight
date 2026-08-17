<template>
  <section class="admin-page">
    <header class="page-head">
      <div>
        <h1>数据源</h1>
        <p>管理当前工作空间的执行库连接（测连、设默认、库表授权）。</p>
      </div>
      <button type="button" class="primary" :disabled="!isOrgAdmin" @click="openCreate">
        新建数据源
      </button>
    </header>

    <p v-if="!isOrgAdmin && meLoaded" class="banner error" role="alert">
      仅组织管理员可新建/编辑数据源，以及刷新结构与字段授权。
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
          <tr v-for="row in rows" :key="row.id">
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
            <td class="actions">
              <button type="button" @click="onTest(row)">测连</button>
              <button
                type="button"
                :disabled="!isOrgAdmin || row.is_default"
                @click="onSetDefault(row)"
              >
                设默认
              </button>
              <button
                type="button"
                :disabled="!isOrgAdmin || introspectingId === row.id"
                @click="onRefreshSchema(row)"
              >
                {{ introspectingId === row.id ? "刷新中…" : "刷新结构" }}
              </button>
              <button type="button" :disabled="!isOrgAdmin" @click="openGrants(row)">
                字段授权
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

    <div v-if="grantsOpen" class="modal-backdrop" @click.self="closeGrants">
      <div class="modal modal-wide grants-modal" role="dialog" aria-labelledby="grants-title">
        <header class="grants-head">
          <div>
            <h2 id="grants-title">字段授权</h2>
            <p v-if="grantsDs">
              {{ grantsDs.name }} · 勾选表时默认全选其列；保存后问数仅可用授权列。
            </p>
          </div>
          <button type="button" class="ghost" @click="closeGrants">关闭</button>
        </header>

        <p v-if="grantsError" class="banner error" role="alert">{{ grantsError }}</p>

        <div v-if="grantsLoading" class="empty">加载结构…</div>
        <div v-else-if="!grantTables.length" class="empty">
          暂无探测结果。请先点击「刷新结构」。
        </div>
        <div v-else class="grant-tree">
          <div v-for="table in grantTables" :key="tableKey(table)" class="grant-table">
            <label class="grant-table-check">
              <input
                type="checkbox"
                :checked="isTableChecked(table)"
                :indeterminate.prop="isTableIndeterminate(table)"
                @change="onToggleTable(table, ($event.target as HTMLInputElement).checked)"
              />
              <span class="mono">{{ table.schema_name }}.{{ table.table_name }}</span>
              <span class="pill">{{ table.columns.length }} 列</span>
            </label>
            <ul class="grant-cols">
              <li v-for="col in table.columns" :key="col.name">
                <label class="check">
                  <input
                    type="checkbox"
                    :checked="isColumnChecked(table, col.name)"
                    @change="
                      onToggleColumn(table, col.name, ($event.target as HTMLInputElement).checked)
                    "
                  />
                  <span class="mono">{{ col.name }}</span>
                  <span class="col-type">{{ col.data_type || "—" }}</span>
                </label>
              </li>
            </ul>
          </div>
        </div>

        <div class="modal-actions">
          <button type="button" class="ghost" @click="closeGrants">取消</button>
          <button
            type="button"
            class="primary"
            :disabled="grantsSaving || grantsLoading"
            @click="onSaveGrants"
          >
            {{ grantsSaving ? "保存中…" : "保存授权" }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import {
  createDatasource,
  deleteDatasource,
  fetchDatasourceSchema,
  fetchMe,
  friendlyError,
  introspectDatasource,
  listDatasources,
  saveDatasourceGrants,
  setDefaultDatasource,
  testDatasource,
  updateDatasource,
  type Datasource,
  type DatasourceSchemaTable,
} from "../../api";

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
const introspectingId = ref<number | null>(null);

const grantsOpen = ref(false);
const grantsDs = ref<Datasource | null>(null);
const grantTables = ref<DatasourceSchemaTable[]>([]);
/** Selected column names per `schema.table` key. */
const selectedColumns = ref<Record<string, Set<string>>>({});
const grantsLoading = ref(false);
const grantsSaving = ref(false);
const grantsError = ref("");

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

function tableKey(table: Pick<DatasourceSchemaTable, "schema_name" | "table_name">): string {
  return `${table.schema_name}.${table.table_name}`;
}

function isColumnChecked(
  table: Pick<DatasourceSchemaTable, "schema_name" | "table_name">,
  columnName: string,
): boolean {
  return selectedColumns.value[tableKey(table)]?.has(columnName) ?? false;
}

function isTableChecked(table: DatasourceSchemaTable): boolean {
  const selected = selectedColumns.value[tableKey(table)];
  if (!table.columns.length) return selected != null;
  if (!selected) return false;
  return table.columns.every((c) => selected.has(c.name));
}

function isTableIndeterminate(table: DatasourceSchemaTable): boolean {
  const selected = selectedColumns.value[tableKey(table)];
  if (!selected || !table.columns.length) return false;
  const count = table.columns.filter((c) => selected.has(c.name)).length;
  return count > 0 && count < table.columns.length;
}

function onToggleTable(table: DatasourceSchemaTable, checked: boolean) {
  const key = tableKey(table);
  if (checked) {
    // Checking a table selects all its columns by default.
    selectedColumns.value = {
      ...selectedColumns.value,
      [key]: new Set(table.columns.map((c) => c.name)),
    };
  } else {
    const next = { ...selectedColumns.value };
    delete next[key];
    selectedColumns.value = next;
  }
}

function onToggleColumn(
  table: DatasourceSchemaTable,
  columnName: string,
  checked: boolean,
) {
  const key = tableKey(table);
  const next = new Set(selectedColumns.value[key] ?? []);
  if (checked) {
    next.add(columnName);
  } else {
    next.delete(columnName);
  }
  if (next.size === 0) {
    const copy = { ...selectedColumns.value };
    delete copy[key];
    selectedColumns.value = copy;
  } else {
    selectedColumns.value = { ...selectedColumns.value, [key]: next };
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

async function onRefreshSchema(row: Datasource) {
  if (!isOrgAdmin.value) return;
  introspectingId.value = row.id;
  error.value = "";
  note.value = "";
  try {
    const result = await introspectDatasource(row.id);
    note.value = `已刷新「${row.name}」结构：${result.tables} 表 / ${result.columns} 列`;
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    introspectingId.value = null;
  }
}

async function openGrants(row: Datasource) {
  if (!isOrgAdmin.value) return;
  grantsDs.value = row;
  grantsOpen.value = true;
  grantsError.value = "";
  grantsLoading.value = true;
  grantTables.value = [];
  selectedColumns.value = {};
  try {
    const schema = await fetchDatasourceSchema(row.id);
    grantTables.value = schema.tables ?? [];
    const next: Record<string, Set<string>> = {};
    for (const table of grantTables.value) {
      const cols = table.columns.filter((c) => c.granted).map((c) => c.name);
      if (table.granted || cols.length) {
        // Prefer explicit column grants; if table granted with no column flags, select all.
        next[tableKey(table)] = new Set(
          cols.length ? cols : table.columns.map((c) => c.name),
        );
      }
    }
    selectedColumns.value = next;
  } catch (err) {
    grantsError.value = friendlyError(err);
  } finally {
    grantsLoading.value = false;
  }
}

function closeGrants() {
  grantsOpen.value = false;
  grantsDs.value = null;
  grantTables.value = [];
  selectedColumns.value = {};
  grantsError.value = "";
}

async function onSaveGrants() {
  if (!isOrgAdmin.value || !grantsDs.value) return;
  grantsSaving.value = true;
  grantsError.value = "";
  error.value = "";
  note.value = "";
  try {
    const tables = grantTables.value
      .map((table) => {
        const key = tableKey(table);
        const selected = selectedColumns.value[key];
        if (!selected || selected.size === 0) return null;
        return {
          schema_name: table.schema_name,
          table_name: table.table_name,
          columns: table.columns.map((c) => c.name).filter((name) => selected.has(name)),
        };
      })
      .filter((t): t is NonNullable<typeof t> => t != null && t.columns.length > 0);

    const result = await saveDatasourceGrants(grantsDs.value.id, tables);
    note.value = `已保存「${grantsDs.value.name}」授权：${result.tables} 表 / ${result.columns} 列`;
    closeGrants();
  } catch (err) {
    grantsError.value = friendlyError(err);
  } finally {
    grantsSaving.value = false;
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
  max-height: min(90vh, 860px);
  overflow: auto;
}

.grants-modal {
  display: grid;
  gap: 0.85rem;
  align-content: start;
}

.grants-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.grants-head h2 {
  margin: 0;
}

.grants-head p {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.82rem;
  line-height: 1.45;
}

.grant-tree {
  display: grid;
  gap: 0.65rem;
  max-height: min(55vh, 520px);
  overflow: auto;
  padding-right: 0.15rem;
}

.grant-table {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface-muted);
  padding: 0.55rem 0.7rem 0.65rem;
}

.grant-table-check {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem 0.65rem;
  font-weight: 600;
  color: var(--ink);
}

.grant-table-check input {
  width: auto;
  margin: 0;
}

.grant-cols {
  list-style: none;
  margin: 0.55rem 0 0;
  padding: 0 0 0 1.35rem;
  display: grid;
  gap: 0.35rem;
}

.grant-cols .check {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem 0.55rem;
}

.grant-cols .check input {
  width: auto;
  margin: 0;
}

.col-type {
  font-size: 0.75rem;
  color: var(--muted);
}
</style>
