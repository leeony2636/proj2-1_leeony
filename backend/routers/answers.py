from fastapi import APIRouter, HTTPException

from backend.schemas import AnswerConfirmationRequest, AnswerResponse
from backend.services.answer_vault import confirm_answer


router = APIRouter(prefix="/api/answers", tags=["answers"])


@router.post("/confirm", response_model=AnswerResponse)
def confirm(payload: AnswerConfirmationRequest) -> dict:
    # 수정 사유: ANSWER는 Agent 응답에서 바로 노출하지 않고 명시적 동의 API로 분리한다.
    try:
        return confirm_answer(
            payload.session_id,
            payload.team_id,
            payload.puzzle_id,
            payload.offer_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# 기존 GET /reveal은 STRONG 이력만으로 정답을 공개할 수 있어 MVP API에서 제거했다.
# 정답 공개는 위의 POST /confirm과 일회성 offer_id를 통한 동의만 허용한다.
