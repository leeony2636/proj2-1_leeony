export type AgentRequest = {
  request_id?: string;
  session_id: string;
  team_id: string;
  puzzle_id: string;
  message: string;
};

export type CreateSessionRequest = {
  theme_id: string;
  team_id: string;
};

export type SessionSummary = {
  session_id: string;
  team_id: string;
  theme_id?: string;
  current_puzzle_id: string;
};

export type CreateSessionResponse = {
  session: SessionSummary;
};

export type VoiceAgentRequest = {
  session_id: string;
  team_id: string;
  puzzle_id: string;
  audio: File;
  language?: string;
};

export type VoiceAgentResponse = {
  status: "ACCEPTED" | "CONFIRMATION_REQUIRED" | "RETRY_REQUIRED";
  transcript?: string | null;
  confidence?: number | null;
  reason_codes?: string[];
  agent_response?: AgentResponse | null;
};

export type AgentResponse = {
  status: "NEED_MORE_INFO" | "INFORMATION" | "PROVIDE_HINT" | "ANSWER_CONFIRMATION_REQUIRED" | "MASTER_REQUEST" | "MULTI_ACTION" | "CLOSED" | "ERROR";
  hint_strength?: "WEAK" | "NORMAL" | "STRONG";
  hint_text?: string | null;
  offer_id?: string | null;
  offer_expires_at?: string | null;
  requires_confirmation?: boolean;
  reason_codes?: string[];
  next_action?: string | null;
  customer_message?: string | null;
  completed_actions?: string[];
  pending_actions?: string[];
  master_request_ids?: string[];
};

export type AnswerConfirmationRequest = {
  session_id: string;
  team_id: string;
  puzzle_id: string;
  offer_id: string;
};

export type AnswerResponse = {
  puzzle_id: string;
  answer: string;
  policy: "USER_EXPLICIT_CONFIRMATION" | string;
};

export type MasterRequestStatus = "OPEN" | "ACKNOWLEDGED" | "RESOLVED" | "CANCELED";

export type MasterRequest = {
  request_id: string;
  session_id: string;
  team_id: string;
  reason: string;
  status: MasterRequestStatus;
  created_at: string;
  operator_id?: string;
  note?: string;
};

export type MasterAction = "acknowledge" | "resolve" | "cancel";

export type MasterActionRequest = {
  operator_id: string;
  note?: string;
  idempotency_key?: string;
};

type Fetcher = typeof fetch;

async function postJson<T>(fetcher: Fetcher, url: string, body: unknown): Promise<T> {
  const response = await fetcher(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail ?? `API_REQUEST_FAILED:${response.status}`);
  }
  return payload as T;
}

async function postMultipart<T>(fetcher: Fetcher, url: string, body: FormData): Promise<T> {
  const response = await fetcher(url, { method: "POST", body });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail ?? `API_REQUEST_FAILED:${response.status}`);
  }
  return payload as T;
}

async function getJson<T>(fetcher: Fetcher, url: string): Promise<T> {
  const response = await fetcher(url, { method: "GET" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail ?? `API_REQUEST_FAILED:${response.status}`);
  }
  return payload as T;
}

export function createAgentApi(baseUrl = import.meta.env.VITE_API_BASE_URL ?? "", fetcher: Fetcher = fetch) {
  const normalizedBaseUrl = baseUrl.replace(/\/$/, "");
  return {
    createSession(payload: CreateSessionRequest) {
      return postJson<CreateSessionResponse>(fetcher, `${normalizedBaseUrl}/api/sessions`, payload);
    },
    requestHint(payload: AgentRequest) {
      return postJson<AgentResponse>(fetcher, `${normalizedBaseUrl}/api/agent`, payload);
    },
    requestVoiceHint(payload: VoiceAgentRequest) {
      // 수정 사유: multipart 요청에는 브라우저가 boundary를 설정하므로
      // Content-Type을 직접 지정하지 않고 기존 Agent 음성 경로로 전달한다.
      const form = new FormData();
      form.append("audio", payload.audio);
      form.append("session_id", payload.session_id);
      form.append("team_id", payload.team_id);
      form.append("puzzle_id", payload.puzzle_id);
      form.append("language", payload.language ?? "ko-KR");
      return postMultipart<VoiceAgentResponse>(fetcher, `${normalizedBaseUrl}/api/agent/voice`, form);
    },
    getMasterRequests() {
      return getJson<{ requests: MasterRequest[] }>(fetcher, `${normalizedBaseUrl}/api/master/requests`);
    },
    updateMasterRequest(requestId: string, action: MasterAction, payload: MasterActionRequest) {
      return postJson<MasterRequest>(
        fetcher,
        `${normalizedBaseUrl}/api/master/requests/${requestId}/${action}`,
        payload,
      );
    },
    confirmAnswer(payload: AnswerConfirmationRequest) {
      return postJson<AnswerResponse>(fetcher, `${normalizedBaseUrl}/api/answers/confirm`, payload);
    },
  };
}
