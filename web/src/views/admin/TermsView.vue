<template>
  <section class="admin-page">
    <header class="page-head">
      <div>
        <h1>术语库</h1>
        <p>维护业务术语到标准表达与字段映射。</p>
      </div>
      <button type="button" class="primary" @click="openCreate">新建术语</button>
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
      <div v-else-if="!rows.length" class="empty">暂无术语。</div>
      <table v-else>
        <thead>
          <tr>
            <th>业务域</th>
            <th>术语</th>
            <th>标准表达</th>
            <th>映射字段</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td>{{ domainLabel(row.domain) }}</td>
            <td>{{ row.term }}</td>
            <td>{{ row.standard }}</td>
            <td class="mono">{{ row.maps_to || "—" }}</td>
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
        <h2>{{ editingId == null ? "新建术语" : "编辑术语" }}</h2>
        <label>
          <span>业务域</span>
          <select v-model="form.domain" required>
            <option v-for="d in domainOptions" :key="d.id" :value="d.id">{{ d.label }}</option>
          </select>
        </label>
        <label>
          <span>术语</span>
          <input v-model="form.term" required />
        </label>
        <label>
          <span>标准表达</span>
          <input v-model="form.standard" required />
        </label>
        <label>
          <span>映射字段（可选）</span>
          <input v-model="form.maps_to" placeholder="如 arpu" />
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
  createTerm,
  deleteTerm,
  friendlyError,
  listTerms,
  updateTerm,
  type Term,
} from "../../api";

const domainOptions = [
  { id: "biz", label: "经营" },
  { id: "network", label: "网络" },
  { id: "cs", label: "客服" },
] as const;

const rows = ref<Term[]>([]);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const domainFilter = ref("");
const dialogOpen = ref(false);
const editingId = ref<number | null>(null);

const form = reactive({
  domain: "biz",
  term: "",
  standard: "",
  maps_to: "",
});

function domainLabel(domain: string): string {
  return domainOptions.find((d) => d.id === domain)?.label ?? domain;
}

async function refresh() {
  loading.value = true;
  error.value = "";
  try {
    rows.value = await listTerms(domainFilter.value || undefined);
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingId.value = null;
  form.domain = domainFilter.value || "biz";
  form.term = "";
  form.standard = "";
  form.maps_to = "";
  dialogOpen.value = true;
}

function openEdit(row: Term) {
  editingId.value = row.id;
  form.domain = row.domain;
  form.term = row.term;
  form.standard = row.standard;
  form.maps_to = row.maps_to ?? "";
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
      term: form.term.trim(),
      standard: form.standard.trim(),
      maps_to: form.maps_to.trim() || null,
    };
    if (editingId.value == null) {
      await createTerm(payload);
    } else {
      await updateTerm(editingId.value, payload);
    }
    dialogOpen.value = false;
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    saving.value = false;
  }
}

async function onDelete(row: Term) {
  if (!window.confirm(`确认删除术语「${row.term}」？`)) return;
  error.value = "";
  try {
    await deleteTerm(row.id);
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
