#!/usr/bin/env python3
"""Minimal text loop for dialogue module (no server)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Spoken_model.dialogue.contracts.types import TurnRequest
from Spoken_model.dialogue.core.dialogue_service import DialogueService


def main() -> None:
    svc = DialogueService(llm_enabled=False)
    started = svc.start("restaurant_order")
    session_id = started["session_id"]
    print(f"[waiter] {started['opening_line']}")
    print(f"session={session_id}  (type 'quit' to exit)\n")

    while True:
        user = input("[you] ").strip()
        if user.lower() in {"quit", "exit", "q"}:
            svc.end(session_id)
            print("bye")
            break
        if not user:
            continue
        result = svc.turn(TurnRequest(session_id=session_id, user_text=user))
        print(f"[waiter] {result.waiter_reply}  ({result.route.value}, {result.user_count_in_cycle}/{10})")
        if result.cycle_evaluation_ready:
            report = svc.evaluation(session_id)
            print(f"\n--- cycle {report['cycle_index']} score={report['score']} ---")
            print("covered:", report.get("covered"))
            print("tips:", report.get("tips"))
            choice = input("Continue next cycle? [y/N] ").strip().lower()
            if choice == "y":
                svc.continue_session(session_id)
                print("--- new cycle ---\n")
            else:
                svc.end(session_id)
                break


if __name__ == "__main__":
    main()
