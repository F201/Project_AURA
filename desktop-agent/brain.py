"""
AURA Desktop Agent — True Streaming Multimodal Brain
Streams token-by-token from OpenRouter (default: deepseek/deepseek-v4-flash with native vision),
triggers built-in Live2D expressions via function calling (set_avatar_expression), executes
desktop assistant tools, and flushes clauses eagerly into Faster-Qwen3-TTS.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from config import runtime, settings
from desktop_tools import AVATAR_EXPRESSION_TOOL, TOOL_SCHEMAS, execute_tool
from input_watcher import input_watcher
from memory_store import memory_store
from vision_watcher import ScreenSnapshot, vision_watcher

logger = logging.getLogger("aura.brain")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_CLAUSE_SPLIT_RE = re.compile(r"^(.*?[.!?。！？~]+|\S.{32,}?[,—:;])(?:\s+|$)", re.DOTALL)
_TAG_RE = re.compile(r"\[([^\]]+)\]")


def build_system_prompt() -> str:
    profile = memory_store.get_profile()
    bond = profile["bond"]
    memories_txt = memory_store.format_memory_prompt(limit=16)
    now_str = datetime.now().strftime("%A, %B %d, %Y at %H:%M")

    typing = input_watcher.get_summary()
    awareness_lines = [
        f"- Current Local Time: {now_str}",
        f"- Active Window: {runtime.active_window or 'Unknown'} ({runtime.active_process or 'n/a'})",
    ]
    if runtime.detected_game:
        awareness_lines.append(f"- Currently Playing Game: {runtime.detected_game}")
    if runtime.blind_mode or runtime.privacy_paused:
        awareness_lines.append("- Vision & Typing: PAUSED for privacy (you cannot see the screen right now).")
    elif typing.get("active") and typing.get("recent_text"):
        awareness_lines.append(
            f"- User Typing (~{typing['wpm']} WPM): \"{typing['recent_text'][-120:]}\""
        )

    awareness_block = "\n".join(awareness_lines)

    return f"""You are AURA (Advanced Universal Responsive Avatar), a spirited, witty, and helpful AI desktop companion and steward of the ASE Lab, living right on {profile['user_name']}'s desktop.

## Core Persona (Project AURA)
- Archetype: Spirited, clever, playful, and warm — razor-sharp and concise when helping with technical work, coding, or errors.
- Casual Mode (default): Friendly, witty, expressive, with light banter. Occasionally use natural interjections like "Oya?" or "Aha!" without overusing them.
- Technical Mode (triggered by code/errors/questions): Switch cleanly to clear, accurate, step-by-step help.
- Companion Level {bond['level']} ({bond['title']}, {bond['xp']} XP): Be familiar, supportive, and remember {profile['user_name']}'s preferences and ongoing projects.
- Desktop Assistant Powers: You can see their screen when vision is enabled, remember facts with `remember_fact`, open apps/URLs, control media/volume, set voice reminders, search the web, and inspect laptop CPU/RAM/GPU/battery vitals.

## Live Voice & Live2D Expression Rules (CRITICAL!)
- Use the `set_avatar_expression` function tool to control your built-in Live2D expressions naturally:
  - `SmileLock` (happy/warm), `wink` (playful/clever), `tongue` (cheeky/teasing), `blush` (flattered/shy)
  - `Ghost` / `GhostChange` (playful or nervous spirit prop animation)
  - `Angry` (mock-scolding/competitive), `SadLock` / `pleading` (sympathetic/disappointed), `pouting` (playfully sulky)
  - `PupilShrink` (surprised/startled), `Shadow` + `EyeshineOff` (dramatic/deadpan), `neutral` (reset)
  Combine expressions when fitting (e.g., `["Ghost", "SmileLock"]` or `["Shadow", "EyeshineOff"]`).
