from __future__ import annotations

from Spoken_model.dialogue.contracts.protocols import ScenarioPlugin
from Spoken_model.dialogue.contracts.types import RouteKind, SessionState


class ScriptEngine:
    def try_reply(
        self,
        plugin: ScenarioPlugin,
        user_text: str,
        session: SessionState,
        route: RouteKind,
    ) -> tuple[str | None, str | None]:
        if route not in (
            RouteKind.SCRIPT_CONTROL,
            RouteKind.SCRIPT_CHITCHAT,
            RouteKind.SCRIPT_TOPIC,
            RouteKind.REDIRECT,
        ):
            return None, None
        return plugin.try_script(user_text, session, route)
