from __future__ import annotations

from Spoken_model.dialogue.contracts.protocols import ScenarioPlugin
from Spoken_model.dialogue.contracts.types import SessionState


def evaluate_cycle(plugin: ScenarioPlugin, session: SessionState) -> dict:
    checklist = plugin.coverage_checklist()
    transcript_text = " ".join(
        f"{t.get('user', '')} {t.get('assistant', '')}" for t in session.transcript
    ).lower()

    covered: list[str] = []
    missing: list[str] = []
    for item in checklist:
        label = str(item.get("label") or item.get("id") or "")
        keywords = [str(k).lower() for k in item.get("keywords") or []]
        if not label:
            continue
        if keywords and any(k in transcript_text for k in keywords):
            covered.append(label)
        elif not keywords:
            covered.append(label)
        else:
            missing.append(label)

    user_turns = [t for t in session.transcript if t.get("user")]
    score = 0
    if user_turns:
        score = min(100, 40 + len(covered) * 10 + min(len(user_turns), 10) * 3)

    tips: list[str] = []
    if missing:
        tips.append(f"Try practicing: {', '.join(missing[:3])}.")
    if len(user_turns) < session.cycle_size:
        tips.append("Speak a bit more each cycle to build fluency.")
    if not tips:
        tips.append("Good job! Continue the next cycle or try open-ended ordering.")

    return {
        "cycle_index": session.cycle_index,
        "score": score,
        "covered": covered,
        "missing": missing,
        "turn_count": len(user_turns),
        "tips": tips,
    }
