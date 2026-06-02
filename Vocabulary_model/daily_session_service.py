"""
每日学习：开课、续学、快照保存（衔接 StudySession 与 DailyProgressStore）。
"""

from __future__ import annotations

from typing import Any, Callable

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
        review_shortfall=int(review_plan.review_shortfall),
        planned_count=int(segments["planned_count"]),
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
        new_words=list(plan.get("new_words") or []),
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


def confirm_rebuild_requested(payload: dict[str, Any]) -> bool:
    v = payload.get("confirm_rebuild")
    return v in (True, 1, "1", "true", "yes")


def settings_affect_today_plan(prev: dict[str, Any], new: dict[str, Any]) -> bool:
    def _wb(v: Any) -> str:
        return str(v or "cet6").strip()

    try:
        prev_daily = int(prev.get("daily_words", 50))
    except (TypeError, ValueError):
        prev_daily = 50
    try:
        new_daily = int(new.get("daily_words", 50))
    except (TypeError, ValueError):
        new_daily = 50
    return (
        prev_daily != new_daily
        or str(prev.get("review_ratio", "1:1")) != str(new.get("review_ratio", "1:1"))
        or _wb(prev.get("wordbook_id")) != _wb(new.get("wordbook_id"))
    )


def needs_settings_confirm(
    prev: dict[str, Any],
    proposed: dict[str, Any],
    store: DailyProgressStore,
) -> bool:
    return settings_confirm_mode(prev, proposed, store) is not None


def settings_confirm_mode(
    prev: dict[str, Any],
    proposed: dict[str, Any],
    store: DailyProgressStore,
) -> str | None:
    """返回确认类型：rebuild=重排今日未完成计划；tomorrow=今日已完成，新设置明天生效。"""
    if not settings_affect_today_plan(prev, proposed):
        return None
    prev_wb = str(prev.get("wordbook_id", "cet6"))
    new_wb = str(proposed.get("wordbook_id", prev_wb))
    saw_completed = False
    for wid in {prev_wb, new_wb}:
        status = str(store.progress_payload(wid).get("status", "none"))
        if status == "in_progress":
            return "rebuild"
        if status == "completed":
            saw_completed = True
    if saw_completed:
        return "tomorrow"
    return None


def _merge_word_into_bucket(
    bucket: list[str], word: str, completed_cf: set[str]
) -> None:
    w = str(word).strip()
    if not w or w.casefold() in completed_cf:
        return
    if any(x.casefold() == w.casefold() for x in bucket):
        return
    bucket.append(w)


def push_unfinished_plan_to_carryover(
    store: DailyProgressStore,
    wordbook_id: str,
    plan: dict[str, Any],
) -> None:
    completed_cf = {w.casefold() for w in (plan.get("completed_words") or [])}
    review_set = {
        str(w).strip().casefold() for w in (plan.get("review_words") or [])
    }
    new_set = {str(w).strip().casefold() for w in (plan.get("new_words") or [])}
    carry_review = store.get_carryover_review_words(wordbook_id)
    carry_new = store.get_carryover_new_words(wordbook_id)
    for w in plan.get("planned_words") or []:
        w = str(w).strip()
        if not w or w.casefold() in completed_cf:
            continue
        k = w.casefold()
        if k in new_set and k not in review_set:
            _merge_word_into_bucket(carry_new, w, completed_cf)
        else:
            _merge_word_into_bucket(carry_review, w, completed_cf)
    store.set_carryover_review_words(wordbook_id, carry_review)
    store.set_carryover_new_words(wordbook_id, carry_new)


def rebuild_today_plan(
    store: DailyProgressStore,
    *,
    wordbook_id: str,
    entries: list[Entry],
    daily_words: int,
    review_ratio: str,
    review_store: Any,
) -> dict[str, Any] | None:
    plan = store.get_today_plan(wordbook_id)
    if not plan or plan.get("status") != "in_progress":
        return None

    completed = list(plan.get("completed_words") or [])
    push_unfinished_plan_to_carryover(store, wordbook_id, plan)

    carry_review = store.get_carryover_review_words(wordbook_id)
    carry_new = store.get_carryover_new_words(wordbook_id)

    new_target, review_quota = compute_daily_quotas(int(daily_words), review_ratio)
    new_target = max(1, min(new_target, len(entries)))
    all_words = [e.word for e in entries]
    review_plan = review_store.build_review_plan(
        new_target, review_ratio, wordbook_id=wordbook_id
    )
    completed_cf = {w.casefold() for w in completed}
    filtered_review = [
        w for w in review_plan.review_words if w.casefold() not in completed_cf
    ]
    segments = build_daily_plan_segments(
        all_entry_words=all_words,
        new_target=new_target,
        review_target=review_quota,
        review_words=filtered_review,
        carryover_review_words=carry_review,
        carryover_new_words=carry_new,
        exclude_words=completed,
    )
    planned_cf = {w.casefold() for w in segments["planned_words"]}
    store.set_carryover_review_words(
        wordbook_id,
        [w for w in carry_review if w.casefold() not in planned_cf],
    )
    store.set_carryover_new_words(
        wordbook_id,
        [w for w in carry_new if w.casefold() not in planned_cf],
    )
    return store.replace_today_plan(
        wordbook_id,
        segments=segments,
        review_shortfall=int(review_plan.review_shortfall),
        completed_words=completed,
    )


