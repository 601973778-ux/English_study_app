# Spoken dialogue module

Modular spoken English practice: **script fast path** (optional), **quick chitchat** for short greetings, **RAG + DeepSeek LLM** for open dialogue.

## Layout

```
Spoken_model/dialogue/
  config/          # llm_defaults.json, dialogue_flags.json
  data/            # quick_chitchat.json (fast hello/thanks replies)
  contracts/       # types + adapter/scenario protocols
  core/            # pipeline, session store, registry, DialogueService
  engines/         # ScriptEngine, QuickChitchatEngine, RagLlmEngine
  adapters/        # ASR/TTS/LLM/RAG wrappers
  evaluation/      # cycle rule evaluator
  scenarios/       # JSON scenario packs (default + restaurant_order)
  user_data/       # sessions + llm_settings.json (gitignored)
```

## Turn pipeline

**Default (script frozen)** — see `config/dialogue_flags.json` (`script_engine_frozen: true`):

```
user text → normalize
  → quick chitchat patterns (hello/thanks/bye from data/quick_chitchat.json)
  → else RAG retrieve → DeepSeek chat (or template if LLM off)
  → update session / stage → TTS URL → cycle counter (10 turns)
```

**Legacy (script enabled)** — set `script_engine_frozen: false` or `DIALOGUE_SCRIPT_FROZEN=0`:

```
user text → classify route → script engine (control/chitchat/topic/redirect)
  → else RAG + LLM as above
```

Script engine code remains in the repo; when frozen it is not called.

## DeepSeek LLM 配置

支持 **DeepSeek 官方 API** 与 **本地 OpenAI 兼容服务**（Ollama / vLLM / LM Studio）。

### 方式一：环境变量

```bash
set DIALOGUE_LLM_ENABLED=true
set DEEPSEEK_API_KEY=sk-...
# 本地部署示例：
# set DEEPSEEK_BASE_URL=http://127.0.0.1:11434/v1
# set DEEPSEEK_MODEL=deepseek-r1:7b
```

### 方式二：配置文件

写入 `Spoken_model/dialogue/user_data/llm_settings.json`（或通过 API）：

```json
{
  "enabled": true,
  "base_url": "https://api.deepseek.com/v1",
  "model": "deepseek-chat",
  "api_key": "sk-...",
  "max_tokens": 256,
  "temperature": 0.7,
  "rag_min_score": 0.15
}
```

本地无 API Key 时，只要 `base_url` 为 `localhost` / `127.0.0.1` 也可启用。

### HTTP API

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/dialogue/llm-config` | 查看配置（密钥脱敏） |
| POST | `/api/dialogue/llm-config` | 保存配置并热重载 LLM |

## Dialogue API

| Method | Path | Body / query |
|--------|------|----------------|
| GET | `/api/dialogue/scenarios` | list scenarios |
| POST | `/api/dialogue/start` | `{ "scenario_id": "restaurant_order" }` |
| POST | `/api/dialogue/turn` | `{ "session_id", "user_text" }` |
| GET | `/api/dialogue/evaluation?session_id=` | cycle report |
| POST | `/api/dialogue/continue` | `{ "session_id" }` |
| POST | `/api/dialogue/end` | `{ "session_id" }` |

TTS: responses include `tts_url` → existing `GET /api/tts?text=...`.

## Dev test

```bash
python -m Spoken_model.rag.build_kb
python -m Spoken_model.dialogue.cli_text_test
```

## Add a scenario

1. Copy `scenarios/restaurant_order/` to `scenarios/your_theme/`.
2. Edit `manifest.json`, `scenario.json`, `rag_filter.json`, `scripts/*.json`.
3. Restart server; scenario appears in `GET /api/dialogue/scenarios`.

## Later hooks

- **ASR**: implement `AsrAdapter` (e.g. Xfyun IAT), pass `audio_b64` in `/api/dialogue/turn`.
