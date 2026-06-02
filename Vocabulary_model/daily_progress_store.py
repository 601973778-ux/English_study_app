"""
每日学习计划与会话快照（按词书 + 自然日）。

文件：Vocabulary_model/user_data/daily_progress.json
"""

from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from Vocabulary_model.json_file_io import save_json_atomic
from Vocabulary_model.wordbook_catalog import DEFAULT_WORDBOOK_ID, normalize_wordbook_id

DATA_DIR = Path(__file__).resolve().parent / "user_data"
DAILY_PROGRESS_FILE = DATA_DIR / "daily_progress.json"
FILE_VERSION = 1
DEFAULT_TZ = "Asia/Shanghai"


def _utc_now_iso() -> str:
    return datetime.now(ZoneInfo("UTC")).isoformat()


def today_key(tz_name: str = DEFAULT_TZ) -> str:
    return datetime.now(ZoneInfo(tz_name)).date().isoformat()


def _empty_root() -> dict[str, Any]:
    return {"version": FILE_VERSION, "timezone": DEFAULT_TZ, "wordbooks": {}}


def _empty_bucket() -> dict[str, Any]:
    return {
        "current_date": "",
        "plans": {},
        "carryover_review_words": [],
        "carryover_new_words": [],
        "session": None,
    }


def _normalize_carryover_bucket(bucket: dict[str, Any]) -> None:
    """兼容旧字段 carryover_words：未拆分时全部视为昨日未完成的复习段。"""
    if not isinstance(bucket.get("carryover_review_words"), list):
        bucket["carryover_review_words"] = []
    if not isinstance(bucket.get("carryover_new_words"), list):
        bucket["carryover_new_words"] = []
    legacy = bucket.get("carryover_words")
    if isinstance(legacy, list) and legacy:
        seen = {w.casefold() for w in bucket["carryover_review_words"]}
        for w in legacy:
            w = str(w).strip()
            if w and w.casefold() not in seen:
                bucket["carryover_review_words"].append(w)
                seen.add(w.casefold())
        bucket.pop("carryover_words", None)


