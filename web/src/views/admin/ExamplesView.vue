<template>
  <section class="admin-page">
    <header class="page-head">
      <div>
        <h1>SQL 示例</h1>
        <p>维护问数检索用的问题–SQL 样例对。</p>
      </div>
      <button type="button" class="primary" @click="openCreate">新建示例</button>
    </header>

    <div class="filters">
      <select v-model="domainFilter" aria-label="按业务域筛选">
        <option value="">全部业务域</option>
        <option v-for="d in domainOptions" :key="d.id" :value="d.id">{{ d.label }}</option>
      </select>
    </div>

    <p v-if="error" class="banner error" role="alert">{{ error }}</p>

    <div class="table-card">
      <div v-if="loading" class="empty">加载中…</div>
      <div v-else-if="!rows.length" class="empty">暂无 SQL 示例。</div>
      <table v-else>
        <thead>
          <tr>
            <th>业务域</th>
            <th>问题</th>
            <th>SQL</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td>{{ domainLabel(row.domain) }}</td>
            <td class="clip" :title="row.question">{{ row.question }}</td>
            <td class="mono" :title="row.sql">{{ row.sql }}</td>
            <td class="actions">
              <button type="button" @click="openEdit(row)">编辑</button>
              <button type="button" class="danger" @click="onDelete(row)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="dialogOpen" class="modal-backdrop" @click.self="closeDialog">
      <form class="modal" @submit.prevent="onSave">
        <h2>{{ editingId == null ? "新建 SQL 示例" : "编辑 SQL 示例" }}</h2>
        <label>
          <span>业务域</span>
          <select v-model="form.domain" required>
            <option v-for="d in domainOptions" :key="d.id" :value="d.id">{{ d.label }}</option>
          </select>
        </label>
        <label>
          <span>问题</span>
          <input v-model="form.question" required />
        </label>
        <label>
          <span>SQL</span>
          <textarea v-model="form.sql" required />
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
import { onMounted, reactive, ref, watch } from "vue";
import {
  createExample,
  deleteExample,
  friendlyError,
  listExamples,
  updateExample,
  type SqlExample,
} from "../../api";

const domainOptions = [
  { id: "biz", label: "经营" },
  { id: "network", label: "网络" },
  { id: "cs", label: "客服" },
] as const;

const rows = ref<SqlExample[]>([]);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const domainFilter = ref("");
const dialogOpen = ref(false);
const editingId = ref<number | null>(null);

const form = reactive({
  domain: "biz",
  question: "",
  sql: "",
});

function domainLabel(domain: string): string {
  return domainOptions.find((d) => d.id === domain)?.label ?? domain;
}

async function refresh() {
  loading.value = true;
  error.value = "";
  try {
    rows.value = await listExamples(domainFilter.value || undefined);
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingId.value = null;
  form.domain = domainFilter.value || "biz";
  form.question = "";
  form.sql = "";
  dialogOpen.value = true;
}

function openEdit(row: SqlExample) {
  editingId.value = row.id;
  form.domain = row.domain;
  form.question = row.question;
  form.sql = row.sql;
  dialogOpen.value = true;
}

function closeDialog() {
  dialogOpen.value = false;
}

async function onSave() {
  saving.value = true;
  error.value = "";
  try {
    const payload = {
      domain: form.domain,
      question: form.question.trim(),
      sql: form.sql.trim(),
    };
    if (editingId.value == null) {
      await createExample(payload);
    } else {
      await updateExample(editingId.value, payload);
    }
    dialogOpen.value = false;
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    saving.value = false;
  }
}

async function onDelete(row: SqlExample) {
  if (!window.confirm(`确认删除示例「${row.question}」？`)) return;
  error.value = "";
  try {
    await deleteExample(row.id);
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  }
}

watch(domainFilter, () => {
  void refresh();
});

onMounted(() => {
  void refresh();
});
</script>

<style src="./admin-shared.css"></style>