def apply_plan_changes_after_settings_save(
    store: DailyProgressStore,
    *,
    prev: dict[str, Any],
    settings: dict[str, Any],
    entries: list[Entry],
    review_store: Any,
) -> None:
    if not settings_affect_today_plan(prev, settings):
        return

    prev_wb = str(prev.get("wordbook_id", "cet6"))
    new_wb = str(settings.get("wordbook_id", "cet6"))

    if new_wb != prev_wb:
        prev_plan = store.get_today_plan(prev_wb)
        if prev_plan and prev_plan.get("status") == "in_progress":
            push_unfinished_plan_to_carryover(store, prev_wb, prev_plan)
            store.expire_today_plan(prev_wb)

    plan = store.get_today_plan(new_wb)
    if plan and plan.get("status") == "in_progress":
        rebuild_today_plan(
            store,
            wordbook_id=new_wb,
            entries=entries,
            daily_words=int(settings.get("daily_words", 50)),
            review_ratio=str(settings.get("review_ratio", "1:1")),
            review_store=review_store,
        )


def settings_api_payload(
    settings: dict[str, Any], store: DailyProgressStore
) -> dict[str, Any]:
    wid = str(settings.get("wordbook_id", "cet6"))
    progress = store.progress_payload(wid)
    status = str(progress.get("status", "none"))
    return {
        **settings,
        "today_plan_status": status,
        "today_plan_in_progress": status == "in_progress",
        "today_plan_completed": status == "completed",
        "today_completed": int(progress.get("completed", 0) or 0),
        "today_remaining": int(progress.get("remaining", 0) or 0),
        "today_target": int(progress.get("target", 0) or 0),
    }


SETTINGS_CONFIRM_MESSAGE = (
    "更改设置后，今日未完成计划将立刻发生改动。是否确定保存？"
)
SETTINGS_CONFIRM_COMPLETED_MESSAGE = (
    "今日计划已完成。保存后新设置将于明天自动生效（今日已完成进度不变）。是否确定保存？"
)


def _settings_confirm_message(mode: str) -> str:
    if mode == "tomorrow":
        return SETTINGS_CONFIRM_COMPLETED_MESSAGE
    return SETTINGS_CONFIRM_MESSAGE


def save_user_settings_with_plan(
    store: DailyProgressStore,
    payload: dict[str, Any],
    *,
    review_store: Any,
    get_entries: Callable[[], list[Entry]],
) -> tuple[int, dict[str, Any]]:
    """保存用户设置；若影响进行中的今日计划则须 confirm_rebuild。"""
    from Vocabulary_model.user_settings import load_user_settings, merge_user_settings, save_user_settings

    prev = load_user_settings()
    proposed = merge_user_settings(payload)
    confirm_mode = settings_confirm_mode(prev, proposed, store)
    if confirm_mode and not confirm_rebuild_requested(payload):
        return 409, {
            "error": _settings_confirm_message(confirm_mode),
            "requires_confirm": True,
            "confirm_mode": confirm_mode,
            "confirm_message": _settings_confirm_message(confirm_mode),
        }

    settings = save_user_settings(payload)
    session_cleared = False
    settings_apply_when = None
    if confirm_mode == "rebuild":
        apply_plan_changes_after_settings_save(
            store,
            prev=prev,
            settings=settings,
            entries=get_entries(),
            review_store=review_store,
        )
        session_cleared = True
        settings_apply_when = "now"
    elif confirm_mode == "tomorrow":
        settings_apply_when = "tomorrow"
    out = settings_api_payload(settings, store)
    out["session_cleared"] = session_cleared
    if settings_apply_when:
        out["settings_apply_when"] = settings_apply_when
    return 200, out


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
    if progress.get("status") == "none":
        new_t, rev_t = compute_daily_quotas(
            int(settings.get("daily_words", 50)), str(settings.get("review_ratio", "1:1"))
        )
        progress = {
            **progress,
            "new_quota": new_t,
            "review_quota": rev_t,
        }
    meta = f"「{wordbook_label}」· 词库 {entries_count} 条"
    return _idle_state(
        meta=meta,
        wordbook={"id": wordbook_id, "label": wordbook_label},
        progress=progress,
    )
