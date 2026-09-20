class ERCCAdapter:
    """P0 미연결.

    실제 ERCC 사용이 확정되면 room/timer/hint API를
    내부 공통 계약으로 변환하는 Adapter로 구현한다.
    """

    def not_connected(self) -> None:
        raise NotImplementedError("ERCC_ADAPTER_NOT_CONNECTED")
