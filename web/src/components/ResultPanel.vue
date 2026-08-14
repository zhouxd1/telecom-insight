<template>
  <section class="result-panel">
    <div v-if="loading" class="state">正在分析问题…</div>
    <div v-else-if="error" class="state error" role="alert">{{ error }}</div>
    <template v-else-if="result">
      <div v-if="result.narrative" class="narrative">
        <h2>洞察</h2>
        <p>{{ result.narrative }}</p>
      </div>

      <div v-if="hasChart" class="chart-wrap">
        <h2>图表</h2>
        <div ref="chartEl" class="chart" />
      </div>

      <div v-if="columns.length" class="table-wrap">
        <h2>明细</h2>
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
        <p v-if="result.truncated" class="note">结果已截断，仅展示部分行。</p>
      </div>

      <div
        v-if="!result.narrative && !hasChart && !columns.length && result.message"
        class="state"
      >
        {{ result.message }}
      </div>
    </template>
    <div v-else class="state muted">选择推荐问题或输入问题开始分析。</div>
  </section>
</template>

<script setup lang="ts">
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import type { AskResponse, ChartPayload } from "../api";

const props = defineProps<{
  loading: boolean;
  error: string;
  result: AskResponse | null;
}>();

const chartEl = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

const columns = computed(() => {
  const rows = props.result?.rows ?? [];
  if (!rows.length) return [] as string[];
  return Object.keys(rows[0]);
});

const hasChart = computed(() => {
  const chartData = props.result?.chart;
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
  if (!hasChart.value || !chartEl.value || !props.result?.chart) {
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
  () => [props.result, props.loading, props.error] as const,
  () => {
    void renderChart();
  },
  { deep: true },
);

onBeforeUnmount(() => {
  chart?.dispose();
  chart = null;
});
</script>

<style scoped>
.result-panel {
  display: grid;
  gap: 1rem;
  padding: 1.1rem 1.15rem;
  border-radius: var(--radius);
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: var(--shadow);
  min-height: 180px;
}

h2 {
  margin: 0 0 0.55rem;
  font-size: 0.95rem;
  letter-spacing: 0.04em;
  color: var(--teal);
  text-transform: none;
}

.narrative p {
  margin: 0;
  line-height: 1.65;
  color: var(--ink);
  white-space: pre-wrap;
}

.chart {
  width: 100%;
  height: 280px;
}

.table-scroll {
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 10px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

th,
td {
  padding: 0.65rem 0.75rem;
  border-bottom: 1px solid var(--line);
  text-align: left;
  white-space: nowrap;
}

th {
  background: rgba(15, 118, 110, 0.08);
  color: var(--ink-soft);
  font-weight: 600;
}

tr:last-child td {
  border-bottom: 0;
}

.note {
  margin: 0.55rem 0 0;
  color: var(--muted);
  font-size: 0.82rem;
}

.state {
  color: var(--ink-soft);
  line-height: 1.5;
}

.state.error {
  color: var(--danger);
}

.state.muted {
  color: var(--muted);
}
</style>
