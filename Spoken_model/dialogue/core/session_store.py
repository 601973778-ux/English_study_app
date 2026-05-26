from __future__ import annotations

import json
import uuid
from pathlib import Path

from Vocabulary_model.json_file_io import save_json_atomic

from Spoken_model.dialogue.contracts.types import SessionState, SessionStatus


class SessionStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, SessionState] = {}

    def _path(self, session_id: str) -> Path:
        return self._root / f"{session_id}.json"

    def create(
        self,
        *,
        scenario_id: str,
        cycle_size: int,
        default_stage: str,
    ) -> SessionState:
        session_id = uuid.uuid4().hex
        state = SessionState(
            session_id=session_id,
            scenario_id=scenario_id,
            stage=default_stage,
            cycle_index=1,
            user_count_in_cycle=0,
            cycle_size=cycle_size,
            status=SessionStatus.ACTIVE,
        )
        self.save(state)
        return state

    def get(self, session_id: str) -> SessionState | None:
        if session_id in self._cache:
            return self._cache[session_id]
        path = self._path(session_id)
        if not path.is_file():
            return None
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return None
        state = SessionState.from_dict(raw)
        self._cache[session_id] = state
        return state

    def save(self, state: SessionState) -> None:
        self._cache[state.session_id] = state
        save_json_atomic(self._path(state.session_id), state.to_dict())

    def delete(self, session_id: str) -> None:
        self._cache.pop(session_id, None)
        path = self._path(session_id)
        if path.is_file():
            path.unlink()
