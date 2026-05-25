"""
每日学习：开课、续学、快照保存（衔接 StudySession 与 DailyProgressStore）。
"""

from __future__ import annotations

from typing import Any

from Vocabulary_model.daily_progress_store import DailyProgressStore, build_daily_plan_segments
def _load_review_quotas_fn():
    import importlib.util
    import sys
    from pathlib import Path

    _rr_path = Path(__file__).resolve().parent / "review&reciting_data.py"
    _spec = importlib.util.spec_from_file_location("review_reciting_data_dyn", _rr_path)
    if _spec is None or _spec.loader is None:
        raise RuntimeError(f"无法加载: {_rr_path}")
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _mod
    _spec.loader.exec_module(_mod)
    return _mod.compute_daily_quotas


compute_daily_quotas = _load_review_quotas_fn()
from Vocabulary_model.study_words_cli import Entry, StudySession
from Vocabulary_model.user_settings import load_user_settings


def _merge_progress(state: dict[str, Any], progress: dict[str, Any]) -> dict[str, Any]:
    out = dict(state)
    out["progress"] = progress
    return out


def _idle_state(
    *,
    meta: str,
    wordbook: dict[str, str],
    progress: dict[str, Any],
    word: str = "点击「开始学习」",
    meaning: str = "中文释义会在你作答后显示。",
) -> dict[str, Any]:
    start_label = "继续学习" if progress.get("resumable") else "开始学习"
    finished_today = progress.get("status") == "completed"
    if finished_today:
        word = "今日学习任务已完成"
        meaning = (
            f"今日已完成 {progress.get('completed', 0)}/{progress.get('target', 0)} 个单词"
            f"（复习 {progress.get('review_completed', 0)}/{progress.get('review_target', 0)}，"
            f"新学 {progress.get('new_completed', 0)}/{progress.get('new_target', 0)}）。"
            "明天将开启新计划。"
        )
        start_label = "今日已完成"

    return {
        "phase": "idle",
        "word": word,
        "meaning": meaning,
        "meta": meta,
        "wordbook": wordbook,
        "phonetic": "",
        "examplePhrase": "",
        "progress": progress,
        "ui": {
            "startEnabled": not finished_today,
            "startLabel": start_label,
            "knownEnabled": False,
            "unknownEnabled": False,
            "showMistake": False,
            "showNext": False,
        },
    }


def ensure_today_plan(
    store: DailyProgressStore,
    *,
    wordbook_id: str,
    entries: list[Entry],
    daily_words: int,
    review_ratio: str,
    review_store: Any,
) -> dict[str, Any]:
    store.rollover_if_needed(wordbook_id)
    plan = store.get_today_plan(wordbook_id)
    if plan is not None:
        return plan

    new_target, review_quota = compute_daily_quotas(int(daily_words), review_ratio)
    new_target = max(1, min(new_target, len(entries)))
    all_words = [e.word for e in entries]
    review_plan = review_store.build_review_plan(
        new_target, review_ratio, wordbook_id=wordbook_id
    )
    carryover_review = store.get_carryover_review_words(wordbook_id)
    carryover_new = store.get_carryover_new_words(wordbook_id)
    segments = build_daily_plan_segments(
        all_entry_words=all_words,
        new_target=new_target,
        review_target=review_quota,
        review_words=review_plan.review_words,
        carryover_review_words=carryover_review,
        carryover_new_words=carryover_new,
    )
    carry_r_set = {w.casefold() for w in carryover_review}
    carry_n_set = {w.casefold() for w in carryover_new}
    used_review = [w for w in segments["review_words"] if w.casefold() in carry_r_set]
    used_new = [w for w in segments["new_words"] if w.casefold() in carry_n_set]
    store.consume_carryover_review(wordbook_id, used_review)
    store.consume_carryover_new(wordbook_id, used_new)
    return store.create_today_plan(
        wordbook_id,
        target=int(segments["target"]),
        planned_words=list(segments["planned_words"]),
        review_words=list(segments["review_words"]),
        new_words=list(segments["new_words"]),
        new_target=int(segments["new_target"]),
        review_target=int(segments["review_target"]),
    )


