import unittest
from datetime import datetime, timezone

from backend.schemas import HintEvent, HintStrength
from mcp_server.adapters.local_runtime import LocalRuntime


class LocalRuntimeIdempotencyTests(unittest.TestCase):
    def test_duplicate_hint_delivery_returns_existing_result(self):
        # 수정 사유: 같은 사용자 쓰기의 재전송이 힌트 이력을 중복 생성하지 않게 한다.
        runtime = LocalRuntime()
        session = runtime.create_session("last_train", "team-idem-hint")
        event = HintEvent(
            session_id=session.session_id,
            team_id=session.team_id,
            puzzle_id=session.current_puzzle_id,
            strength=HintStrength.WEAK,
            delivered_at=datetime.now(timezone.utc),
            reason_codes=["TEST"],
            idempotency_key="req-idem-hint:PROVIDED:train-p01",
        )

        first = runtime.record_hint_delivery(event)
        second = runtime.record_hint_delivery(event)

        self.assertFalse(first["deduplicated"])
        self.assertTrue(second["deduplicated"])
        self.assertEqual(len(runtime.get_hint_history(session.session_id, session.current_puzzle_id)), 1)

    def test_same_hint_key_with_different_payload_is_rejected(self):
        runtime = LocalRuntime()
        session = runtime.create_session("last_train", "team-idem-conflict")
        base = HintEvent(
            session_id=session.session_id,
            team_id=session.team_id,
            puzzle_id=session.current_puzzle_id,
            strength=HintStrength.WEAK,
            delivered_at=datetime.now(timezone.utc),
            reason_codes=["TEST"],
            idempotency_key="req-idem-conflict:PROVIDED:train-p01",
        )
        runtime.record_hint_delivery(base)

        conflict = base.model_copy(update={"strength": HintStrength.STRONG})
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_CONFLICT"):
            runtime.record_hint_delivery(conflict)

    def test_duplicate_game_master_request_returns_existing_result(self):
        # 수정 사유: 네트워크 재전송으로 게임마스터 호출이 중복 생성되지 않게 한다.
        runtime = LocalRuntime()
        session = runtime.create_session("last_train", "team-idem-master")
        first = runtime.request_game_master(
            session.session_id,
            "team-idem-master",
            "DIRECT_REQUEST",
            idempotency_key="req-idem-master:MASTER_REQUEST",
        )
        second = runtime.request_game_master(
            session.session_id,
            "team-idem-master",
            "DIRECT_REQUEST",
            idempotency_key="req-idem-master:MASTER_REQUEST",
        )

        self.assertEqual(first["request_id"], second["request_id"])
        self.assertTrue(second["deduplicated"])


if __name__ == "__main__":
    unittest.main()