class DailyProgressStore:
    def __init__(self, path: Path | str = DAILY_PROGRESS_FILE, tz_name: str = DEFAULT_TZ) -> None:
        self.path = Path(path)
        self.tz_name = tz_name
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            self._save(_empty_root())

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return _empty_root()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _empty_root()
        if not isinstance(data, dict):
            return _empty_root()
        data.setdefault("version", FILE_VERSION)
        data.setdefault("timezone", self.tz_name)
        data.setdefault("wordbooks", {})
        return data

    def _save(self, data: dict[str, Any]) -> None:
        data["version"] = FILE_VERSION
        data.setdefault("timezone", self.tz_name)
        save_json_atomic(self.path, data)

    def _bucket(self, data: dict[str, Any], wordbook_id: str) -> dict[str, Any]:
        wid = normalize_wordbook_id(wordbook_id)
        wb = data["wordbooks"].setdefault(wid, _empty_bucket())
        if not isinstance(wb.get("plans"), dict):
            wb["plans"] = {}
        _normalize_carryover_bucket(wb)
        return wb

    def rollover_if_needed(self, wordbook_id: str) -> str:
        """跨日：未完成词按「复习/新学」放回对应 backlog，过期昨日计划。返回今日日期键。"""
        today = today_key(self.tz_name)
        data = self._load()
        bucket = self._bucket(data, wordbook_id)

        prev_date = str(bucket.get("current_date") or "").strip()
        if prev_date and prev_date != today:
            old_plan = bucket["plans"].get(prev_date)
            if isinstance(old_plan, dict) and old_plan.get("status") == "in_progress":
                planned = old_plan.get("planned_words") or []
                completed = set(old_plan.get("completed_words") or [])
                unfinished = [w for w in planned if w not in completed]
                review_set = {str(w).strip().casefold() for w in (old_plan.get("review_words") or [])}
                new_set = {str(w).strip().casefold() for w in (old_plan.get("new_words") or [])}
                carry_review: list[str] = list(bucket.get("carryover_review_words") or [])
                carry_new: list[str] = list(bucket.get("carryover_new_words") or [])
                seen_r = {w.casefold() for w in carry_review}
                seen_n = {w.casefold() for w in carry_new}
                for w in unfinished:
                    w = str(w).strip()
                    if not w:
                        continue
                    k = w.casefold()
                    if k in new_set and k not in review_set:
                        if k not in seen_n:
                            carry_new.append(w)
                            seen_n.add(k)
                    else:
                        if k not in seen_r:
                            carry_review.append(w)
                            seen_r.add(k)
                bucket["carryover_review_words"] = carry_review
                bucket["carryover_new_words"] = carry_new
                old_plan["status"] = "expired"
            bucket["session"] = None

        bucket["current_date"] = today
        self._save(data)
        return today

    def get_today_plan(self, wordbook_id: str) -> dict[str, Any] | None:
        today = self.rollover_if_needed(wordbook_id)
        data = self._load()
        bucket = self._bucket(data, wordbook_id)
        plan = bucket["plans"].get(today)
        return plan if isinstance(plan, dict) else None

    def create_today_plan(
        self,
        wordbook_id: str,
        *,
        target: int,
        planned_words: list[str],
        review_words: list[str] | None = None,
        new_words: list[str] | None = None,
        new_target: int | None = None,
        review_target: int | None = None,
        review_shortfall: int = 0,
        planned_count: int | None = None,
    ) -> dict[str, Any]:
        today = self.rollover_if_needed(wordbook_id)
        data = self._load()
        bucket = self._bucket(data, wordbook_id)
        now = _utc_now_iso()
        rw = list(review_words or [])
        nw = list(new_words or [])
        new_quota = int(new_target if new_target is not None else len(nw))
        review_quota = int(review_target if review_target is not None else len(rw))
        scheduled = int(planned_count if planned_count is not None else len(planned_words))
        plan = {
            "target": scheduled,
            "planned_count": scheduled,
            "planned_words": list(planned_words),
            "review_words": rw,
            "new_words": nw,
            "new_quota": new_quota,
            "review_quota": review_quota,
            "new_target": len(nw),
            "review_target": len(rw),
            "review_shortfall": max(0, int(review_shortfall)),
            "completed_words": [],
            "word_segments": {},
            "status": "in_progress",
            "created_at": now,
            "updated_at": now,
        }
        bucket["plans"][today] = plan
        bucket["session"] = None
        self._save(data)
        return plan

    def mark_completed(self, wordbook_id: str, word: str) -> None:
        w = str(word).strip()
        if not w:
            return
        today = today_key(self.tz_name)
        data = self._load()
        bucket = self._bucket(data, wordbook_id)
        plan = bucket["plans"].get(today)
        if not isinstance(plan, dict):
            return
        completed: list[str] = list(plan.get("completed_words") or [])
        if w not in completed:
            completed.append(w)
            segments: dict[str, str] = dict(plan.get("word_segments") or {})
            review_set = {str(x).strip() for x in (plan.get("review_words") or []) if str(x).strip()}
            new_set = {str(x).strip() for x in (plan.get("new_words") or []) if str(x).strip()}
            if w in review_set:
                segments[w] = "review"
            elif w in new_set:
                segments[w] = "new"
            plan["word_segments"] = segments
        plan["completed_words"] = completed
        plan["updated_at"] = _utc_now_iso()
        remaining = [x for x in plan.get("planned_words") or [] if x not in set(completed)]
        if not remaining:
            plan["status"] = "completed"
            bucket["session"] = None
        self._save(data)

    def get_carryover_review_words(self, wordbook_id: str) -> list[str]:
        data = self._load()
        bucket = self._bucket(data, wordbook_id)
        return [
            str(w).strip()
            for w in bucket.get("carryover_review_words") or []
            if str(w).strip()
        ]

    def get_carryover_new_words(self, wordbook_id: str) -> list[str]:
        data = self._load()
        bucket = self._bucket(data, wordbook_id)
        return [
            str(w).strip()
            for w in bucket.get("carryover_new_words") or []
            if str(w).strip()
        ]

    def get_carryover_words(self, wordbook_id: str) -> list[str]:
        """兼容：复习 + 新学 backlog 合并列表。"""
        return self.get_carryover_review_words(wordbook_id) + self.get_carryover_new_words(
            wordbook_id
        )

    def consume_carryover_review(self, wordbook_id: str, used_words: Iterable[str]) -> None:
        used_cf = {str(w).strip().casefold() for w in used_words if str(w).strip()}
        if not used_cf:
            return
        data = self._load()
        bucket = self._bucket(data, wordbook_id)
        carry = bucket.get("carryover_review_words") or []
        bucket["carryover_review_words"] = [
            w for w in carry if str(w).casefold() not in used_cf
        ]
        self._save(data)

    def consume_carryover_new(self, wordbook_id: str, used_words: Iterable[str]) -> None:
        used_cf = {str(w).strip().casefold() for w in used_words if str(w).strip()}
        if not used_cf:
            return
        data = self._load()
        bucket = self._bucket(data, wordbook_id)
        carry = bucket.get("carryover_new_words") or []
        bucket["carryover_new_words"] = [
            w for w in carry if str(w).casefold() not in used_cf
        ]
        self._save(data)

    def consume_carryover(self, wordbook_id: str, used_words: Iterable[str]) -> None:
        """从复习/新学 backlog 中移除已纳入今日计划的词。"""
        self.consume_carryover_review(wordbook_id, used_words)
        self.consume_carryover_new(wordbook_id, used_words)

    def set_carryover_review_words(self, wordbook_id: str, words: list[str]) -> None:
        data = self._load()
        bucket = self._bucket(data, wordbook_id)
        bucket["carryover_review_words"] = [
            str(w).strip() for w in words if str(w).strip()
        ]
        self._save(data)

    def set_carryover_new_words(self, wordbook_id: str, words: list[str]) -> None:
        data = self._load()
        bucket = self._bucket(data, wordbook_id)
        bucket["carryover_new_words"] = [
            str(w).strip() for w in words if str(w).strip()
        ]
        self._save(data)

    def replace_today_plan(
        self,
        wordbook_id: str,
        *,
        segments: dict[str, Any],
        review_shortfall: int,
        completed_words: list[str],
    ) -> dict[str, Any]:
        today = today_key(self.tz_name)
        data = self._load()
        bucket = self._bucket(data, wordbook_id)
        plan = bucket["plans"].get(today)
        if not isinstance(plan, dict):
            raise ValueError("今日尚无学习计划，无法重排")
        rw = list(segments["review_words"])
        nw = list(segments["new_words"])
        planned = list(segments["planned_words"])
        scheduled = int(segments["planned_count"])
        new_quota = int(segments["new_target"])
        review_quota = int(segments["review_target"])
        completed = list(completed_words)
        completed_set = set(completed)
        remaining = [w for w in planned if w not in completed_set]
        word_segments = dict(plan.get("word_segments") or {})
        plan.update(
            {
                "target": len(completed) + len(remaining),
                "planned_count": scheduled,
                "planned_words": planned,
                "review_words": rw,
                "new_words": nw,
                "new_quota": new_quota,
                "review_quota": review_quota,
                "new_target": len(nw),
                "review_target": len(rw),
                "review_shortfall": max(0, int(review_shortfall)),
                "completed_words": completed,
                "word_segments": word_segments,
                "status": "completed" if not remaining else "in_progress",
                "updated_at": _utc_now_iso(),
            }
        )
        bucket["session"] = None
        self._save(data)
        return plan

    def expire_today_plan(self, wordbook_id: str) -> None:
        today = today_key(self.tz_name)
        data = self._load()
        bucket = self._bucket(data, wordbook_id)
        plan = bucket["plans"].get(today)
        if isinstance(plan, dict) and plan.get("status") == "in_progress":
            plan["status"] = "expired"
            plan["updated_at"] = _utc_now_iso()
        bucket["session"] = None
        self._save(data)

    def save_session_snapshot(self, wordbook_id: str, snapshot: dict[str, Any]) -> None:
        today = today_key(self.tz_name)
        data = self._load()
        bucket = self._bucket(data, wordbook_id)
        plan = bucket["plans"].get(today)
        if not isinstance(plan, dict) or plan.get("status") != "in_progress":
            return
        snapshot = dict(snapshot)
        snapshot["date"] = today
        bucket["session"] = snapshot
        plan["updated_at"] = _utc_now_iso()
        self._save(data)

    def clear_session_snapshot(self, wordbook_id: str) -> None:
        data = self._load()
        bucket = self._bucket(data, wordbook_id)
        bucket["session"] = None
        self._save(data)

    def get_session_snapshot(self, wordbook_id: str) -> dict[str, Any] | None:
        today = today_key(self.tz_name)
        data = self._load()
        bucket = self._bucket(data, wordbook_id)
        snap = bucket.get("session")
        if not isinstance(snap, dict):
            return None
        if str(snap.get("date", "")) != today:
            return None
        return snap

    @staticmethod
    def _segment_of_word(word: str, plan: dict[str, Any]) -> str:
        w = str(word).strip()
        if not w:
            return "review"
        segments = plan.get("word_segments") or {}
        if isinstance(segments, dict) and w in segments:
            seg = str(segments[w]).strip().lower()
            if seg in ("review", "new"):
                return seg
        review_cf = {
            str(x).strip().casefold()
            for x in (plan.get("review_words") or [])
            if str(x).strip()
        }
        new_cf = {
            str(x).strip().casefold()
            for x in (plan.get("new_words") or [])
            if str(x).strip()
        }
        k = w.casefold()
        if k in new_cf:
            return "new"
        if k in review_cf:
            return "review"
        # 重排前已完成、当前段列表中已不存在的词，按复习计入（兼容旧数据）
        return "review"

    @classmethod
    def _daily_segment_progress(cls, plan: dict[str, Any]) -> tuple[int, int, int, int]:
        """返回 (复习完成, 复习实际排入, 新学完成, 新学实际排入)。"""
        review_words = list(plan.get("review_words") or [])
        new_words = list(plan.get("new_words") or [])
        completed_list = list(plan.get("completed_words") or [])
        completed_set = set(completed_list)
        review_done = sum(
            1 for w in completed_list if cls._segment_of_word(w, plan) == "review"
        )
        new_done = sum(
            1 for w in completed_list if cls._segment_of_word(w, plan) == "new"
        )
        review_remaining = sum(1 for w in review_words if w not in completed_set)
        new_remaining = sum(1 for w in new_words if w not in completed_set)
        review_scheduled = review_done + review_remaining
        new_scheduled = new_done + new_remaining
        return review_done, review_scheduled, new_done, new_scheduled

    def progress_payload(self, wordbook_id: str) -> dict[str, Any]:
        today = self.rollover_if_needed(wordbook_id)
        plan = self.get_today_plan(wordbook_id)
        if not plan:
            return {
                "date": today,
                "target": 0,
                "completed": 0,
                "remaining": 0,
                "new_target": 0,
                "review_target": 0,
                "new_completed": 0,
                "review_completed": 0,
                "new_remaining": 0,
                "review_remaining": 0,
                "segment": "none",
                "status": "none",
                "resumable": False,
            }
        review_words = list(plan.get("review_words") or [])
        new_words = list(plan.get("new_words") or [])
        planned_words = list(plan.get("planned_words") or [])
        completed_set = set(plan.get("completed_words") or [])
        review_quota = int(plan.get("review_quota", plan.get("review_target", len(review_words))))
        new_quota = int(plan.get("new_quota", plan.get("new_target", len(new_words))))
        planned_count = int(
            plan.get("planned_count", len(planned_words))
        ) or (len(review_words) + len(new_words))
        review_completed, review_scheduled, new_completed, new_scheduled = (
            self._daily_segment_progress(plan)
        )
        completed = len(completed_set)
        review_remaining = max(0, review_scheduled - review_completed)
        new_remaining = max(0, new_scheduled - new_completed)
        remaining = sum(1 for w in planned_words if w not in completed_set)
        target = completed + remaining
        review_shortfall = int(
            plan.get("review_shortfall", max(0, review_quota - review_scheduled))
        )
        if review_remaining > 0:
            segment = "review"
        elif new_remaining > 0:
            segment = "new"
        else:
            segment = "done"
        status = str(plan.get("status", "in_progress"))
        snap = self.get_session_snapshot(wordbook_id)
        resumable = status == "in_progress" and remaining > 0
        data = self._load()
        bucket = self._bucket(data, wordbook_id)
        return {
            "date": today,
            "target": target,
            "completed": completed,
            "remaining": remaining,
            "new_target": new_scheduled,
            "review_target": review_scheduled,
            "new_quota": new_quota,
            "review_quota": review_quota,
            "review_shortfall": review_shortfall,
            "planned_count": planned_count,
            "carryover_review_pending": len(bucket.get("carryover_review_words") or []),
            "carryover_new_pending": len(bucket.get("carryover_new_words") or []),
            "new_completed": new_completed,
            "review_completed": review_completed,
            "new_remaining": new_remaining,
            "review_remaining": review_remaining,
            "segment": segment,
            "status": status,
            "resumable": resumable and status == "in_progress",
        }