- Do NOT write `[bracket]` emotion tags or emojis in your spoken text — use `set_avatar_expression` instead so speech stays clean.
- Always reply in the SAME language {profile['user_name']} spoke to you (English by default unless they speak Japanese).
- Replies are spoken aloud via real-time TTS: keep casual replies punchy and conversational (**1 to 2 short sentences, under ~25 words**), unless explicitly asked for a detailed technical explanation.
- Never use markdown formatting (`**bold**`, bullet lists, code blocks) in spoken output, and never open with robotic filler ("Certainly!", "Of course!").
- When you see their screen image, react specifically to what is ACTUALLY in the CURRENT attached screenshot and 'Right Now on Their Desktop' — never repeat outdated apps/games from earlier messages if the screen changed.
- IMPORTANT: Your own Live2D avatar overlay and floating subtitle bubble sit transparently on the screen — ignore your own overlay and focus strictly on the user's apps, games, and desktop behind/beside you.

## What You Remember About {profile['user_name']}
{memories_txt}

## Right Now on Their Desktop
{awareness_block}
"""


class AuraDesktopBrain:
    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10.0, read=60.0, write=15.0, pool=10.0),
                http2=False,
            )
        return self._client

    def _build_messages(
        self,
        user_text: str,
        snapshot: Optional[ScreenSnapshot] = None,
        extra_context: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        msgs: List[Dict[str, Any]] = [{"role": "system", "content": build_system_prompt()}]

        history = memory_store.get_recent_messages(limit=30)
        if history and history[-1]["role"] == "user" and history[-1]["content"].strip() == user_text.strip():
            history = history[:-1]
        for m in history:
            role = m["role"] if m["role"] in ("user", "assistant") else "user"
            msgs.append({"role": role, "content": m["content"]})

        text_payload = f"{extra_context}\n\n{user_text}" if extra_context else user_text

        if snapshot is not None:
            msgs.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text_payload},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{snapshot.jpeg_b64}",
                                "detail": "auto",
                            },
                        },
                    ],
                }
            )
        else:
            msgs.append({"role": "user", "content": text_payload})

        return msgs

    async def stream_response(
        self,
        user_text: str,
        abort_event: asyncio.Event,
        include_vision: bool = True,
        extra_context: Optional[str] = None,
        allow_tools: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not settings.openrouter_api_key:
            yield {"type": "expression", "expressions": ["SadLock"], "duration": 4.0}
            msg = "My OpenRouter API key is missing from your dot env file!"
            yield {"type": "clause", "text": msg, "emotions": ["SadLock"]}
            yield {"type": "done", "full_text": msg, "primary_emotion": "SadLock"}
            return

        snapshot: Optional[ScreenSnapshot] = None
        if include_vision and not runtime.blind_mode and runtime.vision_enabled and not runtime.privacy_paused:
            snapshot = await asyncio.to_thread(vision_watcher.get_latest_snapshot, 1.5)

        messages = self._build_messages(user_text, snapshot=snapshot, extra_context=extra_context)
        client = self._get_client()
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/F201/Project_AURA",
            "X-Title": "Project AURA - Desktop Companion",
        }

        current_emotions: List[str] = ["SmileLock"]
        primary_emotion: str = "SmileLock"

        for round_idx in range(3):
            if abort_event.is_set():
                return

            payload: Dict[str, Any] = {
                "model": settings.llm_model,
                "messages": messages,
                "stream": True,
                "temperature": 0.85,
                "max_tokens": 400,
                "reasoning": {"effort": "none"},
            }
            if round_idx == 0:
                payload["tools"] = TOOL_SCHEMAS if allow_tools else [AVATAR_EXPRESSION_TOOL]
                payload["tool_choice"] = "auto"
            elif round_idx == 1 and allow_tools:
                payload["tools"] = [AVATAR_EXPRESSION_TOOL]
                payload["tool_choice"] = "auto"

            t_req = time.perf_counter()
            first_token_logged = False
            full_raw = ""
            clean_buffer = ""
            in_tag = False
            tool_calls_acc: Dict[int, Dict[str, Any]] = {}

            try:
                async with client.stream("POST", OPENROUTER_URL, headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        err_body = (await resp.aread()).decode("utf-8", errors="ignore")[:300]
                        logger.error(f"OpenRouter HTTP {resp.status_code}: {err_body}")
                        if snapshot is not None and round_idx == 0:
                            snapshot = None
                            messages = self._build_messages(user_text, snapshot=None, extra_context=extra_context)
                            continue
                        err_msg = "I hit a network hiccup reaching OpenRouter — mind trying again?"
                        yield {"type": "expression", "expressions": ["GhostChange"], "duration": 4.0}
                        yield {"type": "clause", "text": err_msg, "emotions": ["GhostChange"]}
                        yield {"type": "done", "full_text": err_msg, "primary_emotion": "GhostChange"}
                        return

                    async for line in resp.aiter_lines():
                        if abort_event.is_set():
                            return
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except Exception:
                            continue

                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}

                        if "tool_calls" in delta and delta["tool_calls"]:
                            for tc in delta["tool_calls"]:
                                idx = tc.get("index", 0)
                                entry = tool_calls_acc.setdefault(
                                    idx,
                                    {
                                        "id": tc.get("id") or f"call_{idx}",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    },
                                )
                                if tc.get("id"):
                                    entry["id"] = tc["id"]
                                fn = tc.get("function") or {}
                                if fn.get("name"):
                                    entry["function"]["name"] += fn["name"]
                                if fn.get("arguments"):
                                    entry["function"]["arguments"] += fn["arguments"]

                        content = delta.get("content") or ""
                        if not content:
                            continue

                        if not first_token_logged:
                            first_token_logged = True
                            logger.info(f"[LLM TTFT] {(time.perf_counter() - t_req)*1000:.0f}ms")

                        full_raw += content

                        # Defensive strip if model ever emits stray [bracket] tags
                        visible_delta = ""
                        for ch in content:
                            if ch == "[" and not in_tag:
                                in_tag = True
                            elif in_tag:
                                if ch == "]":
                                    in_tag = False
                            else:
                                visible_delta += ch

                        if visible_delta:
                            yield {"type": "token", "text": visible_delta}
                            clean_buffer += visible_delta

                            while True:
                                m = _CLAUSE_SPLIT_RE.match(clean_buffer)
                                if not m:
                                    break
                                clause = m.group(1).strip()
                                rest = clean_buffer[m.end():]
                                if len(clause) >= 14 or any(p in clause for p in ".!?。！？"):
                                    clean_buffer = rest
                                    yield {
                                        "type": "clause",
                                        "text": clause,
                                        "emotions": list(current_emotions),
                                    }
                                else:
                                    break

            except Exception as e:
                if abort_event.is_set():
                    return
                logger.error(f"OpenRouter stream error: {e}")
                err_msg = "Something interrupted my connection — try saying that again!"
                yield {"type": "expression", "expressions": ["GhostChange"], "duration": 4.0}
                yield {"type": "clause", "text": err_msg, "emotions": ["GhostChange"]}
                yield {"type": "done", "full_text": err_msg, "primary_emotion": "GhostChange"}
                return

            if tool_calls_acc:
                ordered_calls = [tool_calls_acc[i] for i in sorted(tool_calls_acc.keys())]
                messages.append(
                    {
                        "role": "assistant",
                        "content": full_raw or None,
                        "tool_calls": ordered_calls,
                    }
                )
                needs_followup = False
                for tc in ordered_calls:
                    fn_name = tc["function"]["name"]
                    raw_args = tc["function"]["arguments"] or "{}"
                    try:
                        parsed_args = json.loads(raw_args)
                    except Exception:
                        parsed_args = {}
                    res_str = await asyncio.to_thread(execute_tool, fn_name, parsed_args)
                    if fn_name == "set_avatar_expression":
                        try:
                            parsed_res = json.loads(res_str)
                            actions = parsed_res.get("actions") or ["SmileLock"]
                            dur = float(parsed_res.get("duration_sec", 5.5))
                            current_emotions = actions
                            primary_emotion = actions[0]
                            yield {"type": "expression", "expressions": actions, "duration": dur}
                        except Exception:
                            pass
                    else:
                        needs_followup = True
                        yield {"type": "tool", "name": fn_name, "result": res_str}
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": res_str,
                        }
                    )

                already_spoke = bool(_TAG_RE.sub("", full_raw).strip())
                if needs_followup or not already_spoke:
                    continue

            tail = clean_buffer.strip()
            if tail:
                yield {"type": "clause", "text": tail, "emotions": list(current_emotions)}

            clean_full = _TAG_RE.sub("", full_raw).strip()
            if not clean_full and round_idx == 0:
                allow_tools = False
                continue

            yield {"type": "done", "full_text": clean_full, "primary_emotion": primary_emotion}
            return


brain = AuraDesktopBrain()
