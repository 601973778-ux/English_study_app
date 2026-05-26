# Spoken dialogue module

Modular spoken English practice: **script fast path** for chitchat/control/simple slots, **RAG + LLM** for open dialogue. LLM is stubbed until DeepSeek local deployment.

## Layout

```
Spoken_model/dialogue/
  contracts/       # types + adapter/scenario protocols
  core/            # pipeline, session store, registry, DialogueService
  engines/         # ScriptEngine, RagLlmEngine
  adapters/        # ASR/TTS/LLM/RAG wrappers
  evaluation/      # cycle rule evaluator
  scenarios/       # JSON scenario packs (default + restaurant_order)
  user_data/       # persisted sessions (gitignored)
```

## Turn pipeline

```
user text (or ASR later) → normalize → classify route
  → script engine (control/chitchat/topic/redirect)
  → else RAG retrieve → StubLlm or template reply
  → update session / stage → TTS URL → cycle counter (10 turns)
```

## API (via `app/server.py`)

| Method | Path | Body / query |
|--------|------|----------------|
| GET | `/api/dialogue/scenarios` | list scenarios |
| POST | `/api/dialogue/start` | `{ "scenario_id": "restaurant_order" }` |
| POST | `/api/dialogue/turn` | `{ "session_id", "user_text" }` |
| GET | `/api/dialogue/evaluation?session_id=` | cycle report |
| POST | `/api/dialogue/continue` | `{ "session_id" }` |
| POST | `/api/dialogue/end` | `{ "session_id" }` |

TTS: responses include `tts_url` → existing `GET /api/tts?text=...`.

## Dev test (text only)

```bash
# from repo root
python -m Spoken_model.dialogue.cli_text_test
```

Requires RAG index built once:

```bash
python -m Spoken_model.rag.build_kb
```

## Add a scenario

1. Copy `scenarios/restaurant_order/` to `scenarios/your_theme/`.
2. Edit `manifest.json`, `scenario.json`, `rag_filter.json`, `scripts/*.json`.
3. Restart server; scenario appears in `GET /api/dialogue/scenarios`.

## Later hooks

- **ASR**: implement `AsrAdapter` (e.g. Xfyun IAT), pass `audio_b64` in `/api/dialogue/turn`.
- **LLM**: replace `StubLlm` with `DeepSeekLlm` in `DialogueService` when local DeepSeek is ready; set `llm_enabled=True`.
