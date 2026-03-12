import { useAuthStore } from "@/lib/auth-store";

const CONFIGURED_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend";
const DIRECT_API_BASE = process.env.NEXT_PUBLIC_API_DIRECT_URL ?? "http://localhost:8001";
let preferredApiBase: string | null = null;

let isRefreshing = false;
let refreshQueue: Array<(token: string | null) => void> = [];

function flushQueue(token: string | null): void {
  refreshQueue.forEach((resolve) => resolve(token));
  refreshQueue = [];
}

type RequestOptions = RequestInit & {
  _retry?: boolean;
  token?: string;
};

function normalizeBase(url: string): string {
  return url.replace(/\/+$/, "");
}

function getCsrfTokenFromCookie(): string | null {
  if (typeof document === "undefined") return null;
  const entry = document.cookie
    .split("; ")
    .find((part) => part.startsWith("apex_csrf_token="));
  if (!entry) return null;
  return decodeURIComponent(entry.slice("apex_csrf_token=".length));
}

function apiBaseCandidates(): string[] {
  const set = new Set<string>();
  const add = (value: string | null | undefined) => {
    if (!value) return;
    set.add(normalizeBase(value));
  };

  add(preferredApiBase);
  add(CONFIGURED_API_BASE);
  if (typeof window !== "undefined") {
    add("/backend");
    const host = window.location.hostname.toLowerCase();
    if (host === "localhost" || host === "127.0.0.1") add(DIRECT_API_BASE);
  }
  return [...set];
}

async function fetchApi(path: string, init: RequestInit): Promise<Response> {
  let lastError: unknown = null;
  const candidates = apiBaseCandidates();
  for (let i = 0; i < candidates.length; i += 1) {
    const base = candidates[i];
    try {
      const response = await fetch(`${base}${path}`, init);
      const shouldFallback = (response.status >= 500 || response.status === 404) && i < candidates.length - 1;
      if (shouldFallback) {
        lastError = new Error(`Upstream ${response.status} from ${base}`);
        continue;
      }
      preferredApiBase = base;
      return response;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Failed to connect to API");
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data === "string") return data;
    if (data && typeof data.detail === "string") return data.detail;
    if (data && typeof data.message === "string") return data.message;
    if (data && data.detail && typeof data.detail.message === "string") return data.detail.message;
  } catch {
    // Ignore JSON parse errors; fallback to text below.
  }

  try {
    const text = await response.text();
    if (text) return text;
  } catch {
    // Ignore read errors and fallback to generic status message.
  }

  return `Request failed: ${response.status}`;
}

async function request<T>(path: string, init: RequestOptions = {}): Promise<T> {
  const state = useAuthStore.getState();
  const token = init.token ?? state.accessToken;
  const method = (init.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrf = getCsrfTokenFromCookie();
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }

  const response = await fetchApi(path, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });

  if (response.status !== 401) {
    if (!response.ok) {
      throw new Error(await readErrorMessage(response));
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }

  if (init._retry) {
    useAuthStore.getState().clear();
    if (typeof window !== "undefined") window.location.replace("/auth/login?session_expired=true");
    throw new Error("Session expired");
  }

  if (isRefreshing) {
    const queuedToken = await new Promise<string | null>((resolve) => refreshQueue.push(resolve));
    if (!queuedToken) throw new Error("Session expired");
    return request<T>(path, { ...init, _retry: true, token: queuedToken });
  }

  isRefreshing = true;
  const newToken = await useAuthStore.getState().refreshToken();
  isRefreshing = false;
  flushQueue(newToken);

  if (!newToken) {
    useAuthStore.getState().clear();
    if (typeof window !== "undefined") window.location.replace("/auth/login?session_expired=true");
    throw new Error("Session expired");
  }

  return request<T>(path, { ...init, _retry: true, token: newToken });
}

