"""
AURA Desktop Agent — Function-Calling Tools
Provides reliable Live2D expression triggers + real desktop assistant actions:
  - set_avatar_expression (built-in Cubism 4 .exp3 actions + procedural expressions)
  - open_app_or_url
  - media_control (play/pause, next/prev, volume)
  - set_reminder (voice-announced timers/reminders)
  - web_search (DuckDuckGo)
  - remember_fact (persistent SQLite memory)
  - get_system_status (CPU, RAM, GPU temp/VRAM, battery)
"""
from __future__ import annotations

import ctypes
import json
import logging
import os
import subprocess
import webbrowser
from datetime import datetime
from typing import Any, Dict, List

import psutil

from memory_store import memory_store

logger = logging.getLogger("aura.tools")

VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
KEYEVENTF_KEYUP = 0x0002

APP_ALIASES: Dict[str, str] = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "explorer": "explorer.exe",
    "files": "explorer.exe",
    "vscode": "code",
    "vs code": "code",
    "spotify": "spotify:",
    "discord": "discord:",
    "steam": "steam:",
    "youtube": "https://www.youtube.com",
    "twitch": "https://www.twitch.tv",
    "github": "https://github.com",
    "google": "https://www.google.com",
}

BUILTIN_LIVE2D_ACTIONS = [
    "SmileLock",
    "SadLock",
    "Angry",
    "Ghost",
    "GhostChange",
    "Shadow",
    "PupilShrink",
    "EyeshineOff",
    "wink",
    "blush",
    "pouting",
    "tongue",
    "pleading",
    "neutral",
]


def _press_vk(vk: int, repeat: int = 1) -> None:
    if os.name != "nt":
        return
    user32 = ctypes.windll.user32
    for _ in range(repeat):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


