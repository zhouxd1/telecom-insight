import axios, { AxiosError } from "axios";
import type { Branding } from "./branding";

const TOKEN_KEY = "ti_token";
const WORKSPACE_KEY = "ti_workspace_id";

export type { Branding };

export type BrandingUpdatePayload = Partial<{
  product_name: string;
  tagline: string;
  logo_url: string | null;
  favicon_url: string | null;
  preset_id: string;
  color_mode: string;
  primary: string | null;
  primary_soft: string | null;
  bg: string | null;
  surface: string | null;
  text: string | null;
  muted: string | null;
}>;

export type DomainInfo = {
  id: string;
  name: string;
  version: string;
};

export type WorkspaceSummary = {
  id: number;
  name: string;
  role: string;
  domains: string[];
};

export type MeResponse = {
  id: number;
  username: string;
  display_name: string;
  org_id: number;
  org_name: string;
  org_role: string;
  workspaces: WorkspaceSummary[];
};

export type Workspace = {
  id: number;
  org_id: number;
  name: string;
  status: string;
  created_at: string;
};

export type WorkspaceMember = {
  id: number;
  workspace_id: number;
  user_id: number;
  role: string;
  domains: string[];
};

export type OrgUser = {
  id: number;
  org_id: number;
  username: string;
  display_name: string;
  org_role: string;
  enabled: boolean;
};

export type Datasource = {
  id: number;
  workspace_id: number;
  name: string;
  db_type: string;
  host: string;
  port?: number | null;
  database: string;
  username: string;
  extra_json?: Record<string, unknown> | null;
  is_default: boolean;
  last_ok_at?: string | null;
  last_error?: string | null;
};

