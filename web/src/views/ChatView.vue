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
  grid-template-columns: 240px 1fr;
  height: calc(100vh - 56px);
  min-height: 520px;
  background: var(--bg);
}

.session-pane {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem 0.75rem;
  border-right: 1px solid var(--line);
  background: var(--surface);
}

.session-toolbar {
  display: grid;
  gap: 0.5rem;
}

.new-btn {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 0.55rem 0.75rem;
  background: var(--surface);
  color: var(--ink);
  font-weight: 600;
  font-size: 0.85rem;
}

.new-btn:hover {
  background: var(--accent-soft);
  border-color: #ccfbf1;
  color: var(--accent-ink);
}

.domain-select {
  width: 100%;
  border-radius: var(--radius);
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--text);
  padding: 0.45rem 0.55rem;
  font-size: 0.85rem;
}

.pane-hint {
  padding: 0.5rem 0.35rem;
  color: var(--muted);
  font-size: 0.8rem;
}

.session-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow: auto;
  display: grid;
  gap: 0.25rem;
}

.session-item {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.35rem;
  align-items: start;
  padding: 0.6rem 0.55rem;
  border-radius: var(--radius);
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 120ms ease, border-color 120ms ease;
}

.session-item:hover {
  background: var(--surface-muted);
}

.session-item.active {
  background: var(--accent-soft);
  border-color: #ccfbf1;
}

.session-main {
  display: grid;
  gap: 0.3rem;
  min-width: 0;
}

.session-main strong {
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.domain-badge {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 0.08rem 0.4rem;
  border-radius: var(--radius);
  font-size: 0.68rem;
  font-weight: 500;
  background: var(--surface-muted);
  color: var(--muted);
  border: 1px solid var(--line);
}

.thread-head .domain-badge {
  color: var(--accent-ink);
  background: var(--accent-soft);
  border-color: #ccfbf1;
}

.session-actions {
  display: flex;
  gap: 0.2rem;
}

.icon-btn {
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--muted);
  border-radius: var(--radius);
  padding: 0.15rem 0.35rem;
  font-size: 0.7rem;
  font-weight: 500;
}

.icon-btn:hover {
  background: var(--surface-muted);
  color: var(--text);
}

.icon-btn.danger:hover {
  background: var(--danger-soft);
  color: var(--danger);
  border-color: #fecaca;
}

.thread-pane {
  display: grid;
  grid-template-rows: auto 1fr auto;
  min-width: 0;
  min-height: 0;
}

.thread-head {
  padding: 1.15rem 1.5rem 0.9rem;
  border-bottom: 1px solid var(--line);
  background: var(--surface);
}

.thread-head h1 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--ink);
}

.thread-head p {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.82rem;
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.thread {
  overflow: auto;
  padding: 1.5rem 1.5rem 1.75rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.empty-state {
  margin: auto;
  text-align: center;
  padding: 3rem 1.5rem;
  color: var(--muted);
  max-width: 360px;
}

.empty-state.soft {
  color: var(--muted);
}

.empty-logo {
  width: 40px;
  height: 40px;
  margin-bottom: 1rem;
  padding: 10px;
  box-sizing: content-box;
  background: var(--accent-soft);
  border: 1px solid #ccfbf1;
  border-radius: var(--radius);
}

.empty-state h2 {
  margin: 0;
  color: var(--ink);
  font-size: 1.15rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.empty-state p {
  margin: 0.5rem 0 0;
  font-size: 0.88rem;
  line-height: 1.55;
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
  max-width: min(640px, 86%);
  padding: 0.7rem 0.9rem;
  border-radius: var(--radius-lg);
  background: var(--accent-soft);
  color: var(--accent-ink);
  border: 1px solid #ccfbf1;
  line-height: 1.55;
  white-space: pre-wrap;
  font-size: 0.9rem;
}

.assistant-plain {
  border-radius: var(--radius-lg);
  background: var(--surface);
  color: var(--ink);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-sm);
  padding: 0.7rem 0.9rem;
}

.thinking {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.65rem 0.85rem;
  border-radius: var(--radius);
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.85rem;
  box-shadow: var(--shadow-sm);
}

.pulse {
  width: 6px;
  height: 6px;
  border-radius: 1px;
  background: var(--accent);
  animation: pulse 1.1s ease-in-out infinite;
}

.composer {
  border-top: 1px solid var(--line);
  background: var(--surface);
  padding: 1rem 1.5rem 1.15rem;
  display: grid;
  gap: 0.65rem;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.chip {
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--text);
  border-radius: var(--radius);
  padding: 0.3rem 0.65rem;
  font-size: 0.78rem;
  font-weight: 500;
  transition: background 120ms ease, border-color 120ms ease;
}

.chip:hover:not(:disabled) {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent-ink);
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
  border-radius: var(--radius);
  padding: 0.7rem 0.85rem;
  outline: none;
  background: var(--surface);
  color: var(--text);
}

textarea:focus {
  border-color: var(--accent);
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
  font-size: 0.82rem;
}

.composer-actions button {
  margin-left: auto;
  border: 1px solid var(--accent);
  border-radius: var(--radius);
  padding: 0.55rem 1.1rem;
  background: var(--accent-soft);
  color: var(--accent-ink);
  font-weight: 600;
  font-size: 0.85rem;
}

.composer-actions button:hover:not(:disabled) {
  background: #d5f5ef;
  border-color: var(--accent-ink);
}

.composer-actions button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 1;
  }
}

@media (max-width: 960px) {
  .chatbi {
    grid-template-columns: 1fr;
    height: auto;
    min-height: calc(100vh - 56px);
  }

  .session-pane {
    max-height: 220px;
  }

  .thread-pane {
    min-height: 70vh;
  }
}
</style>