AVATAR_EXPRESSION_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "set_avatar_expression",
        "description": (
            "Trigger AURA's built-in Live2D model expressions and companion animations. "
            "Built-in .exp3 actions: SmileLock (happy smile), SadLock (sad/worried), Angry (frustrated/scolding), "
            "Ghost (summon spirit prop), GhostChange (nervous spirit prop), Shadow (dramatic forehead shadow), "
            "PupilShrink (shocked/startled pupils), EyeshineOff (deadpan/blank eyes). "
            "Extra facial actions: wink, blush, pouting, tongue, pleading, neutral (reset). "
            "Multiple actions can be combined, e.g. ['Ghost', 'SmileLock'] or ['Shadow', 'EyeshineOff']."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {"type": "string", "enum": BUILTIN_LIVE2D_ACTIONS},
                    "description": "One or more Live2D expression names to activate simultaneously.",
                },
                "duration_sec": {
                    "type": "number",
                    "description": "How long in seconds to hold the expression (default 5.5).",
                },
            },
            "required": ["actions"],
        },
    },
}

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    AVATAR_EXPRESSION_TOOL,
    {
        "type": "function",
        "function": {
            "name": "open_app_or_url",
            "description": "Open a desktop application (notepad, calc, spotify, discord, steam, vscode) or website URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "App name or full https:// URL."}
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "media_control",
            "description": "Control system media playback or volume.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["play_pause", "next", "previous", "volume_up", "volume_down", "mute"],
                    }
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Set a timer or reminder; AURA will announce it aloud when time is up.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Reminder message."},
                    "minutes": {"type": "number", "description": "Delay in minutes."},
                },
                "required": ["text", "minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for live info, documentation, guides, or answers.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query."}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Save an important personal fact, user name, preference, or project detail into local memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "Concise sentence to remember."},
                    "category": {
                        "type": "string",
                        "enum": ["fact", "preference", "game", "joke", "schedule", "milestone"],
                    },
                },
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "Check local system vitals: CPU %, RAM %, GPU temp & VRAM, battery, and local time.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def execute_tool(name: str, arguments: Dict[str, Any]) -> str:
    logger.info(f"Executing tool: {name}({arguments})")
    try:
        if name == "set_avatar_expression":
            raw_actions = arguments.get("actions") or []
            if isinstance(raw_actions, str):
                raw_actions = [raw_actions]
            valid = [a for a in raw_actions if a in BUILTIN_LIVE2D_ACTIONS] or ["SmileLock"]
            dur = max(1.5, min(15.0, float(arguments.get("duration_sec", 5.5))))
            return json.dumps({"ok": True, "actions": valid, "duration_sec": dur})

        if name == "open_app_or_url":
            target = str(arguments.get("target", "")).strip()
            if not target:
                return json.dumps({"ok": False, "error": "Empty target"})
            resolved = APP_ALIASES.get(target.lower(), target)
            if resolved.startswith(("http://", "https://", "spotify:", "discord:", "steam:")):
                webbrowser.open(resolved)
                return json.dumps({"ok": True, "opened": resolved})
            if any(ch in resolved for ch in "&|;><`$\n\r"):
                return json.dumps({"ok": False, "error": "Unsafe characters in target"})
            try:
                os.startfile(resolved)  # type: ignore[attr-defined]
            except Exception:
                subprocess.Popen([resolved], shell=False)
            return json.dumps({"ok": True, "opened": resolved})

        if name == "media_control":
            action = str(arguments.get("action", "")).lower()
            mapping = {
                "play_pause": (VK_MEDIA_PLAY_PAUSE, 1),
                "next": (VK_MEDIA_NEXT_TRACK, 1),
                "previous": (VK_MEDIA_PREV_TRACK, 1),
                "volume_up": (VK_VOLUME_UP, 5),
                "volume_down": (VK_VOLUME_DOWN, 5),
                "mute": (VK_VOLUME_MUTE, 1),
            }
            if action not in mapping:
                return json.dumps({"ok": False, "error": f"Unknown media action: {action}"})
            vk, count = mapping[action]
            _press_vk(vk, count)
            return json.dumps({"ok": True, "action": action})

        if name == "set_reminder":
            text = str(arguments.get("text", "Reminder")).strip()
            minutes = float(arguments.get("minutes", 5))
            rem = memory_store.add_reminder(text, minutes * 60.0)
            return json.dumps({"ok": True, "reminder": rem})

        if name == "web_search":
            query = str(arguments.get("query", "")).strip()
            if not query:
                return json.dumps({"ok": False, "error": "Empty query"})
            try:
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=4))
                compact = [
                    {"title": r.get("title", ""), "snippet": r.get("body", "")[:220], "url": r.get("href", "")}
                    for r in results
                ]
                return json.dumps({"ok": True, "results": compact})
            except Exception as e:
                return json.dumps({"ok": False, "error": f"Search error: {e}"})

        if name == "remember_fact":
            fact = str(arguments.get("fact", "")).strip()
            category = str(arguments.get("category", "fact")).strip()
            mid = memory_store.add_memory(fact, category=category, importance=7)
            return json.dumps({"ok": True, "memory_id": mid, "saved": fact})

        if name == "get_system_status":
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            batt = psutil.sensors_battery()
            gpu_info = "unavailable"
            try:
                out = subprocess.check_output(
                    [
                        "nvidia-smi",
                        "--query-gpu=temperature.gpu,memory.used,memory.total,utilization.gpu",
                        "--format=csv,noheader,nounits",
                    ],
                    timeout=2,
                    text=True,
                ).strip()
                if out:
                    temp, used, total, util = [x.strip() for x in out.split(",")]
                    gpu_info = f"{temp}C, VRAM {used}/{total} MiB, load {util}%"
            except Exception:
                pass
            return json.dumps(
                {
                    "ok": True,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "cpu_percent": cpu,
                    "ram_percent": mem.percent,
                    "gpu": gpu_info,
                    "battery": (
                        f"{batt.percent:.0f}% ({'charging' if batt.power_plugged else 'on battery'})"
                        if batt
                        else "AC / desktop"
                    ),
                }
            )

        return json.dumps({"ok": False, "error": f"Unknown tool: {name}"})
    except Exception as e:
        logger.error(f"Tool '{name}' failed: {e}")
        return json.dumps({"ok": False, "error": str(e)})
