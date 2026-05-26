from __future__ import annotations

from pathlib import Path

from Spoken_model.dialogue.contracts.protocols import ScenarioPlugin
from Spoken_model.dialogue.scenarios.loader import load_scenario

DIALOGUE_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = DIALOGUE_ROOT / "scenarios"
DEFAULT_DIR = SCENARIOS_DIR / "default"


def list_scenarios() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for child in sorted(SCENARIOS_DIR.iterdir()):
        if not child.is_dir() or child.name.startswith("_") or child.name == "default":
            continue
        manifest_path = child / "manifest.json"
        if not manifest_path.is_file():
            continue
        plugin = load_scenario(child, default_dir=DEFAULT_DIR)
        out.append(
            {
                "id": plugin.scenario_id,
                "title_zh": plugin.title_zh,
                "title_en": plugin.title_en,
            }
        )
    return out


def get_scenario(scenario_id: str) -> ScenarioPlugin:
    target = SCENARIOS_DIR / scenario_id
    if not target.is_dir():
        raise KeyError(f"unknown scenario: {scenario_id}")
    return load_scenario(target, default_dir=DEFAULT_DIR)
