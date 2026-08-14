<template>
  <div class="chat-page">
    <section class="workspace">
      <nav class="domain-tabs" aria-label="业务域">
        <button
          v-for="tab in domainTabs"
          :key="tab.id"
          type="button"
          :class="{ active: activeDomain === tab.id }"
          @click="switchDomain(tab.id)"
        >
          {{ tab.label }}
        </button>
      </nav>

      <div class="recommended" v-if="recommended.length">
        <span class="label">推荐提问</span>
        <div class="chips">
          <button
            v-for="item in recommended"
            :key="item.id"
            type="button"
            class="chip"
            :disabled="loading"
            @click="askRecommended(item.text)"
          >
            {{ item.text }}
          </button>
        </div>
      </div>

      <form class="ask-box" @submit.prevent="sendAsk">
        <textarea
          v-model="question"
          rows="3"
          placeholder="输入业务问题，例如：上月 ARPU 是多少？"
          :disabled="loading"
          @keydown.enter.exact.prevent="sendAsk"
        />
        <div class="ask-actions">
          <p v-if="statusNote" class="status-note">{{ statusNote }}</p>
          <button type="submit" :disabled="loading || !question.trim()">
            {{ loading ? "分析中…" : "发送" }}
          </button>
        </div>
      </form>

      <ResultPanel
        :loading="loading"
        :error="panelError"
        :result="result"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ask, friendlyError, listRecommended } from "../api";
import type { AskResponse, RecommendedItem } from "../api";
import ResultPanel from "../components/ResultPanel.vue";

const domainTabs = [
  { id: "biz", label: "经营" },
  { id: "network", label: "网络" },
  { id: "cs", label: "客服" },
] as const;

const activeDomain = ref<string>("biz");
const recommended = ref<RecommendedItem[]>([]);
const question = ref("");
const loading = ref(false);
const panelError = ref("");
const statusNote = ref("");
const result = ref<AskResponse | null>(null);

async function loadRecommended(domainId: string) {
  statusNote.value = "";
  try {
    recommended.value = await listRecommended(domainId);
  } catch (err) {
    recommended.value = [];
    statusNote.value = friendlyError(err);
  }
}

async function switchDomain(domainId: string) {
  if (activeDomain.value === domainId) return;
  activeDomain.value = domainId;
  result.value = null;
  panelError.value = "";
  await loadRecommended(domainId);
}

async function sendAsk() {
  const q = question.value.trim();
  if (!q || loading.value) return;

  loading.value = true;
  panelError.value = "";
  statusNote.value = "";
  result.value = null;

  try {
    const resp = await ask(activeDomain.value, q);
    result.value = resp;
    if (resp.status === "clarify" || resp.status === "error") {
      panelError.value = resp.message || "问题需要进一步澄清。";
    } else if (resp.message && resp.status !== "ok") {
      panelError.value = resp.message;
    }
  } catch (err) {
    panelError.value = friendlyError(err);
  } finally {
    loading.value = false;
  }
}

async function askRecommended(text: string) {
  question.value = text;
  await sendAsk();
}

onMounted(() => {
  void loadRecommended(activeDomain.value);
});
</script>

<style scoped>
.chat-page {
  height: 100%;
  min-height: calc(100vh - 58px);
  padding: 1.25rem 1.25rem 2rem;
}

.workspace {
  max-width: 980px;
  margin: 0 auto;
  display: grid;
  gap: 1rem;
  animation: rise 380ms ease-out;
}

.domain-tabs {
  display: flex;
  gap: 0.5rem;
  padding: 0.3rem;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--line);
  width: fit-content;
}

.domain-tabs button {
  border: 0;
  background: transparent;
  color: var(--muted);
  padding: 0.55rem 1rem;
  border-radius: 10px;
  font-weight: 600;
}

.domain-tabs button.active {
  background: linear-gradient(135deg, var(--ink) 0%, var(--teal) 100%);
  color: #f4fffc;
}

.recommended {
  display: grid;
  gap: 0.55rem;
}

.label {
  font-size: 0.82rem;
  color: var(--muted);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.chip {
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.8);
  color: var(--ink-soft);
  border-radius: 999px;
  padding: 0.45rem 0.85rem;
  transition: background 140ms ease, border-color 140ms ease;
}

.chip:hover:not(:disabled) {
  border-color: var(--teal);
  background: var(--teal-mist);
}

.ask-box {
  display: grid;
  gap: 0.7rem;
  padding: 1rem;
  border-radius: var(--radius);
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: var(--shadow);
}

textarea {
  width: 100%;
  resize: vertical;
  min-height: 84px;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.75rem 0.85rem;
  outline: none;
  background: #fff;
}

textarea:focus {
  border-color: var(--teal);
  box-shadow: 0 0 0 3px var(--teal-mist);
}

.ask-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.status-note {
  margin: 0;
  color: var(--danger);
  font-size: 0.88rem;
}

.ask-actions button {
  margin-left: auto;
  border: 0;
  border-radius: 10px;
  padding: 0.65rem 1.15rem;
  background: linear-gradient(135deg, var(--ink) 0%, var(--teal) 100%);
  color: #f4fffc;
  font-weight: 600;
}

.ask-actions button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 640px) {
  .domain-tabs {
    width: 100%;
  }

  .domain-tabs button {
    flex: 1;
  }

  .ask-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .ask-actions button {
    margin-left: 0;
  }
}
</style>