def build_daily_plan_segments(
    *,
    all_entry_words: list[str],
    new_target: int,
    review_target: int,
    review_words: list[str],
    carryover_review_words: list[str] | None = None,
    carryover_new_words: list[str] | None = None,
    carryover_words: list[str] | None = None,
    exclude_words: list[str] | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """
    今日计划：复习段、新学段各自有配额（来自用户设置）。
    昨日未完成词优先占用对应段配额，不足再从词库/已学池补足；不会「carryover + 配额」叠成 100。
    """
    rng = random.Random(seed)
    word_set = set(all_entry_words)
    seen: set[str] = {
        str(w).casefold() for w in (exclude_words or []) if str(w).strip()
    }
    new_quota = max(0, int(new_target))
    review_quota = max(0, int(review_target))

    legacy_carry = list(carryover_words or [])
    carry_review = list(carryover_review_words or []) + legacy_carry
    carry_new = list(carryover_new_words or [])

    def add_word(bucket: list[str], w: str, limit: int) -> bool:
        if len(bucket) >= limit:
            return False
        w = str(w).strip()
        if not w or w not in word_set:
            return False
        k = w.casefold()
        if k in seen:
            return False
        seen.add(k)
        bucket.append(w)
        return True

    review_list: list[str] = []
    rng.shuffle(carry_review)
    for w in carry_review:
        if len(review_list) >= review_quota:
            break
        add_word(review_list, w, review_quota)
    for w in review_words:
        if len(review_list) >= review_quota:
            break
        add_word(review_list, w, review_quota)

    new_list: list[str] = []
    rng.shuffle(carry_new)
    for w in carry_new:
        if len(new_list) >= new_quota:
            break
        add_word(new_list, w, new_quota)
    rest = [w for w in all_entry_words if w.casefold() not in seen]
    rng.shuffle(rest)
    for w in rest:
        if len(new_list) >= new_quota:
            break
        add_word(new_list, w, new_quota)

    planned = review_list + new_list
    scheduled = len(planned)
    return {
        "review_words": review_list,
        "new_words": new_list,
        "planned_words": planned,
        "target": scheduled,
        "planned_count": scheduled,
        "new_target": new_quota,
        "review_target": review_quota,
    }
