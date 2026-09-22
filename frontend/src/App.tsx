import { useEffect, useState, type ReactNode } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import { createAgentApi, type AgentResponse, type MasterRequest, type MasterAction, type SessionSummary } from "./api";

function Shell({ role, children }: { role: string; children: ReactNode }) {
  return <main className="shell"><nav><Link to="/customer">고객 화면</Link><Link to="/game-master">게임마스터 화면</Link></nav><section className="card"><p className="eyebrow">ESCAPE ROOM AGENT</p><h1>{role}</h1>{children}</section></main>;
}

function Customer() {
  const api = createAgentApi();
  const [message, setMessage] = useState("");
  const [response, setResponse] = useState<AgentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [teamId, setTeamId] = useState("demo-team");
  const [session, setSession] = useState<SessionSummary | null>(null);
  const [starting, setStarting] = useState(false);

  async function startSession() {
    setStarting(true);
    setError(null);
    try {
      const result = await api.createSession({ theme_id: "last_train", team_id: teamId.trim() });
      setSession(result.session);
      setResponse(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "세션 시작에 실패했습니다.");
    } finally {
      setStarting(false);
    }
  }

  async function requestHint() {
    setError(null);
    setResponse(null);
    if (!session) return;
    try {
      const result = await api.requestHint({
        session_id: session.session_id,
        team_id: session.team_id,
        puzzle_id: session.current_puzzle_id,
        message,
      });
      setResponse(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "힌트 요청에 실패했습니다.");
    }
  }

  async function confirmAnswer() {
    if (!response?.offer_id) return;
    setConfirming(true);
    setError(null);
    try {
      const answer = await api.confirmAnswer({
        session_id: session?.session_id ?? "",
        team_id: session?.team_id ?? "",
        puzzle_id: session?.current_puzzle_id ?? "",
        offer_id: response.offer_id,
      });
      setResponse({ ...response, status: "PROVIDE_HINT", hint_text: answer.answer, requires_confirmation: false });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "정답 확인에 실패했습니다.");
    } finally {
      setConfirming(false);
    }
  }

  return <Shell role="힌트가 필요할 때 질문하세요">
    <p>현재 세션의 퍼즐 상황에 맞춰 단계적인 힌트를 제공합니다.</p>
    <label>
      팀 식별자
      <input aria-label="team id" value={teamId} onChange={(event) => setTeamId(event.target.value)} />
    </label>
    <button onClick={startSession} disabled={starting || !teamId.trim()}>
      {starting ? "세션 시작 중..." : session ? "새 세션 시작" : "세션 시작"}
    </button>
    {session && <p role="status">현재 세션: {session.session_id} · 퍼즐: {session.current_puzzle_id}</p>}
    <textarea aria-label="hint request" value={message} onChange={(event) => setMessage(event.target.value)} placeholder="예: 이 퍼즐의 다음 단계를 알려주세요" />
    <button onClick={requestHint} disabled={!session || !message.trim()}>힌트 요청</button>
    {response?.hint_text && <p role="status">{response.hint_text}</p>}
    {response?.status === "ANSWER_CONFIRMATION_REQUIRED" && <button onClick={confirmAnswer} disabled={confirming}>
      {confirming ? "정답 확인 중..." : "정답 보기"}
    </button>}
    {error && <p role="alert">{error}</p>}
  </Shell>;
}
// SMUS002: 제공된 Escape Ops 데모를 기존 게임마스터 라우트에 연결한다.
function GameMaster() {
  const api = createAgentApi();
  const [requests, setRequests] = useState<MasterRequest[]>([]);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function loadRequests() {
      try {
        const result = await api.getMasterRequests();
        if (active) {
          setRequests(result.requests);
          setQueueError(null);
        }
      } catch (cause) {
        if (active) setQueueError(cause instanceof Error ? cause.message : "요청 큐를 불러오지 못했습니다.");
      }
    }

    loadRequests();
    // 수정 사유: P0에서는 WebSocket보다 단순 polling으로 운영 요청 갱신을 검증한다.
    const timer = window.setInterval(loadRequests, 5000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  async function updateRequest(requestId: string, action: MasterAction) {
    setUpdating(requestId);
    try {
      await api.updateMasterRequest(requestId, action, {
        operator_id: "gm-demo",
        note: action === "acknowledge" ? "게임마스터 확인" : action === "resolve" ? "현장 처리 완료" : "요청 취소",
        idempotency_key: `ui:${requestId}:${action}`,
      });
      const result = await api.getMasterRequests();
      setRequests(result.requests);
      setQueueError(null);
    } catch (cause) {
      setQueueError(cause instanceof Error ? cause.message : "요청 상태 변경에 실패했습니다.");
    } finally {
      setUpdating(null);
    }
  }

  return <main className="ops-page">
    <iframe
      className="ops-frame"
      src="/escape-ops/index.html"
      title="ESCAPE OPS 게임마스터 관제 화면"
    />
    <aside className="master-live-panel" aria-label="실시간 게임마스터 요청">
      <div className="master-live-header"><strong>LIVE REQUESTS</strong><span>{requests.filter((item) => item.status === "OPEN").length} 대기</span></div>
      {queueError && <p className="master-live-error" role="alert">{queueError}</p>}
      {!queueError && requests.length === 0 && <p className="master-live-empty">현재 운영 요청이 없습니다.</p>}
      {requests.slice(-5).reverse().map((item) => <article className={`master-request ${item.status.toLowerCase()}`} key={item.request_id}>
        <div><b>{item.status}</b><small>{item.team_id} · {item.reason}</small></div>
        {item.status === "OPEN" && <button disabled={updating === item.request_id} onClick={() => updateRequest(item.request_id, "acknowledge")}>확인</button>}
        {item.status === "ACKNOWLEDGED" && <button disabled={updating === item.request_id} onClick={() => updateRequest(item.request_id, "resolve")}>해결</button>}
        {(item.status === "OPEN" || item.status === "ACKNOWLEDGED") && <button className="cancel-request" disabled={updating === item.request_id} onClick={() => updateRequest(item.request_id, "cancel")}>취소</button>}
      </article>)}
    </aside>
    <Link className="ops-customer-link" to="/customer">고객 화면으로 이동</Link>
  </main>;
}
export default function App() { return <Routes><Route path="/" element={<Navigate to="/customer" replace />} /><Route path="/customer" element={<Customer />} /><Route path="/game-master" element={<GameMaster />} /></Routes>; }
