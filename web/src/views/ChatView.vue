<template>
  <div class="chatbi">
    <aside class="session-pane">
      <div class="session-toolbar">
        <button type="button" class="new-btn" @click="onCreateSession">新建对话</button>
        <select v-model="createDomain" class="domain-select" aria-label="新建会话业务域">
          <option v-for="d in domainOptions" :key="d.id" :value="d.id">{{ d.label }}</option>
        </select>
      </div>

      <div v-if="sessionsLoading" class="pane-hint">加载会话…</div>
      <div v-else-if="!sessions.length" class="pane-hint">暂无会话，点击上方新建。</div>

      <ul v-else class="session-list" role="listbox" aria-label="会话列表">
        <li
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === activeSessionId }"
          role="option"
          :aria-selected="s.id === activeSessionId"
          @click="selectSession(s.id)"
        >
          <div class="session-main">
            <strong>{{ s.title || "新会话" }}</strong>
            <span class="domain-badge">{{ domainLabel(s.domain) }}</span>
          </div>
          <div class="session-actions" @click.stop>
            <button type="button" class="icon-btn" title="重命名" @click="onRename(s)">改</button>
            <button type="button" class="icon-btn danger" title="删除" @click="onDelete(s)">删</button>
          </div>
        </li>
      </ul>
    </aside>

    <section class="thread-pane">
      <header class="thread-head">
        <div>
          <h1>{{ activeSession?.title || "问数工作台" }}</h1>
          <p v-if="activeSession">
            当前域
            <span class="domain-badge">{{ domainLabel(activeSession.domain) }}</span>
          </p>
          <p v-else>选择或新建会话开始提问</p>
        </div>
      </header>

      <div ref="threadEl" class="thread" aria-live="polite">
        <div v-if="!activeSessionId" class="empty-state">
          <img src="/logo.svg" alt="" class="empty-logo" />
          <h2>元景.智数</h2>
          <p>用自然语言探查经营、网络与客服数据。</p>
        </div>

        <div v-else-if="messagesLoading" class="empty-state soft">加载消息…</div>

        <div v-else-if="!threadItems.length" class="empty-state">
          <img src="/logo.svg" alt="" class="empty-logo" />
          <h2>开始一段新对话</h2>
          <p>选择推荐问题，或在下方输入业务问题。</p>
        </div>

        <template v-else>
          <div v-for="item in threadItems" :key="item.key" class="msg-row" :class="item.role">
            <div v-if="item.role === 'user'" class="user-bubble">{{ item.text }}</div>
            <AssistantCard v-else-if="item.result" :result="item.result" />
            <div v-else class="user-bubble assistant-plain">{{ item.text }}</div>
          </div>
        </template>

        <div v-if="asking" class="msg-row assistant">
          <div class="thinking">
            <span class="pulse" />
            正在理解问题并生成分析…
          </div>
        </div>
      </div>

      <footer class="composer">
        <div v-if="recommended.length" class="chips" aria-label="推荐提问">
          <button
            v-for="item in recommended"
            :key="item.id"
            type="button"
            class="chip"
            :disabled="asking || !activeSessionId"
            @click="askRecommended(item.text)"
          >
            {{ item.text }}
          </button>
        </div>

        <form class="composer-form" @submit.prevent="sendAsk">
          <textarea
            v-model="question"
            rows="2"
            placeholder="输入业务问题，Enter 发送，Shift+Enter 换行"
            :disabled="asking || !activeSessionId"
            @keydown.enter.exact.prevent="sendAsk"
          />
          <div class="composer-actions">
            <p v-if="errorNote" class="error-note" role="alert">{{ errorNote }}</p>
            <button type="submit" :disabled="asking || !activeSessionId || !question.trim()">
              {{ asking ? "分析中…" : "发送" }}
            </button>
          </div>
        </form>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import {
  askInSession,
  createSession,
  deleteSession,
  friendlyError,
  listMessages,
  listRecommended,
  listSessions,
  updateSession,
} from "../api";
import type { AskResponse, ChatMessage, ChatSession, RecommendedItem } from "../api";
import AssistantCard from "../components/AssistantCard.vue";