def create_session_from_plan(
    entries: list[Entry],
    plan: dict[str, Any],
    snapshot: dict[str, Any] | None,
) -> StudySession:
    planned = list(plan.get("planned_words") or [])
    completed = set(plan.get("completed_words") or [])
    session = StudySession.from_daily_state(
        entries,
        planned_words=planned,
        completed_words=completed,
        review_words=list(plan.get("review_words") or []),
        snapshot=snapshot,
    )
    return session


def start_or_resume(
    entries: list[Entry],
    *,
    wordbook_id: str,
    wordbook_label: str,
    review_store: Any,
    daily_words: int | None = None,
    review_ratio: str | None = None,
    force_new: bool = False,
) -> tuple[StudySession | None, dict[str, Any]]:
    settings = load_user_settings()
    count = int(daily_words if daily_words is not None else settings.get("daily_words", 50))
    ratio = str(review_ratio if review_ratio is not None else settings.get("review_ratio", "1:1"))

    store = DailyProgressStore()
    wid = wordbook_id
    wb = {"id": wid, "label": wordbook_label}
    meta_base = f"「{wordbook_label}」· 词库 {len(entries)} 条"

    plan = ensure_today_plan(
        store,
        wordbook_id=wid,
        entries=entries,
        daily_words=count,
        review_ratio=ratio,
        review_store=review_store,
    )
    progress = store.progress_payload(wid)

    if plan.get("status") == "completed":
        return None, _idle_state(
            meta=meta_base,
            wordbook=wb,
            progress=progress,
        )

    snapshot = None if force_new else store.get_session_snapshot(wid)
    session = create_session_from_plan(entries, plan, snapshot)

    if not session.active_pool:
        store.clear_session_snapshot(wid)
        progress = store.progress_payload(wid)
        return None, _idle_state(
            meta=f"{meta_base} | 今日已完成",
            wordbook=wb,
            progress=progress,
            word="今日学习任务已完成",
            meaning=f"今日已完成 {progress.get('completed', 0)}/{progress.get('target', 0)} 个单词。",
        )

    if snapshot is None and session.current is None:
        session.start()
    elif snapshot is None and session.current is not None:
        pass
    elif snapshot is not None and session.current is None and session.active_pool:
        session.start()

    save_session_snapshot(store, wid, session)
    progress = store.progress_payload(wid)
    state = _merge_progress(session.state(), progress)
    state["meta"] = session._meta_text()
    return session, state


def save_session_snapshot(
    store: DailyProgressStore, wordbook_id: str, session: StudySession
) -> None:
    store.save_session_snapshot(wordbook_id, session.to_snapshot())


def on_session_action(
    store: DailyProgressStore,
    wordbook_id: str,
    session: StudySession,
    *,
    just_completed_word: str | None = None,
) -> dict[str, Any]:
    if just_completed_word:
        store.mark_completed(wordbook_id, just_completed_word)
    if not session.active_pool:
        store.clear_session_snapshot(wordbook_id)
    else:
        save_session_snapshot(store, wordbook_id, session)
    progress = store.progress_payload(wordbook_id)
    return _merge_progress(session.state(), progress)


def idle_progress_state(
    entries_count: int,
    wordbook_id: str,
    wordbook_label: str,
) -> dict[str, Any]:
    store = DailyProgressStore()
    store.rollover_if_needed(wordbook_id)
    progress = store.progress_payload(wordbook_id)
    settings = load_user_settings()
    new_t, rev_t = compute_daily_quotas(
        int(settings.get("daily_words", 50)), str(settings.get("review_ratio", "1:1"))
    )
    if progress.get("status") == "none":
        progress = {
            **progress,
            "new_target": new_t,
            "review_target": rev_t,
            "target": new_t + rev_t,
        }
    meta = f"「{wordbook_label}」· 词库 {entries_count} 条"
    return _idle_state(
        meta=meta,
        wordbook={"id": wordbook_id, "label": wordbook_label},
        progress=progress,
    )
