from __future__ import annotations

from typing import Protocol


class SlackNotificationAdapter(Protocol):
    """게임마스터 운영 요청 알림을 외부 채널과 분리하는 최소 계약."""

    def send_master_request_notification(self, master_request: dict) -> None: ...


class MockSlackNotificationAdapter:
    """P0 개발·테스트용 Mock Slack Adapter.

    실제 Slack Webhook을 호출하지 않고, 전달된 운영 요청을 메모리에 보관한다.
    외부 인증·채널·재시도 정책이 확정되기 전까지 실제 Slack 전송은 하지 않는다.
    """

    def __init__(self) -> None:
        self.sent_requests: list[dict] = []

    def send_master_request_notification(self, master_request: dict) -> None:
        self.sent_requests.append(dict(master_request))