type ThreadItem = {
  key: string;
  role: "user" | "assistant";
  text: string;
  result?: AskResponse;
};

const domainOptions = [
  { id: "biz", label: "经营" },
  { id: "network", label: "网络" },
  { id: "cs", label: "客服" },
] as const;

const sessions = ref<ChatSession[]>([]);
const sessionsLoading = ref(false);
const activeSessionId = ref<number | null>(null);
const createDomain = ref("biz");
const messages = ref<ChatMessage[]>([]);
const messagesLoading = ref(false);
const recommended = ref<RecommendedItem[]>([]);
const question = ref("");
const asking = ref(false);
const errorNote = ref("");
const threadEl = ref<HTMLElement | null>(null);

const activeSession = computed(
  () => sessions.value.find((s) => s.id === activeSessionId.value) ?? null,
);

const threadItems = computed<ThreadItem[]>(() =>
  messages.value.map((m) => {
    if (m.role === "user") {
      let text = m.content_json;
      try {
        const parsed = JSON.parse(m.content_json) as { text?: string };
        text = parsed.text ?? m.content_json;
      } catch {
        /* keep raw */
      }
      return { key: `m-${m.id}`, role: "user" as const, text };
    }

    try {
      const parsed = JSON.parse(m.content_json) as AskResponse;
      return {
        key: `m-${m.id}`,
        role: "assistant" as const,
        text: parsed.message || "",
        result: {
          status: parsed.status ?? "ok",
          message: parsed.message ?? "",
          sql: parsed.sql ?? null,
          rows: parsed.rows ?? [],
          truncated: Boolean(parsed.truncated),
          chart: parsed.chart ?? {},
          narrative: parsed.narrative ?? "",
          steps: parsed.steps ?? [],
        },
      };
    } catch {
      return { key: `m-${m.id}`, role: "assistant" as const, text: m.content_json };
    }
  }),
);

function domainLabel(domain: string): string {
  return domainOptions.find((d) => d.id === domain)?.label ?? domain;
}

async function scrollThread() {
  await nextTick();
  if (threadEl.value) {
    threadEl.value.scrollTop = threadEl.value.scrollHeight;
  }
}

async function refreshSessions(selectId?: number | null) {
  sessionsLoading.value = true;
  errorNote.value = "";
  try {
    sessions.value = await listSessions();
    if (selectId != null) {
      activeSessionId.value = selectId;
    } else if (
      activeSessionId.value != null &&
      !sessions.value.some((s) => s.id === activeSessionId.value)
    ) {
      activeSessionId.value = sessions.value[0]?.id ?? null;
    } else if (activeSessionId.value == null && sessions.value.length) {
      activeSessionId.value = sessions.value[0].id;
    }
  } catch (err) {
    errorNote.value = friendlyError(err);
  } finally {
    sessionsLoading.value = false;
  }
}

async function loadMessages(sessionId: number) {
  messagesLoading.value = true;
  errorNote.value = "";
  try {
    messages.value = await listMessages(sessionId);
    await scrollThread();
  } catch (err) {
    messages.value = [];
    errorNote.value = friendlyError(err);
  } finally {
    messagesLoading.value = false;
  }
}

async function loadRecommended(domainId: string) {
  try {
    recommended.value = await listRecommended(domainId);
  } catch {
    recommended.value = [];
  }
}

async function selectSession(id: number) {
  if (activeSessionId.value === id) return;
  activeSessionId.value = id;
}

async function onCreateSession() {
  errorNote.value = "";
  try {
    const created = await createSession(createDomain.value, "新会话");
    await refreshSessions(created.id);
  } catch (err) {
    errorNote.value = friendlyError(err);
  }
}

async function onRename(session: ChatSession) {
  const next = window.prompt("重命名会话", session.title || "新会话");
  if (next == null) return;
  const title = next.trim();
  if (!title) return;
  try {
    await updateSession(session.id, { title });
    await refreshSessions(activeSessionId.value);
  } catch (err) {
    errorNote.value = friendlyError(err);
  }
}

