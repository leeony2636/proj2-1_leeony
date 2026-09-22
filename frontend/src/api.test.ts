import { describe, expect, it, vi } from "vitest";
import { createAgentApi } from "./api";

describe("agent api client", () => {
  it("creates a customer session before hint requests", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        session: {
          session_id: "session-1",
          team_id: "team-1",
          current_puzzle_id: "train-p01",
        },
      }), { status: 200 }),
    );
    const api = createAgentApi("http://localhost:8000", fetcher);

    const result = await api.createSession({ theme_id: "last_train", team_id: "team-1" });

    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/api/sessions",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.session.session_id).toBe("session-1");
  });

  it("posts a customer hint request to the backend", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "PROVIDE_HINT", hint_text: "단서를 살펴보세요." }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const api = createAgentApi("http://localhost:8000", fetcher);

    const result = await api.requestHint({
      session_id: "session-1",
      team_id: "team-1",
      puzzle_id: "train-p01",
      message: "힌트 주세요",
    });

    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/api/agent",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.status).toBe("PROVIDE_HINT");
  });

  it("posts an audio file to the STT-to-agent endpoint", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ACCEPTED", agent_response: { status: "PROVIDE_HINT" } }), { status: 200 }),
    );
    const api = createAgentApi("http://localhost:8000", fetcher);
    const audio = new File(["audio"], "hint.webm", { type: "audio/webm" });

    const result = await api.requestVoiceHint({
      session_id: "session-1",
      team_id: "team-1",
      puzzle_id: "train-p01",
      audio,
    });

    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/api/agent/voice",
      expect.objectContaining({ method: "POST", body: expect.any(FormData) }),
    );
    expect(result.status).toBe("ACCEPTED");
  });

  it("posts an explicit answer confirmation", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        puzzle_id: "train-p01",
        answer: "DEMO_ANSWER_01",
        policy: "USER_EXPLICIT_CONFIRMATION",
      }), { status: 200 }),
    );
    const api = createAgentApi("http://localhost:8000", fetcher);

    const result = await api.confirmAnswer({
      session_id: "session-1",
      team_id: "team-1",
      puzzle_id: "train-p01",
      offer_id: "aof-1",
    });

    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/api/answers/confirm",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.policy).toBe("USER_EXPLICIT_CONFIRMATION");
  });

  it("reads and updates the game master request queue", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ requests: [{ request_id: "req-1", status: "OPEN" }] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ request_id: "req-1", status: "ACKNOWLEDGED" }), { status: 200 }));
    const api = createAgentApi("http://localhost:8000", fetcher);

    const queue = await api.getMasterRequests();
    const updated = await api.updateMasterRequest("req-1", "acknowledge", {
      operator_id: "gm-001",
      note: "확인 중",
    });

    expect(fetcher).toHaveBeenNthCalledWith(1, "http://localhost:8000/api/master/requests", expect.objectContaining({ method: "GET" }));
    expect(fetcher).toHaveBeenNthCalledWith(2, "http://localhost:8000/api/master/requests/req-1/acknowledge", expect.objectContaining({ method: "POST" }));
    expect(queue.requests[0].status).toBe("OPEN");
    expect(updated.status).toBe("ACKNOWLEDGED");
  });
});