export const api = {
  register: (body: { email: string; password: string; full_name: string }) =>
    request<{ message: string }>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    request<{ access_token: string; token_type: string; expires_in: number; user: any }>("/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  verifyEmail: (token: string) =>
    request<{ access_token: string; token_type: string; expires_in: number; user: any }>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  forgotPassword: (email: string) =>
    request<{ message: string }>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }),
  resetPassword: (token: string, new_password: string) =>
    request<{ message: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password }),
    }),
  resendVerification: (email: string) =>
    request<{ message: string }>("/auth/resend-verification", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  refresh: () => request<{ access_token: string; token_type: string; expires_in: number; user: any }>("/auth/refresh", { method: "POST" }),
  logout: () => request<{ message: string }>("/auth/logout", { method: "POST" }),

  getProfile: (token: string) => request("/profile", { token }),
  upsertProfile: (token: string, body: unknown) =>
    request("/profile", { method: "PUT", body: JSON.stringify(body), token }),
  patchProfile: (token: string, body: unknown) =>
    request("/profile", { method: "PATCH", body: JSON.stringify(body), token }),

  searchJobs: (token: string, query: URLSearchParams) => request(`/jobs/search?${query.toString()}`, { token }),
  refreshJobs: (token: string) => request(`/jobs/refresh`, { method: "POST", token }),
  getJobMatches: (token: string, resumeId: string, nResults = 50, minScore = 0.6) =>
    request(`/jobs/matches?resume_id=${encodeURIComponent(resumeId)}&n_results=${nResults}&min_score=${minScore}`, {
      token,
    }),
  getJob: (token: string, id: string) => request(`/jobs/${id}`, { token }),
  recordJobFeedback: (token: string, id: string, body: { event_type: string; value?: string }) =>
    request(`/jobs/${id}/feedback`, { method: "POST", body: JSON.stringify(body), token }),
  saveJob: (token: string, id: string) => request(`/jobs/${id}/save`, { method: "POST", token }),
  unsaveJob: (token: string, id: string) => request(`/jobs/${id}/save`, { method: "DELETE", token }),
  listSavedJobs: (token: string) => request("/jobs/saved", { token }),

  listResumes: (token: string) => request("/resumes", { token }),
  uploadResume: async (token: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const csrf = getCsrfTokenFromCookie();
    const response = await fetchApi("/resumes/upload", {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers: {
        ...(csrf ? { "X-CSRF-Token": csrf } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: form,
    });
    if (!response.ok) throw new Error(await readErrorMessage(response));
    return response.json();
  },
  getResume: (token: string, id: string) => request(`/resumes/${id}`, { token }),
  updateResume: (token: string, id: string, body: { label?: string; is_primary?: boolean }) =>
    request(`/resumes/${id}`, { method: "PUT", body: JSON.stringify(body), token }),
  deleteResume: (token: string, id: string) => request(`/resumes/${id}`, { method: "DELETE", token }),
  permanentDeleteResume: (token: string, id: string) => request(`/resumes/${id}/permanent`, { method: "DELETE", token }),
  getResumeDownloadUrl: (token: string, id: string) => request<{ url: string }>(`/resumes/${id}/download`, { token }),
  createTailorTask: (token: string, body: { resume_id: string; job_id: string }) =>
    request("/resumes/tailor", { method: "POST", body: JSON.stringify(body), token }),
  createTailorTaskForResume: (token: string, resumeId: string, body: { job_id: string; job_description?: string }) =>
    request(`/resumes/${resumeId}/tailor`, { method: "POST", body: JSON.stringify(body), token }),
  getTailorTask: (token: string, taskId: string) => request(`/resumes/tailor/${taskId}/status`, { token }),
  listTailoredResumes: (token: string, id: string) => request(`/resumes/${id}/tailored`, { token }),
  getTailoredResume: (token: string, id: string) => request(`/resumes/tailored/${id}`, { token }),
  exportTailoredResume: (token: string, id: string, format: "pdf" | "docx" | "txt" = "pdf") =>
    request(`/resumes/tailored/${id}/export`, { method: "POST", body: JSON.stringify({ format }), token }),
  createCoverLetter: (token: string, id: string, body: { job_id?: string; tone: string; hiring_manager_name?: string }) =>
    request(`/resumes/${id}/cover-letter`, { method: "POST", body: JSON.stringify(body), token }),
  getCoverLetter: (token: string, id: string) => request(`/resumes/cover-letters/${id}`, { token }),
  getResumeReview: (token: string, id: string) => request(`/resumes/${id}/review`, { token }),
  regenerateResumeReview: (token: string, id: string) => request(`/resumes/${id}/review`, { method: "POST", token }),
  editResume: (token: string, id: string, body: { section: string; field_path: string; original_value: string; new_value: string; change_summary?: string }) =>
    request(`/resumes/${id}/edit`, { method: "POST", body: JSON.stringify(body), token }),
  listResumeVersions: (token: string, id: string) => request(`/resumes/${id}/versions`, { token }),
  restoreResumeVersion: (token: string, id: string, n: number) =>
    request(`/resumes/${id}/versions/${n}/restore`, { method: "POST", token }),
  improveResumeBullet: (token: string, id: string, body: { section: string; bullet_index: number; original: string; target_role?: string }) =>
    request(`/resumes/${id}/improve-bullet`, { method: "POST", body: JSON.stringify(body), token }),
  buildResume: (token: string, payload: unknown) => request(`/resumes/build`, { method: "POST", body: JSON.stringify({ payload }), token }),
  getAutofillProfile: (token: string, id: string) => request(`/resumes/${id}/autofill-profile`, { token }),

  createApplication: (token: string, body: { job_id: string; tailored_resume_id?: string }) =>
    request("/applications", { method: "POST", body: JSON.stringify(body), token }),
  listApplications: (token: string) => request("/applications", { token }),
  updateApplication: (token: string, id: string, body: unknown) =>
    request(`/applications/${id}`, { method: "PATCH", body: JSON.stringify(body), token }),
  queueApplicationPrefill: (token: string, id: string, consent_acknowledged = true) =>
    request(`/applications/${id}/automate`, {
      method: "POST",
      body: JSON.stringify({ consent_acknowledged }),
      token,
    }),
  getApplicationAudit: (token: string, id: string) =>
    request(`/applications/${id}/audit`, { token }),
  getAutomationTaskStatus: (token: string, taskId: string) =>
    request(`/applications/automate/tasks/${taskId}`, { token }),
  draftScreeningAnswer: (
    token: string,
    id: string,
    body: { question: string; ats_type?: string; approved?: boolean; edited_answer?: string; save_to_memory?: boolean },
  ) =>
    request(`/applications/${id}/screening/draft`, {
      method: "POST",
      body: JSON.stringify(body),
      token,
    }),

  getAnalyticsOverview: (token: string) => request("/analytics/overview", { token }),
  getAnalyticsCopilot: (token: string) => request("/analytics/copilot", { token }),
  refreshAnalyticsMarts: (token: string) => request("/analytics/marts/refresh", { method: "POST", token }),

  createCopilotSession: (token: string, body: unknown) =>
    request("/copilot/sessions", { method: "POST", body: JSON.stringify(body), token }),
  listCopilotSessions: (token: string) => request("/copilot/sessions", { token }),
  getInterviewQuestions: (token: string, id: string, jobId?: string) =>
    request(`/copilot/sessions/${id}/interview-questions${jobId ? `?job_id=${jobId}` : ""}`, { token }),

  discoverReferrals: (token: string, job_id: string) =>
    request("/referrals/discover", { method: "POST", body: JSON.stringify({ job_id }), token }),
  getReferralTask: (token: string, taskId: string) => request(`/referrals/discover/${taskId}/status`, { token }),
  listReferrals: (token: string, jobId?: string) => request(`/referrals${jobId ? `?job_id=${jobId}` : ""}`, { token }),
  convertReferral: (token: string, id: string) => request(`/referrals/${id}/convert`, { method: "POST", token }),
  updateReferral: (token: string, id: string, body: { status: string }) =>
    request(`/referrals/${id}`, { method: "PATCH", body: JSON.stringify(body), token }),

  createContact: (token: string, body: unknown) =>
    request("/contacts", { method: "POST", body: JSON.stringify(body), token }),
  importLinkedInContacts: async (token: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const csrf = getCsrfTokenFromCookie();
    const response = await fetchApi("/contacts/import/linkedin", {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers: {
        ...(csrf ? { "X-CSRF-Token": csrf } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: form,
    });
    if (!response.ok) throw new Error(await readErrorMessage(response));
    return response.json();
  },
  deleteContact: (token: string, id: string) => request(`/contacts/${id}`, { method: "DELETE", token }),
  listContacts: (token: string) => request("/contacts", { token }),
  draftOutreach: (token: string, body: { contact_id: string; job_id?: string }) =>
    request("/outreach/draft", { method: "POST", body: JSON.stringify(body), token }),
  listOutreach: (token: string) => request("/outreach", { token }),
  approveOutreach: (token: string, id: string) => request(`/outreach/${id}/approve`, { method: "POST", token }),
  sendOutreach: (token: string, id: string, manual_send_confirmed = true) =>
    request(`/outreach/${id}/send`, {
      method: "POST",
      body: JSON.stringify({ manual_send_confirmed }),
      token,
    }),
  updateOutreachStatus: (token: string, id: string, body: { status: string; follow_up_days?: number }) =>
    request(`/outreach/${id}/status`, { method: "PATCH", body: JSON.stringify(body), token }),
  getDueOutreachFollowups: (token: string) => request("/outreach/followups/due", { token }),

  getAnalyticsFunnel: (token: string) => request("/analytics/funnel", { token }),
  getAnalyticsReferrals: (token: string) => request("/analytics/referrals", { token }),

  getIngestionHealth: (token: string) => request<{ sources?: unknown[] }>("/admin/ingestion/health", { token }),
  getAlertsStatus: (token: string) => request("/admin/alerts/status", { token }),
  getRerankStatus: (token: string, days = 7) =>
    request(`/admin/ranking/rerank-status?days=${days}`, { token }),
  getRerankReadiness: (
    token: string,
    params: { days?: number; min_attempts?: number; max_timeout_rate?: number; max_failure_rate?: number; max_average_latency_ms?: number } = {},
  ) => {
    const q = new URLSearchParams();
    if (params.days !== undefined) q.set("days", String(params.days));
    if (params.min_attempts !== undefined) q.set("min_attempts", String(params.min_attempts));
    if (params.max_timeout_rate !== undefined) q.set("max_timeout_rate", String(params.max_timeout_rate));
    if (params.max_failure_rate !== undefined) q.set("max_failure_rate", String(params.max_failure_rate));
    if (params.max_average_latency_ms !== undefined) q.set("max_average_latency_ms", String(params.max_average_latency_ms));
    const qs = q.toString();
    return request(`/admin/ranking/rerank-readiness${qs ? `?${qs}` : ""}`, { token });
  },
  getRerankConfig: (token: string) => request("/admin/ranking/rerank-config", { token }),
  updateRerankConfig: (token: string, enabled: boolean | null) =>
    request("/admin/ranking/rerank-config", {
      method: "PUT",
      body: JSON.stringify({ enabled }),
      token,
    }),
  triggerIngestionAll: (token: string) => request("/admin/ingestion/trigger-all", { method: "POST", token }),

  buildApplyPlan: (
    token: string,
    sessionId: string,
    body: { max_jobs?: number; auto_tailor?: boolean; resume_id?: string; tailor_top_n?: number },
  ) =>
    request(`/copilot/sessions/${sessionId}/apply-plan`, {
      method: "POST",
      body: JSON.stringify(body),
      token,
    }),
};

export async function streamCopilotMessage(token: string, sessionId: string, message: string, onChunk: (chunk: string) => void): Promise<void> {
  const csrf = getCsrfTokenFromCookie();
  const response = await fetchApi(`/copilot/sessions/${sessionId}/message`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok || !response.body) throw new Error("Failed to stream response");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      if (part.startsWith("data: ")) onChunk(part.slice(6));
    }
  }
}
