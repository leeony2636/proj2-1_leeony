from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
import json, uuid
from backend.schemas import HintEvent, SessionState

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "backend" / "data"
_SESSIONS: dict[str, SessionState] = {}
_HINT_EVENTS: list[HintEvent] = []
_MASTER_REQUESTS: list[dict] = []
_LOCK = Lock()

class LocalRuntime:
    def _theme(self, theme_id: str) -> dict:
        path = DATA_DIR / "themes" / f"{theme_id}.json"
        if not path.exists(): raise KeyError(f"THEME_NOT_FOUND:{theme_id}")
        return json.loads(path.read_text(encoding="utf-8"))
    def _hints(self, theme_id: str) -> dict:
        path = DATA_DIR / "hints" / f"{theme_id}.json"
        if not path.exists(): raise KeyError(f"HINT_DATA_NOT_FOUND:{theme_id}")
        return json.loads(path.read_text(encoding="utf-8"))
    def list_themes(self) -> list[dict]:
        out=[]
        for path in sorted((DATA_DIR/"themes").glob("*.json")):
            t=json.loads(path.read_text(encoding="utf-8"))
            out.append({"theme_id":t["theme_id"],"title":t["title"],"duration_minutes":t["duration_minutes"],"total_puzzles":len(t["puzzles"]),"difficulty":t.get("difficulty")})
        return out
    def create_session(self, theme_id: str, team_id: str) -> SessionState:
        theme=self._theme(theme_id); puzzles=theme.get("puzzles",[])
        if not puzzles: raise ValueError(f"THEME_HAS_NO_PUZZLES:{theme_id}")
        s=SessionState(session_id=str(uuid.uuid4()),team_id=team_id,theme_id=theme_id,started_at=datetime.now(timezone.utc),duration_minutes=int(theme["duration_minutes"]),total_puzzles=len(puzzles),current_puzzle_id=puzzles[0]["puzzle_id"])
        with _LOCK: _SESSIONS[s.session_id]=s
        return s
    def get_game_session(self, session_id: str) -> SessionState:
        if session_id not in _SESSIONS: raise KeyError(f"SESSION_NOT_FOUND:{session_id}")
        return _SESSIONS[session_id]
    def get_puzzle_context(self, theme_id: str, puzzle_id: str) -> dict:
        for p in self._theme(theme_id).get("puzzles",[]):
            if p["puzzle_id"]==puzzle_id: return p
        raise KeyError(f"PUZZLE_NOT_FOUND:{puzzle_id}")
    def get_hint_history(self, session_id: str, puzzle_id: str) -> list[HintEvent]:
        return [e for e in _HINT_EVENTS if e.session_id==session_id and e.puzzle_id==puzzle_id]
    def get_approved_hint(self, theme_id: str, puzzle_id: str, strength: str) -> str:
        try: return self._hints(theme_id)[puzzle_id][strength]
        except KeyError as exc: raise KeyError(f"APPROVED_HINT_NOT_FOUND:{theme_id}:{puzzle_id}:{strength}") from exc
    def record_hint_delivery(self,event:HintEvent)->None:
        with _LOCK: _HINT_EVENTS.append(event)
    def mark_puzzle_solved(self,session_id:str,puzzle_id:str)->SessionState:
        s=self.get_game_session(session_id); theme=self._theme(s.theme_id)
        valid={p["puzzle_id"] for p in theme["puzzles"]}
        if puzzle_id not in valid: raise KeyError(f"PUZZLE_NOT_FOUND:{puzzle_id}")
        if puzzle_id not in s.solved_puzzle_ids:
            s.solved_puzzle_ids.append(puzzle_id); s.solved_puzzles=len(s.solved_puzzle_ids)
        if s.solved_puzzles>=s.total_puzzles:
            s.is_closed=True; s.current_puzzle_id=None
        else:
            for p in theme["puzzles"]:
                if p["puzzle_id"] not in s.solved_puzzle_ids:
                    s.current_puzzle_id=p["puzzle_id"]; break
        _SESSIONS[session_id]=s; return s
    def request_game_master(self,session_id:str,team_id:str,reason:str)->dict:
        item={"request_id":str(uuid.uuid4()),"session_id":session_id,"team_id":team_id,"reason":reason,"created_at":datetime.now(timezone.utc).isoformat(),"status":"OPEN"}
        with _LOCK: _MASTER_REQUESTS.append(item)
        return item
    def get_master_requests(self)->list[dict]: return list(_MASTER_REQUESTS)
