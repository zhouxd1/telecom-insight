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

export type StepInfo = {
  id: string;
  label: string;
  state: string;
};

export type AskResponse = {
  status: string;
  message: string;
  sql?: string | null;
  rows: Array<Record<string, unknown>>;
  truncated: boolean;
  chart: ChartPayload;
  narrative: string;
  steps?: StepInfo[];
};

export type ChatSession = {
  id: number;
  title: string;
  domain: string;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  id: number;
  session_id: number;
  role: string;
  content_json: string;
  created_at: string;
};

export type AiModel = {
  id: number;
  name: string;
  base_url: string;
  api_key: string;
  model: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type Term = {
  id: number;
  domain: string;
  term: string;
  standard: string;
  maps_to?: string | null;
  created_at: string;
  updated_at: string;
};

export type SqlExample = {
  id: number;
  domain: string;
  question: string;
  sql: string;
  created_at: string;
  updated_at: string;
};

function resolveBaseURL(): string {
  const envBase = import.meta.env.VITE_API_BASE;
  if (envBase) return envBase.replace(/\/$/, "");
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

export async function listSessions(): Promise<ChatSession[]> {
  const { data } = await client.get<ChatSession[]>("/sessions");
  return data;
}

export async function createSession(domain: string, title = ""): Promise<ChatSession> {
  const { data } = await client.post<ChatSession>("/sessions", { domain, title });
  return data;
}

export async function updateSession(
  sessionId: number,
  patch: { title?: string; domain?: string },
): Promise<ChatSession> {
  const { data } = await client.patch<ChatSession>(`/sessions/${sessionId}`, patch);
  return data;
}

export async function deleteSession(sessionId: number): Promise<void> {
  await client.delete(`/sessions/${sessionId}`);
}

export async function listMessages(sessionId: number): Promise<ChatMessage[]> {
  const { data } = await client.get<ChatMessage[]>(`/sessions/${sessionId}/messages`);
  return data;
}

export async function askInSession(sessionId: number, question: string): Promise<AskResponse> {
  const { data } = await client.post<AskResponse>(`/sessions/${sessionId}/ask`, { question });
  return data;
}

export async function listModels(): Promise<AiModel[]> {
  const { data } = await client.get<AiModel[]>("/admin/models");
  return data;
}

export async function createModel(body: {
  name: string;
  base_url?: string;
  api_key?: string;
  model?: string;
  enabled?: boolean;
}): Promise<AiModel> {
  const { data } = await client.post<AiModel>("/admin/models", body);
  return data;
}

export async function updateModel(
  id: number,
  body: Partial<{
    name: string;
    base_url: string;
    api_key: string;
    model: string;
    enabled: boolean;
  }>,
): Promise<AiModel> {
  const { data } = await client.patch<AiModel>(`/admin/models/${id}`, body);
  return data;
}

export async function deleteModel(id: number): Promise<void> {
  await client.delete(`/admin/models/${id}`);
}

export async function testModel(id: number): Promise<{ ok: boolean; detail: string }> {
  const { data } = await client.post<{ ok: boolean; detail: string }>(`/admin/models/${id}/test`);
  return data;
}

export async function listTerms(domain?: string): Promise<Term[]> {
  const { data } = await client.get<Term[]>("/admin/terms", {
    params: domain ? { domain } : undefined,
  });
  return data;
}

export async function createTerm(body: {
  domain: string;
  term: string;
  standard: string;
  maps_to?: string | null;
}): Promise<Term> {
  const { data } = await client.post<Term>("/admin/terms", body);
  return data;
}

export async function updateTerm(
  id: number,
  body: Partial<{ domain: string; term: string; standard: string; maps_to: string | null }>,
): Promise<Term> {
  const { data } = await client.patch<Term>(`/admin/terms/${id}`, body);
  return data;
}

export async function deleteTerm(id: number): Promise<void> {
  await client.delete(`/admin/terms/${id}`);
}

export async function listExamples(domain?: string): Promise<SqlExample[]> {
  const { data } = await client.get<SqlExample[]>("/admin/examples", {
    params: domain ? { domain } : undefined,
  });
  return data;
}

export async function createExample(body: {
  domain: string;
  question: string;
  sql: string;
}): Promise<SqlExample> {
  const { data } = await client.post<SqlExample>("/admin/examples", body);
  return data;
}

export async function updateExample(
  id: number,
  body: Partial<{ domain: string; question: string; sql: string }>,
): Promise<SqlExample> {
  const { data } = await client.patch<SqlExample>(`/admin/examples/${id}`, body);
  return data;
}

export async function deleteExample(id: number): Promise<void> {
  await client.delete(`/admin/examples/${id}`);
}
