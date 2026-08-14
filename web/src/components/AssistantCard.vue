<template>
  <article class="assistant-card" :class="statusClass">
    <header class="card-head">
      <div class="avatar" aria-hidden="true">智</div>
      <div class="meta">
        <strong>元景助手</strong>
        <span>{{ statusLabel }}</span>
      </div>
    </header>

    <ol v-if="steps.length" class="steps" aria-label="分析步骤">
      <li
        v-for="(step, idx) in steps"
        :key="step.id"
        class="step"
        :class="step.state"
        :style="{ animationDelay: `${idx * 70}ms` }"
      >
        <span class="step-mark" aria-hidden="true" />
        <span class="step-label">{{ step.label }}</span>
      </li>
    </ol>

    <div v-if="isClarify || isError" class="banner" :class="isError ? 'error' : 'clarify'" role="alert">
      {{ result.message || (isClarify ? "请补充更多业务条件后继续提问。" : "分析未能完成。") }}
    </div>

    <div v-if="result.narrative" class="narrative">
      <h3>洞察</h3>
      <p>{{ result.narrative }}</p>
    </div>

    <details v-if="result.sql" class="sql-block" :open="sqlOpenDefault">
      <summary>查看 SQL</summary>
      <pre><code>{{ result.sql }}</code></pre>
    </details>

    <div v-if="columns.length" class="table-wrap">
      <div class="section-title">
        <h3>结果表</h3>
        <span v-if="result.truncated">已截断</span>
      </div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th v-for="col in columns" :key="col">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in result.rows" :key="idx">
              <td v-for="col in columns" :key="col">{{ formatCell(row[col]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="hasChart" class="chart-wrap">
      <h3>图表</h3>
      <div ref="chartEl" class="chart" />
    </div>

    <p
      v-if="!result.narrative && !result.sql && !columns.length && !hasChart && result.message && !isClarify && !isError"
      class="plain"
    >
      {{ result.message }}
    </p>
  </article>
</template>

<script setup lang="ts">
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import type { AskResponse, ChartPayload, StepInfo } from "../api";

const props = defineProps<{
  result: AskResponse;
}>();

const chartEl = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

const steps = computed<StepInfo[]>(() => props.result.steps ?? []);
const isClarify = computed(() => props.result.status === "clarify");
const isError = computed(() => props.result.status === "error");
const statusClass = computed(() => {
  if (isError.value) return "is-error";
  if (isClarify.value) return "is-clarify";
  return "is-ok";
});
const statusLabel = computed(() => {
  if (isError.value) return "需要关注";
  if (isClarify.value) return "待澄清";
  return "分析完成";
});
const sqlOpenDefault = computed(() => isError.value || !props.result.narrative);

const columns = computed(() => {
  const rows = props.result.rows ?? [];
  if (!rows.length) return [] as string[];
  return Object.keys(rows[0]);
});

const hasChart = computed(() => {
  const chartData = props.result.chart;
  if (!chartData) return false;
  const series = chartData.series ?? [];
  const x = chartData.x ?? [];
  return x.length > 0 && series.some((s) => (s.data?.length ?? 0) > 0);
});

function formatCell(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function toOption(payload: ChartPayload): echarts.EChartsOption {
  const chartType: "bar" | "line" = payload.type === "bar" ? "bar" : "line";
  const series: echarts.SeriesOption[] = (payload.series ?? []).map((s) => {
    if (chartType === "bar") {
      return {
        name: s.name || "系列",
        type: "bar",
        data: s.data,
        itemStyle: { color: "#0f766e" },
      };
    }
    return {
      name: s.name || "系列",
      type: "line",
      data: s.data,
      smooth: true,
      itemStyle: { color: "#0f766e" },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: "rgba(20, 184, 166, 0.35)" },
          { offset: 1, color: "rgba(20, 184, 166, 0.02)" },
        ]),
      },
    };
  });

  return {
    color: ["#0f766e", "#0ea5e9", "#f59e0b"],
    grid: { left: 40, right: 20, top: 36, bottom: 36 },
    tooltip: { trigger: "axis" },
    legend: { top: 0 },
    xAxis: {
      type: "category",
      data: payload.x ?? [],
      axisLine: { lineStyle: { color: "#9db0ba" } },
      axisLabel: { color: "#5b7380" },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "rgba(15, 118, 110, 0.12)" } },
      axisLabel: { color: "#5b7380" },
    },
    series,
  };
}

