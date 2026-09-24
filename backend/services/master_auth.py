"""게임마스터 API 인증 경계.

실제 인증 제공자(JWT/SSO/API Gateway)는 아직 팀에서 선택하지 않았다. 따라서
운영/스테이징은 제공자가 연결되기 전 fail-closed이며, 로컬 개발/테스트에서만
명시적인 bypass 플래그를 허용한다.
"""
from __future__ import annotations

import os
from typing import Literal

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict


class MasterPrincipal(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    subject: str
    role: Literal["game_master", "admin", "viewer"]
    auth_source: str


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def resolve_master_principal(request: Request) -> MasterPrincipal:
    env = os.getenv("APP_ENV", "development").strip().lower()
    bypass = _truthy(os.getenv("GM_AUTH_BYPASS_LOCAL"))

    # 운영/스테이징에서 bypass 플래그가 실수로 켜져도 절대 허용하지 않는다.
    if bypass and env not in {"local", "development", "test"}:
        raise HTTPException(status_code=401, detail="GM_AUTH_MISCONFIGURED")

    if bypass:
        return MasterPrincipal(
            subject="local-game-master",
            role="game_master",
            auth_source="LOCAL_EXPLICIT_BYPASS",
        )

    # 향후 승인된 인증 middleware가 검증된 principal을 request.state에 주입할 수 있다.
    # operator_id 같은 body 자기신고 값은 이 경계에서 사용하지 않는다.
    raw = getattr(request.state, "master_principal", None)
    if raw is not None:
        try:
            return raw if isinstance(raw, MasterPrincipal) else MasterPrincipal.model_validate(raw, strict=True)
        except Exception as exc:
            raise HTTPException(status_code=401, detail="GM_AUTH_INVALID") from exc

    raise HTTPException(status_code=401, detail="GM_AUTH_REQUIRED")


def require_game_master_access(
    principal: MasterPrincipal = Depends(resolve_master_principal),
) -> MasterPrincipal:
    if principal.role not in {"game_master", "admin"}:
        raise HTTPException(status_code=403, detail="GM_FORBIDDEN")
    return principal