async function onDelete(session: ChatSession) {
  if (!window.confirm(`确认删除会话「${session.title || "新会话"}」？`)) return;
  try {
    await deleteSession(session.id);
    if (activeSessionId.value === session.id) {
      activeSessionId.value = null;
      messages.value = [];
    }
    await refreshSessions();
  } catch (err) {
    errorNote.value = friendlyError(err);
  }
}

async function sendAsk() {
  const q = question.value.trim();
  const sid = activeSessionId.value;
  if (!q || !sid || asking.value) return;

  asking.value = true;
  errorNote.value = "";
  question.value = "";

  try {
    await askInSession(sid, q);
    await refreshSessions(sid);
    await loadMessages(sid);
  } catch (err) {
    errorNote.value = friendlyError(err);
    question.value = q;
  } finally {
    asking.value = false;
    await scrollThread();
  }
}

async function askRecommended(text: string) {
  question.value = text;
  await sendAsk();
}

watch(activeSessionId, (id) => {
  if (id == null) {
    messages.value = [];
    recommended.value = [];
    return;
  }
  const session = sessions.value.find((s) => s.id === id);
  void loadMessages(id);
  if (session) {
    void loadRecommended(session.domain);
  }
});

onMounted(async () => {
  await refreshSessions();
  if (!sessions.value.length) {
    try {
      const created = await createSession(createDomain.value, "新会话");
      await refreshSessions(created.id);
    } catch (err) {
      errorNote.value = friendlyError(err);
    }
  }
});
</script>

<style scoped>
.chatbi {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 260px 1fr;
  height: calc(100vh - 58px);
  min-height: 560px;
  background: linear-gradient(180deg, rgba(244, 250, 249, 0.96), rgba(233, 241, 240, 0.98));
}

.session-pane {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.9rem 0.75rem;
  border-right: 1px solid rgba(15, 118, 110, 0.14);
  background: rgba(7, 21, 29, 0.94);
  color: #dceee9;
}

.session-toolbar {
  display: grid;
  gap: 0.45rem;
}

.new-btn {
  border: 0;
  border-radius: 10px;
  padding: 0.65rem 0.8rem;
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  color: #f4fffc;
  font-weight: 600;
}

.domain-select {
  width: 100%;
  border-radius: 10px;
  border: 1px solid rgba(232, 245, 242, 0.16);
  background: rgba(255, 255, 255, 0.05);
  color: #e8f5f2;
  padding: 0.45rem 0.55rem;
}

.pane-hint {
  padding: 0.6rem 0.4rem;
  color: rgba(220, 238, 233, 0.55);
  font-size: 0.82rem;
}

.session-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow: auto;
  display: grid;
  gap: 0.35rem;
}

.session-item {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.35rem;
  align-items: start;
  padding: 0.65rem 0.55rem;
  border-radius: 12px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 140ms ease, border-color 140ms ease;
}

.session-item:hover {
  background: rgba(20, 184, 166, 0.1);
}

.session-item.active {
  background: rgba(20, 184, 166, 0.18);
  border-color: rgba(20, 184, 166, 0.35);
}

.session-main {
  display: grid;
  gap: 0.35rem;
  min-width: 0;
}

