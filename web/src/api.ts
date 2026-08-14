import axios, { AxiosError } from "axios";

const TOKEN_KEY = "ti_token";

export type DomainInfo = {
  id: string;
  name: string;
  version: string;
};

export type RecommendedItem = {
  id: string;
  text: string;
};

export type ChartPayload = {
  type?: string;
  x?: Array<string | number>;
  series?: Array<{ name?: string; data: Array<string | number> }>;
  xField?: string;
  yField?: string;
};

export type AskResponse = {
  status: string;
  message: string;
  sql?: string | null;
  rows: Array<Record<string, unknown>>;
  truncated: boolean;
  chart: ChartPayload;
  narrative: string;
};

function resolveBaseURL(): string {
  const envBase = import.meta.env.VITE_API_BASE;
  if (envBase) return envBase.replace(/\/$/, "");
  // Dev: Vite proxies /api -> backend. Prod nginx can also rewrite /api.
  if (import.meta.env.DEV) return "/api";
  return "/api";
}

const client = axios.create({
  baseURL: resolveBaseURL(),
  timeout: 60_000,
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function friendlyError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const ax = err as AxiosError<{ detail?: string; message?: string }>;
    if (ax.response?.status === 401) {
      return "登录已失效，请重新登录。";
    }
    const detail = ax.response?.data?.detail || ax.response?.data?.message;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (ax.code === "ECONNABORTED") {
      return "请求超时，请稍后重试。";
    }
    if (!ax.response) {
      return "无法连接服务，请确认后端已启动。";
    }
    return "请求失败，请稍后重试。";
  }
  return "出现未知错误，请稍后重试。";
}

export async function login(username: string, password: string): Promise<string> {
  const { data } = await client.post<{ access_token: string }>("/auth/login", {
    username,
    password,
  });
  setToken(data.access_token);
  return data.access_token;
}

export async function listDomains(): Promise<DomainInfo[]> {
  const { data } = await client.get<DomainInfo[]>("/domains");
  return data;
}

export async function listRecommended(domainId: string): Promise<RecommendedItem[]> {
  const { data } = await client.get<RecommendedItem[]>(`/domains/${domainId}/recommended`);
  return data;
}

export async function ask(domain: string, question: string): Promise<AskResponse> {
  const { data } = await client.post<AskResponse>("/ask", { domain, question });
  return data;
}
