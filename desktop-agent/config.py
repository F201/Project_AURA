"""
AURA Desktop Agent — Runtime Configuration & Privacy Guardrails
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
from dotenv import load_dotenv

AGENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AGENT_DIR.parent
VOICE_AGENT_DIR = PROJECT_ROOT / "voice-agent"
ENV_PATH = PROJECT_ROOT / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

DEFAULT_SENSITIVE_KEYWORDS = [
    "1password",
    "bitwarden",
    "keepass",
    "lastpass",
    "dashlane",
    "nordpass",
    "proton pass",
    "windows security",
    "credential",
    "password",
    "sign in",
    "log in",
    "login",
    "incognito",
    "inprivate",
    "private browsing",
    "bank",
    "paypal",
    "stripe",
    "metamask",
    "phantom",
    "coinbase",
    "binance",
    "authenticator",
    "authy",
    "otp",
    "recovery phrase",
    "seed phrase",
    ".env",
]

KNOWN_GAMES = {
    "genshinimpact.exe": "Genshin Impact",
    "starrail.exe": "Honkai: Star Rail",
    "zenlesszonezero.exe": "Zenless Zone Zero",
    "valorant-win64-shipping.exe": "VALORANT",
    "valorant.exe": "VALORANT",
    "league of legends.exe": "League of Legends",
    "cs2.exe": "Counter-Strike 2",
    "dota2.exe": "Dota 2",
    "eldenring.exe": "Elden Ring",
    "cyberpunk2077.exe": "Cyberpunk 2077",
    "r5apex.exe": "Apex Legends",
    "overwatch.exe": "Overwatch 2",
    "minecraft.exe": "Minecraft",
    "javaw.exe": "Minecraft / Java Game",
    "osu!.exe": "osu!",
    "wuthering waves.exe": "Wuthering Waves",
    "bg3.exe": "Baldur's Gate 3",
    "bg3_dx11.exe": "Baldur's Gate 3",
    "helldivers2.exe": "Helldivers 2",
    "marvel-win64-shipping.exe": "Marvel Rivals",
    "fortniteclient-win64-shipping.exe": "Fortnite",
    "gta5.exe": "GTA V",
    "witcher3.exe": "The Witcher 3",
    "hades2.exe": "Hades II",
    "hollow_knight.exe": "Hollow Knight",
    "celeste.exe": "Celeste",
    "terraria.exe": "Terraria",
    "stardew valley.exe": "Stardew Valley",
    "repo.exe": "R.E.P.O.",
    "lethal company.exe": "Lethal Company",
    "phasmophobia.exe": "Phasmophobia",
}


@dataclass
class Settings:
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    llm_model: str = field(
        default_factory=lambda: os.getenv("DESKTOP_LLM_MODEL", os.getenv("DEFAULT_LLM_MODEL", "deepseek/deepseek-v4-flash"))
    )
    host: str = field(default_factory=lambda: os.getenv("DESKTOP_AGENT_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("DESKTOP_AGENT_PORT", "8765")))

    tts_model: str = field(default_factory=lambda: os.getenv("TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-Base"))
    tts_voice_ref: str = field(
        default_factory=lambda: os.getenv(
            "DESKTOP_TTS_VOICE_REF",
            str(VOICE_AGENT_DIR / "resources" / "voice" / "aura_voice_xvec.pt"),
        )
    )
    tts_chunk_size: int = field(default_factory=lambda: int(os.getenv("TTS_CHUNK_SIZE", "6")))
    tts_language: str = field(default_factory=lambda: os.getenv("TTS_LANGUAGE", "English"))
    tts_warmup: bool = field(default_factory=lambda: os.getenv("TTS_WARMUP", "true").lower() == "true")
    remote_tts_url: str = field(default_factory=lambda: os.getenv("DESKTOP_REMOTE_TTS_URL", "").strip().rstrip("/"))

    stt_model: str = field(default_factory=lambda: os.getenv("STT_MODEL", "base"))
    stt_language: str = field(default_factory=lambda: os.getenv("STT_LANGUAGE", "en"))
    stt_device: str = field(default_factory=lambda: os.getenv("STT_DEVICE", "cpu"))
    stt_compute_type: str = field(default_factory=lambda: os.getenv("STT_COMPUTE_TYPE", "int8"))

    vision_enabled: bool = field(default_factory=lambda: os.getenv("VISION_ENABLED", "true").lower() == "true")
    vision_interval_sec: float = field(default_factory=lambda: float(os.getenv("VISION_INTERVAL_SEC", "8")))
    typing_watcher_enabled: bool = field(default_factory=lambda: os.getenv("TYPING_WATCHER_ENABLED", "true").lower() == "true")
    proactive_enabled: bool = field(default_factory=lambda: os.getenv("PROACTIVE_ENABLED", "true").lower() == "true")
    proactive_cooldown_sec: float = field(default_factory=lambda: float(os.getenv("PROACTIVE_COOLDOWN_SEC", "180")))

    user_name: str = field(default_factory=lambda: os.getenv("USER_NAME", "Friend"))

    @property
    def voice_ref_path(self) -> Path:
        p = Path(self.tts_voice_ref)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p


@dataclass
class RuntimeState:
    mic_muted: bool = False
    mic_mode: str = "always"  # "always" | "wake" ("AURA")
    blind_mode: bool = False
    game_mode: bool = False
    proactive_enabled: bool = True
    vision_enabled: bool = True
    typing_watcher_enabled: bool = True
    privacy_paused: bool = False
    privacy_reason: str = ""
    tts_backend: str = "loading"  # "qwen3" | "remote" | "edge" | "loading" | "off"
    tts_error: str = ""
    tts_ready: bool = False
    stt_ready: bool = False
    is_speaking: bool = False
    client_playing: bool = False
    is_listening: bool = False
    is_thinking: bool = False
    active_window: str = ""
    active_process: str = ""
    detected_game: str = ""
    tts_chunk_size: int = 6
    tts_voice_file: str = "aura_voice_xvec.pt"
    tts_language: str = "English"
    proactive_cooldown_sec: float = 180.0
    sensitive_keywords: List[str] = field(default_factory=lambda: list(DEFAULT_SENSITIVE_KEYWORDS))

    def to_dict(self) -> dict:
        return {
            "mic_muted": self.mic_muted,
            "mic_mode": self.mic_mode,
            "blind_mode": self.blind_mode,
            "game_mode": self.game_mode,
            "proactive_enabled": self.proactive_enabled,
            "vision_enabled": self.vision_enabled,
            "typing_watcher_enabled": self.typing_watcher_enabled,
            "privacy_paused": self.privacy_paused,
            "privacy_reason": self.privacy_reason,
            "tts_backend": self.tts_backend,
            "tts_error": self.tts_error,
            "tts_ready": self.tts_ready,
            "stt_ready": self.stt_ready,
            "is_speaking": self.is_speaking,
            "is_listening": self.is_listening,
            "is_thinking": self.is_thinking,
            "active_window": self.active_window,
            "active_process": self.active_process,
            "detected_game": self.detected_game,
            "tts_chunk_size": self.tts_chunk_size,
            "tts_voice_file": self.tts_voice_file,
            "tts_language": self.tts_language,
            "proactive_cooldown_sec": self.proactive_cooldown_sec,
        }


settings = Settings()
runtime = RuntimeState(
    proactive_enabled=settings.proactive_enabled,
    vision_enabled=settings.vision_enabled,
    typing_watcher_enabled=settings.typing_watcher_enabled,
    tts_chunk_size=settings.tts_chunk_size,
    tts_voice_file=settings.voice_ref_path.name,
    tts_language=settings.tts_language,
    proactive_cooldown_sec=settings.proactive_cooldown_sec,
)
