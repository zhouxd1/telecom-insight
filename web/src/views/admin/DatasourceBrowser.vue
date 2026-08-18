<template>
  <section class="browser">
    <header class="page-head browser-head">
      <div class="browser-title">
        <button type="button" class="ghost" @click="emit('back')">← 返回列表</button>
        <div>
          <h1>{{ ds.name }} · <span class="mono">{{ ds.db_type }}</span></h1>
          <p>浏览库表结构与样例数据；勾选列并保存后用于问数授权。</p>
        </div>
      </div>
      <button
        type="button"
        class="primary"
        :disabled="!isOrgAdmin || introspecting"
        @click="onRefreshSchema"
      >
        {{ introspecting ? "刷新中…" : "刷新结构" }}
      </button>
    </header>

    <div v-if="loading" class="empty">加载结构…</div>
    <div v-else-if="!tables.length" class="empty">暂无探测结果。请先点击刷新结构。</div>
    <div v-else class="browser-body">
      <aside class="tree-pane table-card">
        <div v-for="group in schemaGroups" :key="group.schema" class="schema-group">
          <div class="schema-label mono">{{ group.schema }}</div>
          <button
            v-for="table in group.tables"
            :key="tableKey(table)"
            type="button"
            class="tree-item"
            :class="{ active: isSelected(table) }"
            @click="selectTable(table)"
          >
            <span class="mono">{{ table.table_name }}</span>
            <span v-if="table.table_kind" class="pill">{{ table.table_kind }}</span>
          </button>
        </div>
      </aside>

      <div class="detail-pane table-card">
        <div v-if="!selected" class="empty">请选择左侧表。</div>
        <template v-else>
          <div class="detail-head">
            <h2 class="mono">{{ selected.schema_name }}.{{ selected.table_name }}</h2>
            <div class="tabs" role="tablist">
              <button
                type="button"
                role="tab"
                :aria-selected="activeTab === 'structure'"
                :class="{ active: activeTab === 'structure' }"
                @click="activeTab = 'structure'"
              >
                结构
              </button>
              <button
                type="button"
                role="tab"
                :aria-selected="activeTab === 'data'"
                :class="{ active: activeTab === 'data' }"
                @click="switchToData"
              >
                数据
              </button>
            </div>
          </div>

          <div v-if="activeTab === 'structure'" class="structure-pane">
            <p class="meta-line">
              <span class="pill">{{ selected.table_kind || "—" }}</span>
              <span>{{ displayOrDash(selected.table_comment) }}</span>
            </p>

            <div class="col-grid-wrap">
              <table>
                <thead>
                  <tr>
                    <th>授权</th>
                    <th>列</th>
                    <th>类型</th>
                    <th>可空</th>
                    <th>默认</th>
                    <th>主键</th>
                    <th>注释</th>
                  </tr>
                </thead>
                <tbody>
                  <tr class="table-grant-row">
                    <td>
                      <input
                        type="checkbox"
                        :checked="isTableChecked(selected)"
                        :indeterminate.prop="isTableIndeterminate(selected)"
                        :disabled="!isOrgAdmin"
                        @change="
                          onToggleTable(selected, ($event.target as HTMLInputElement).checked)
                        "
                      />
                    </td>
                    <td colspan="6" class="muted">整表（勾选默认全列）</td>
                  </tr>
                  <tr v-for="col in sortedColumns(selected)" :key="col.name">
                    <td>
                      <input
                        type="checkbox"
                        :checked="isColumnChecked(selected, col.name)"
                        :disabled="!isOrgAdmin"
                        @change="
                          onToggleColumn(
                            selected,
                            col.name,
                            ($event.target as HTMLInputElement).checked,
                          )
                        "
                      />
                    </td>
                    <td class="mono">{{ col.name }}</td>
                    <td class="mono">{{ displayOrDash(col.data_type) }}</td>
                    <td>{{ col.nullable ? "是" : "否" }}</td>
                    <td class="mono clip">{{ displayOrDash(col.column_default) }}</td>
                    <td>{{ col.is_primary_key ? "是" : "—" }}</td>
                    <td class="clip">{{ displayOrDash(col.column_comment) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-if="isOrgAdmin" class="structure-actions">
              <button
                type="button"
                class="primary"
                :disabled="grantsSaving"
                @click="onSaveGrants"
              >
                {{ grantsSaving ? "保存中…" : "保存授权" }}
              </button>
            </div>
          </div>

          <div v-else class="data-pane">
            <div v-if="previewLoading" class="empty">加载预览…</div>
            <div v-else-if="!preview" class="empty">暂无预览数据。</div>
            <template v-else>
              <p v-if="preview.truncated" class="banner ok">已截断</p>
              <div class="preview-wrap">
                <table>
                  <thead>
                    <tr>
                      <th v-for="col in preview.columns" :key="col" class="mono">{{ col }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="!preview.rows.length">
                      <td :colspan="Math.max(preview.columns.length, 1)" class="empty">无行</td>
                    </tr>
                    <tr v-for="(row, idx) in preview.rows" :key="idx">
                      <td v-for="col in preview.columns" :key="col" class="mono">
                        {{ formatCell(row[col]) }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>
          </div>
        </template>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  fetchDatasourceSchema,
  friendlyError,
  introspectDatasource,
  previewDatasourceTable,
  saveDatasourceGrants,
  type Datasource,
  type DatasourcePreview,
  type DatasourceSchemaColumn,
  type DatasourceSchemaTable,
} from "../../api";

const props = defineProps<{
  ds: Datasource;
  isOrgAdmin: boolean;
}>();

const emit = defineEmits<{
  back: [];
  note: [message: string];
  error: [message: string];
}>();

const loading = ref(false);
const introspecting = ref(false);
const grantsSaving = ref(false);
const tables = ref<DatasourceSchemaTable[]>([]);
const selected = ref<DatasourceSchemaTable | null>(null);
const activeTab = ref<"structure" | "data">("structure");
/** Selected column names per `schema.table` key. */
const selectedColumns = ref<Record<string, Set<string>>>({});
const preview = ref<DatasourcePreview | null>(null);
const previewLoading = ref(false);
const previewSeq = ref(0);

const schemaGroups = computed(() => {
  const map = new Map<string, DatasourceSchemaTable[]>();
  for (const table of tables.value) {
    const list = map.get(table.schema_name) ?? [];
    list.push(table);
    map.set(table.schema_name, list);
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([schema, groupTables]) => ({
      schema,
      tables: [...groupTables].sort((a, b) => a.table_name.localeCompare(b.table_name)),
    }));
});

function tableKey(table: Pick<DatasourceSchemaTable, "schema_name" | "table_name">): string {
  return `${table.schema_name}.${table.table_name}`;
}

function displayOrDash(value?: string | null): string {
  if (value == null || value === "") return "—";
  return value;
}

function formatCell(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function sortedColumns(table: DatasourceSchemaTable): DatasourceSchemaColumn[] {
  return [...table.columns].sort((a, b) => {
    const ao = a.ordinal_position ?? Number.MAX_SAFE_INTEGER;
    const bo = b.ordinal_position ?? Number.MAX_SAFE_INTEGER;
    if (ao !== bo) return ao - bo;
    return a.name.localeCompare(b.name);
  });
}

function isSelected(table: DatasourceSchemaTable): boolean {
  return (
    selected.value != null &&
    selected.value.schema_name === table.schema_name &&
    selected.value.table_name === table.table_name
  );
}

function isColumnChecked(
  table: Pick<DatasourceSchemaTable, "schema_name" | "table_name">,
  columnName: string,
): boolean {
  return selectedColumns.value[tableKey(table)]?.has(columnName) ?? false;
}

function isTableChecked(table: DatasourceSchemaTable): boolean {
  const selectedSet = selectedColumns.value[tableKey(table)];
  if (!table.columns.length) return selectedSet != null;
  if (!selectedSet) return false;
  return table.columns.every((c) => selectedSet.has(c.name));
}

function isTableIndeterminate(table: DatasourceSchemaTable): boolean {
  const selectedSet = selectedColumns.value[tableKey(table)];
  if (!selectedSet || !table.columns.length) return false;
  const count = table.columns.filter((c) => selectedSet.has(c.name)).length;
  return count > 0 && count < table.columns.length;
}

function onToggleTable(table: DatasourceSchemaTable, checked: boolean) {
  if (!props.isOrgAdmin) return;
  const key = tableKey(table);
  if (checked) {
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
  if (!props.isOrgAdmin) return;
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

function applyGrantedSelection(schemaTables: DatasourceSchemaTable[]) {
  const next: Record<string, Set<string>> = {};
  for (const table of schemaTables) {
    const cols = table.columns.filter((c) => c.granted).map((c) => c.name);
    if (table.granted || cols.length) {
      next[tableKey(table)] = new Set(cols.length ? cols : table.columns.map((c) => c.name));
    }
  }
  selectedColumns.value = next;
}

function restoreSelection(prev: DatasourceSchemaTable | null) {
  if (!prev) {
    selected.value = tables.value[0] ?? null;
    return;
  }
  selected.value =
    tables.value.find(
      (t) => t.schema_name === prev.schema_name && t.table_name === prev.table_name,
    ) ??
    tables.value[0] ??
    null;
}

async function loadSchema() {
  loading.value = true;
  try {
    const schema = await fetchDatasourceSchema(props.ds.id);
    const prev = selected.value;
    tables.value = schema.tables ?? [];
    applyGrantedSelection(tables.value);
    restoreSelection(prev);
    preview.value = null;
    if (activeTab.value === "data" && selected.value) {
      void loadPreview();
    }
  } catch (err) {
    emit("error", friendlyError(err));
  } finally {
    loading.value = false;
  }
}

async function onRefreshSchema() {
  if (!props.isOrgAdmin) return;
  introspecting.value = true;
  try {
    const result = await introspectDatasource(props.ds.id);
    emit("note", `已刷新「${props.ds.name}」结构：${result.tables} 表 / ${result.columns} 列`);
    await loadSchema();
  } catch (err) {
    emit("error", friendlyError(err));
  } finally {
    introspecting.value = false;
  }
}

async function onSaveGrants() {
  if (!props.isOrgAdmin) return;
  grantsSaving.value = true;
  try {
    const payload = tables.value
      .map((table) => {
        const key = tableKey(table);
        const selectedSet = selectedColumns.value[key];
        if (!selectedSet || selectedSet.size === 0) return null;
        return {
          schema_name: table.schema_name,
          table_name: table.table_name,
          columns: table.columns.map((c) => c.name).filter((name) => selectedSet.has(name)),
        };
      })
      .filter((t): t is NonNullable<typeof t> => t != null && t.columns.length > 0);

    const result = await saveDatasourceGrants(props.ds.id, payload);
    emit("note", `已保存「${props.ds.name}」授权：${result.tables} 表 / ${result.columns} 列`);
    await loadSchema();
  } catch (err) {
    emit("error", friendlyError(err));
  } finally {
    grantsSaving.value = false;
  }
}

function selectTable(table: DatasourceSchemaTable) {
  selected.value = table;
  if (activeTab.value === "data") {
    void loadPreview();
  }
}

function switchToData() {
  activeTab.value = "data";
  void loadPreview();
}

async function loadPreview() {
  if (!selected.value) {
    preview.value = null;
    return;
  }
  const schemaName = selected.value.schema_name;
  const tableName = selected.value.table_name;
  const seq = ++previewSeq.value;
  previewLoading.value = true;
  try {
    const result = await previewDatasourceTable(props.ds.id, schemaName, tableName, 50);
    if (
      !selected.value ||
      selected.value.schema_name !== schemaName ||
      selected.value.table_name !== tableName
    ) {
      return;
    }
    preview.value = result;
  } catch (err) {
    if (
      !selected.value ||
      selected.value.schema_name !== schemaName ||
      selected.value.table_name !== tableName
    ) {
      return;
    }
    preview.value = null;
    emit("error", friendlyError(err));
  } finally {
    if (seq === previewSeq.value) {
      previewLoading.value = false;
    }
  }
}

watch(
  () => props.ds.id,
  () => {
    selected.value = null;
    activeTab.value = "structure";
    preview.value = null;
    void loadSchema();
  },
);

onMounted(() => {
  void loadSchema();
});
</script>

<style src="./admin-shared.css"></style>
<style scoped>
.browser {
  display: grid;
  gap: 0.85rem;
}

.browser-head {
  margin-bottom: 0;
}

.browser-title {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  min-width: 0;
}

.browser-title h1 {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--ink);
}

.browser-title p {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.85rem;
  line-height: 1.5;
}

.browser-body {
  display: grid;
  grid-template-columns: minmax(200px, 260px) 1fr;
  gap: 0.85rem;
  min-height: 420px;
  align-items: stretch;
}

.tree-pane {
  padding: 0.55rem;
  overflow: auto;
  max-height: min(70vh, 720px);
}

.schema-group + .schema-group {
  margin-top: 0.65rem;
}

.schema-label {
  padding: 0.35rem 0.45rem;
  color: var(--muted);
  font-weight: 600;
  font-size: 0.75rem;
}

.tree-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
  border: 1px solid transparent;
  border-radius: var(--radius);
  background: transparent;
  color: var(--text);
  padding: 0.4rem 0.5rem;
  text-align: left;
  cursor: pointer;
  font-size: 0.84rem;
}

.tree-item:hover {
  background: var(--surface-muted);
}

.tree-item.active {
  background: var(--accent-soft);
  border-color: #ccfbf1;
  color: var(--accent-ink);
}

.detail-pane {
  display: grid;
  grid-template-rows: auto 1fr;
  min-width: 0;
  overflow: hidden;
}

.detail-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
  padding: 0.75rem 0.85rem;
  border-bottom: 1px solid var(--line);
}

.detail-head h2 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--ink);
}

.tabs {
  display: inline-flex;
  gap: 0.25rem;
  padding: 0.15rem;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface-muted);
}

.tabs button {
  border: 0;
  border-radius: calc(var(--radius) - 2px);
  background: transparent;
  color: var(--muted);
  padding: 0.3rem 0.7rem;
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
}

.tabs button.active {
  background: var(--surface);
  color: var(--ink);
  box-shadow: var(--shadow-sm);
}

.structure-pane,
.data-pane {
  display: grid;
  gap: 0.75rem;
  padding: 0.75rem 0.85rem 0.95rem;
  min-height: 0;
}

.meta-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
  margin: 0;
  color: var(--muted);
  font-size: 0.85rem;
}

.col-grid-wrap,
.preview-wrap {
  overflow: auto;
  max-height: min(55vh, 560px);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.col-grid-wrap table,
.preview-wrap table {
  margin: 0;
}

.table-grant-row td {
  background: var(--surface-muted);
}

.muted {
  color: var(--muted);
  font-size: 0.82rem;
}

.structure-actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 860px) {
  .browser-body {
    grid-template-columns: 1fr;
  }

  .tree-pane {
    max-height: 220px;
  }
}
</style>
