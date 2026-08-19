import axios from "axios";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api";

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Attach JWT token from localStorage
apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── LLM Admin ────────────────────────────────────────────────────────────────

export type ProviderOption = {
  provider: string;
  models: string[];
  is_default: boolean;
};

export type LLMSettingsPayload = {
  default_provider: string;
  default_model: string;
  fallback_provider: string;
  fallback_model: string;
  agent_overrides?: Record<string, { provider: string; model: string }>;
  embedding_provider: string;
  embedding_model: string;
  embedding_dimension: number;
  rerank_enabled: boolean;
  rerank_provider?: string;
  rerank_model?: string;
  rerank_top_k: number;
  rerank_return_n: number;
  guard_enabled: boolean;
  guard_mode: string;
  guard_config?: {
    sensitivity: number;
    pii_redact_input: boolean;
    pii_redact_output: boolean;
    max_input_chars?: number;
    max_output_chars?: number;
  };
  change_note?: string;
};

export const llmApi = {
  getOptions: () => apiClient.get<ProviderOption[]>("/admin/llm/options"),
  getSettings: () => apiClient.get<LLMSettingsPayload>("/admin/llm/settings"),
  saveSettings: (data: LLMSettingsPayload) =>
    apiClient.put<LLMSettingsPayload>("/admin/llm/settings", data),
  testConnection: (provider: string, model: string) =>
    apiClient.post("/admin/llm/test", { provider, model }),
  testGuard: (text: string, direction: "input" | "output" = "input") =>
    apiClient.post("/admin/llm/guard/test", { text, direction }),
};

export type DingTalkSettings = {
  enabled: boolean;
  webhook_url_masked: string;
  secret_configured: boolean;
  quiet_start: string;
  quiet_end: string;
  tz: string;
};

export const notifyApi = {
  getDingTalk: () => apiClient.get<DingTalkSettings>("/admin/notify/dingtalk"),
  saveDingTalk: (data: {
    enabled?: boolean;
    webhook_url?: string;
    secret?: string;
    quiet_start?: string;
    quiet_end?: string;
  }) => apiClient.put<DingTalkSettings>("/admin/notify/dingtalk", data),
  testDingTalk: (text?: string) =>
    apiClient.post("/admin/notify/dingtalk/test", { event: "test", text: text || "Admin 测试消息" }),
};

export default apiClient;