export type DatasourceTestResult = {
  ok: boolean;
  error?: string | null;
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
  const workspaceId = getWorkspaceId();
  if (workspaceId != null) {
    config.headers["X-Workspace-Id"] = String(workspaceId);
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

export function getWorkspaceId(): number | null {
  const raw = localStorage.getItem(WORKSPACE_KEY);
  if (!raw) return null;
  const id = Number(raw);
  return Number.isFinite(id) ? id : null;
}

export function setWorkspaceId(id: number | null): void {
  if (id == null) {
    localStorage.removeItem(WORKSPACE_KEY);
    return;
  }
  localStorage.setItem(WORKSPACE_KEY, String(id));
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
  const me = await fetchMe();
  if (me.workspaces.length > 0) {
    setWorkspaceId(me.workspaces[0].id);
  }
  return data.access_token;
}

export async function fetchMe(): Promise<MeResponse> {
  const { data } = await client.get<MeResponse>("/auth/me");
  return data;
}

export async function listWorkspaces(): Promise<Workspace[]> {
  const { data } = await client.get<Workspace[]>("/workspaces");
  return data;
}

export async function createWorkspace(body: { name: string }): Promise<Workspace> {
  const { data } = await client.post<Workspace>("/workspaces", body);
  return data;
}

export async function archiveWorkspace(workspaceId: number): Promise<Workspace> {
  const { data } = await client.patch<Workspace>(`/workspaces/${workspaceId}`, {
    status: "archived",
  });
  return data;
}

export async function listMembers(workspaceId: number): Promise<WorkspaceMember[]> {
  const { data } = await client.get<WorkspaceMember[]>(`/workspaces/${workspaceId}/members`);
  return data;
}

export async function addMember(
  workspaceId: number,
  body: { user_id: number; role: string; domains?: string[] },
): Promise<WorkspaceMember> {
  const { data } = await client.post<WorkspaceMember>(
    `/workspaces/${workspaceId}/members`,
    body,
  );
  return data;
}

export async function updateMember(
  workspaceId: number,
  userId: number,
  body: Partial<{ role: string; domains: string[] }>,
): Promise<WorkspaceMember> {
  const { data } = await client.patch<WorkspaceMember>(
    `/workspaces/${workspaceId}/members/${userId}`,
    body,
  );
  return data;
}

export async function removeMember(workspaceId: number, userId: number): Promise<void> {
  await client.delete(`/workspaces/${workspaceId}/members/${userId}`);
}

export async function listUsers(): Promise<OrgUser[]> {
  const { data } = await client.get<OrgUser[]>("/admin/users");
  return data;
}

export async function createUser(body: {
  username: string;
  password: string;
  display_name?: string;
  org_role?: string;
  enabled?: boolean;
}): Promise<OrgUser> {
  const { data } = await client.post<OrgUser>("/admin/users", body);
  return data;
}

export async function updateUser(
  userId: number,
  body: Partial<{
    display_name: string;
    org_role: string;
    enabled: boolean;
    password: string;
  }>,
): Promise<OrgUser> {
  const { data } = await client.patch<OrgUser>(`/admin/users/${userId}`, body);
  return data;
}

export async function listDatasources(): Promise<Datasource[]> {
  const { data } = await client.get<Datasource[]>("/admin/datasources");
  return data;
}

export async function createDatasource(body: {
  name: string;
  db_type: string;
  host?: string;
  port?: number | null;
  database?: string;
  username?: string;
  password?: string;
  extra_json?: Record<string, unknown> | null;
  is_default?: boolean;
}): Promise<Datasource> {
  const { data } = await client.post<Datasource>("/admin/datasources", body);
  return data;
}

export async function updateDatasource(
  id: number,
  body: Partial<{
    name: string;
    db_type: string;
    host: string;
    port: number | null;
    database: string;
    username: string;
    password: string;
    extra_json: Record<string, unknown> | null;
    is_default: boolean;
  }>,
): Promise<Datasource> {
  const { data } = await client.patch<Datasource>(`/admin/datasources/${id}`, body);
  return data;
}

export async function testDatasource(id: number): Promise<DatasourceTestResult> {
  const { data } = await client.post<DatasourceTestResult>(`/admin/datasources/${id}/test`);
  return data;
}

export async function setDefaultDatasource(id: number): Promise<Datasource> {
  const { data } = await client.post<Datasource>(`/admin/datasources/${id}/default`);
  return data;
}

export async function deleteDatasource(id: number): Promise<void> {
  await client.delete(`/admin/datasources/${id}`);
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

function asBranding(data: Branding): Branding {
  return {
    product_name: data.product_name,
    tagline: data.tagline,
    logo_src: data.logo_src,
    favicon_src: data.favicon_src,
    preset_id: data.preset_id,
    color_mode: data.color_mode,
    colors: data.colors ?? {},
    primary: data.primary,
    primary_soft: data.primary_soft,
    bg: data.bg,
    surface: data.surface,
    text: data.text,
    muted: data.muted,
  };
}

export async function fetchDefaultBranding(): Promise<Branding> {
  const { data } = await client.get<Branding>("/branding/default");
  return asBranding(data);
}

export async function fetchOrgBranding(): Promise<Branding> {
  const { data } = await client.get<Branding>("/orgs/me/branding");
  return asBranding(data);
}

export async function updateOrgBranding(body: BrandingUpdatePayload): Promise<Branding> {
  const { data } = await client.put<Branding>("/orgs/me/branding", body);
  return asBranding(data);
}

export async function uploadBrandingLogo(file: File): Promise<Branding> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<Branding>("/orgs/me/branding/logo", form);
  return asBranding(data);
}

export async function uploadBrandingFavicon(file: File): Promise<Branding> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<Branding>("/orgs/me/branding/favicon", form);
  return asBranding(data);
}

export async function deleteBrandingLogo(): Promise<Branding> {
  const { data } = await client.delete<Branding>("/orgs/me/branding/logo");
  return asBranding(data);
}

export async function deleteBrandingFavicon(): Promise<Branding> {
  const { data } = await client.delete<Branding>("/orgs/me/branding/favicon");
  return asBranding(data);
}