async function renderChart() {
  await nextTick();
  if (!hasChart.value || !chartEl.value || !props.result.chart) {
    if (chart) {
      chart.dispose();
      chart = null;
    }
    return;
  }
  if (!chart) {
    chart = echarts.init(chartEl.value);
  }
  chart.setOption(toOption(props.result.chart), true);
  chart.resize();
}

watch(
  () => props.result,
  () => {
    void renderChart();
  },
  { deep: true, immediate: true },
);

onBeforeUnmount(() => {
  chart?.dispose();
  chart = null;
});
</script>

<style scoped>
.assistant-card {
  display: grid;
  gap: 0.85rem;
  padding: 1rem 1.05rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--line);
  background: var(--surface);
  box-shadow: var(--shadow-sm);
  max-width: min(760px, 100%);
}

.assistant-card.is-clarify {
  border-color: #fde68a;
}

.assistant-card.is-error {
  border-color: #fecaca;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: var(--radius);
  display: grid;
  place-items: center;
  background: var(--accent-soft);
  color: var(--accent-ink);
  font-size: 0.75rem;
  font-weight: 700;
  border: 1px solid #ccfbf1;
}

.meta {
  display: grid;
  gap: 0.05rem;
}

.meta strong {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--ink);
}

.meta span {
  font-size: 0.72rem;
  color: var(--muted);
}

.steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--surface-muted);
}

.step {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.65rem;
  border-right: 1px solid var(--line);
  background: transparent;
  opacity: 0;
  animation: step-in 280ms ease-out forwards;
  font-size: 0.75rem;
  color: var(--muted);
  font-weight: 500;
}

.step:last-child {
  border-right: 0;
}

.step.done {
  color: var(--accent-ink);
  background: var(--surface);
}

.step.pending {
  opacity: 0.5;
}

.step-mark {
  width: 6px;
  height: 6px;
  border-radius: 1px;
  background: var(--line-strong);
}

.step.done .step-mark {
  background: var(--accent);
}

.banner {
  margin: 0;
  padding: 0.65rem 0.75rem;
  border-radius: var(--radius);
  font-size: 0.86rem;
  line-height: 1.5;
  border: 1px solid transparent;
}

.banner.clarify {
  background: var(--warn-soft);
  color: #92400e;
  border-color: #fde68a;
}

.banner.error {
  background: var(--danger-soft);
  color: #b91c1c;
  border-color: #fecaca;
}

.narrative h3,
.chart-wrap h3,
.section-title h3 {
  margin: 0 0 0.4rem;
  font-size: 0.75rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 600;
}

.narrative p,
.plain {
  margin: 0;
  line-height: 1.6;
  color: var(--ink);
  white-space: pre-wrap;
  font-size: 0.9rem;
}

.sql-block {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
  overflow: hidden;
}

.sql-block summary {
  cursor: pointer;
  padding: 0.5rem 0.75rem;
  font-size: 0.78rem;
  font-weight: 500;
  color: var(--muted);
  user-select: none;
  border-bottom: 1px solid transparent;
}

.sql-block[open] summary {
  border-bottom-color: var(--line);
  background: var(--surface-muted);
}

.sql-block pre {
  margin: 0;
  padding: 0.75rem;
  overflow: auto;
  font-family: var(--mono);
  font-size: 0.78rem;
  line-height: 1.55;
  background: var(--surface-muted);
  color: var(--text);
  border-top: 1px solid var(--line);
}

.section-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
}

.section-title span {
  font-size: 0.72rem;
  color: var(--muted);
}

.table-scroll {
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.84rem;
}

th,
td {
  padding: 0.5rem 0.7rem;
  border-bottom: 1px solid var(--line);
  text-align: left;
  white-space: nowrap;
}

th {
  background: var(--surface-muted);
  color: var(--muted);
  font-weight: 600;
  font-size: 0.75rem;
}

tr:last-child td {
  border-bottom: 0;
}

.chart {
  width: 100%;
  height: 240px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
}

@keyframes step-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
</style>
