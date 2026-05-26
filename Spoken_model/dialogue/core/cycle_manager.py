from __future__ import annotations

from Spoken_model.dialogue.contracts.types import SessionState, SessionStatus


def increment_user_turn(session: SessionState) -> tuple[SessionState, bool]:
    """Increment cycle counter; return (session, evaluation_ready)."""
    session.user_count_in_cycle += 1
    ready = session.user_count_in_cycle >= session.cycle_size
    if ready:
        session.status = SessionStatus.AWAITING_EVAL
    return session, ready


def continue_cycle(session: SessionState) -> SessionState:
    session.cycle_index += 1
    session.user_count_in_cycle = 0
    session.status = SessionStatus.ACTIVE
    return session


def end_session(session: SessionState) -> SessionState:
    session.status = SessionStatus.ENDED
    return session
