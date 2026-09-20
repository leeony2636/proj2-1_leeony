from fastapi import APIRouter, HTTPException

from backend.services.answer_vault import reveal_answer


router = APIRouter(prefix="/api/answers", tags=["answers"])


@router.get("/reveal")
def reveal(session_id: str, team_id: str, puzzle_id: str) -> dict:
    try:
        return reveal_answer(session_id, team_id, puzzle_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
