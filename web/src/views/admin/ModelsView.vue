<template>
  <section class="admin-page">
    <header class="page-head">
      <div>
        <h1>模型配置</h1>
        <p>管理问数引擎使用的大模型接入（同时仅一个启用）。</p>
      </div>
      <button type="button" class="primary" @click="openCreate">新建模型</button>
    </header>

    <p v-if="error" class="banner error" role="alert">{{ error }}</p>
    <p v-if="note" class="banner ok">{{ note }}</p>

    <div class="table-card">
      <div v-if="loading" class="empty">加载中…</div>
      <div v-else-if="!rows.length" class="empty">暂无模型，点击右上角新建。</div>
      <table v-else>
        <thead>
          <tr>
            <th>名称</th>
            <th>模型</th>
            <th>Base URL</th>
            <th>启用</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td>{{ row.name }}</td>
            <td>{{ row.model || "—" }}</td>
            <td class="mono">{{ row.base_url || "—" }}</td>
            <td>
              <span class="pill" :class="{ on: row.enabled }">{{ row.enabled ? "启用" : "停用" }}</span>
            </td>
            <td class="actions">
              <button type="button" @click="openEdit(row)">编辑</button>
              <button type="button" @click="onTest(row)">测试</button>
              <button type="button" class="danger" @click="onDelete(row)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="dialogOpen" class="modal-backdrop" @click.self="closeDialog">
      <form class="modal" @submit.prevent="onSave">
        <h2>{{ editingId == null ? "新建模型" : "编辑模型" }}</h2>
        <label>
          <span>名称</span>
          <input v-model="form.name" required />
        </label>
        <label>
          <span>模型 ID</span>
          <input v-model="form.model" placeholder="如 gpt-4o-mini" />
        </label>
        <label>
          <span>Base URL</span>
          <input v-model="form.base_url" placeholder="https://api.openai.com/v1" />
        </label>
        <label>
          <span>API Key</span>
          <input v-model="form.api_key" type="password" autocomplete="off" />
        </label>
        <label class="check">
          <input v-model="form.enabled" type="checkbox" />
          <span>启用此模型（将停用其他模型）</span>
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
  createModel,
  deleteModel,
  friendlyError,
  listModels,
  testModel,
  updateModel,
  type AiModel,
} from "../../api";

const rows = ref<AiModel[]>([]);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const note = ref("");
const dialogOpen = ref(false);
const editingId = ref<number | null>(null);

const form = reactive({
  name: "",
  model: "",
  base_url: "",
  api_key: "",
  enabled: false,
});

async function refresh() {
  loading.value = true;
  error.value = "";
  try {
    rows.value = await listModels();
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    loading.value = false;
  }
}

function resetForm() {
  form.name = "";
  form.model = "";
  form.base_url = "";
  form.api_key = "";
  form.enabled = false;
}

function openCreate() {
  editingId.value = null;
  resetForm();
  dialogOpen.value = true;
}

function openEdit(row: AiModel) {
  editingId.value = row.id;
  form.name = row.name;
  form.model = row.model;
  form.base_url = row.base_url;
  form.api_key = row.api_key;
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
    const payload = {
      name: form.name.trim(),
      model: form.model.trim(),
      base_url: form.base_url.trim(),
      api_key: form.api_key,
      enabled: form.enabled,
    };
    if (editingId.value == null) {
      await createModel(payload);
    } else {
      await updateModel(editingId.value, payload);
    }
    dialogOpen.value = false;
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  } finally {
    saving.value = false;
  }
}

async function onDelete(row: AiModel) {
  if (!window.confirm(`确认删除模型「${row.name}」？`)) return;
  error.value = "";
  note.value = "";
  try {
    await deleteModel(row.id);
    await refresh();
  } catch (err) {
    error.value = friendlyError(err);
  }
}

async function onTest(row: AiModel) {
  error.value = "";
  note.value = "";
  try {
    const result = await testModel(row.id);
    note.value = `测试「${row.name}」：${result.detail || (result.ok ? "ok" : "failed")}`;
  } catch (err) {
    error.value = friendlyError(err);
  }
}

onMounted(() => {
  void refresh();
});
</script>

<style src="./admin-shared.css"></style>
