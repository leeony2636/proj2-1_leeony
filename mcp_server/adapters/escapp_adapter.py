class EscappAdapter:
    """P0 미연결.

    공개 Escapp 구조는 참고만 하고 전체 코드를 복제하지 않는다.
    실제 연동 필요 시 내부 공통 계약으로 변환한다.
    """

    def not_connected(self) -> None:
        raise NotImplementedError("ESCAPP_ADAPTER_NOT_CONNECTED")