.session-main strong {
  font-size: 0.86rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.domain-badge {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  font-size: 0.7rem;
  background: rgba(20, 184, 166, 0.18);
  color: #9fe8dc;
  border: 1px solid rgba(20, 184, 166, 0.28);
}

.thread-head .domain-badge {
  color: var(--teal);
  background: rgba(20, 184, 166, 0.12);
  border-color: rgba(15, 118, 110, 0.2);
}

.session-actions {
  display: flex;
  gap: 0.2rem;
}

.icon-btn {
  border: 0;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(232, 245, 242, 0.75);
  border-radius: 8px;
  padding: 0.2rem 0.4rem;
  font-size: 0.72rem;
}

.icon-btn.danger:hover {
  background: rgba(180, 83, 9, 0.25);
}

.thread-pane {
  display: grid;
  grid-template-rows: auto 1fr auto;
  min-width: 0;
  min-height: 0;
}

.thread-head {
  padding: 1rem 1.25rem 0.75rem;
  border-bottom: 1px solid rgba(15, 118, 110, 0.1);
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(8px);
}

.thread-head h1 {
  margin: 0;
  font-size: 1.15rem;
  color: var(--ink);
}

.thread-head p {
  margin: 0.3rem 0 0;
  color: var(--muted);
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.thread {
  overflow: auto;
  padding: 1.1rem 1.25rem 1.4rem;
  display: flex;
  flex-direction: column;
  gap: 0.95rem;
}

.empty-state {
  margin: auto;
  text-align: center;
  padding: 2rem 1rem;
  color: var(--muted);
  animation: rise 420ms ease-out;
}

.empty-state.soft {
  color: var(--muted);
}

.empty-logo {
  width: 64px;
  height: 64px;
  margin-bottom: 0.75rem;
  filter: drop-shadow(0 8px 18px rgba(15, 118, 110, 0.25));
}

.empty-state h2 {
  margin: 0;
  color: var(--ink);
  font-size: 1.35rem;
  letter-spacing: 0.04em;
}

.empty-state p {
  margin: 0.45rem 0 0;
  font-size: 0.92rem;
}

.msg-row {
  display: flex;
  width: 100%;
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-row.assistant {
  justify-content: flex-start;
}

.user-bubble {
  max-width: min(680px, 86%);
  padding: 0.75rem 0.95rem;
  border-radius: 16px 16px 4px 16px;
  background: linear-gradient(135deg, #0b1f2a, #0f766e);
  color: #f4fffc;
  line-height: 1.55;
  white-space: pre-wrap;
  box-shadow: 0 10px 24px rgba(11, 31, 42, 0.16);
  animation: rise 280ms ease-out;
}

.assistant-plain {
  border-radius: 16px 16px 16px 4px;
  background: rgba(255, 255, 255, 0.92);
  color: var(--ink);
  border: 1px solid var(--line);
}

.thinking {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.7rem 0.9rem;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.88rem;
}

.pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--teal-bright);
  animation: pulse 1s ease-in-out infinite;
}

.composer {
  border-top: 1px solid rgba(15, 118, 110, 0.12);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(10px);
  padding: 0.85rem 1.15rem 1rem;
  display: grid;
  gap: 0.65rem;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.chip {
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.9);
  color: var(--ink-soft);
  border-radius: 999px;
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
  transition: background 140ms ease, border-color 140ms ease;
}

.chip:hover:not(:disabled) {
  border-color: var(--teal);
  background: var(--teal-mist);
}

.composer-form {
  display: grid;
  gap: 0.55rem;
}

textarea {
  width: 100%;
  resize: none;
  min-height: 72px;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.75rem 0.85rem;
  outline: none;
  background: #fff;
}

textarea:focus {
  border-color: var(--teal);
  box-shadow: 0 0 0 3px var(--teal-mist);
}

.composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.error-note {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}

.composer-actions button {
  margin-left: auto;
  border: 0;
  border-radius: 10px;
  padding: 0.62rem 1.2rem;
  background: linear-gradient(135deg, var(--ink), var(--teal));
  color: #f4fffc;
  font-weight: 600;
}

.composer-actions button:disabled {
  opacity: 0.6;
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

@keyframes pulse {
  0%,
  100% {
    opacity: 0.35;
    transform: scale(0.9);
  }
  50% {
    opacity: 1;
    transform: scale(1.15);
  }
}

@media (max-width: 960px) {
  .chatbi {
    grid-template-columns: 1fr;
    height: auto;
    min-height: calc(100vh - 58px);
  }

  .session-pane {
    max-height: 220px;
  }

  .thread-pane {
    min-height: 70vh;
  }
}
</style>
