from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, output_path: Path) -> Path:
        raise NotImplementedError


class ElevenLabsTTSProvider(TTSProvider):
    async def synthesize(self, text: str, output_path: Path) -> Path:
        raise NotImplementedError("Configure ElevenLabs adapter credentials")


class ClovaTTSProvider(TTSProvider):
    async def synthesize(self, text: str, output_path: Path) -> Path:
        raise NotImplementedError("Configure Clova adapter credentials")


class EdgeTTSProvider(TTSProvider):
    def __init__(self, voice: str | None = None):
        self.voice = voice or os.getenv("EDGE_TTS_VOICE", "ko-KR-SunHiNeural")

    async def synthesize(self, text: str, output_path: Path) -> Path:
        try:
            import edge_tts
        except ImportError as error:
            raise RuntimeError(
                "Install edge-tts or choose TTS_PROVIDER=draft"
            ) from error
        output_path.parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(str(output_path))
        return output_path


class DraftTTSProvider(TTSProvider):
    async def synthesize(self, text: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"")
        return output_path


def get_tts_provider() -> TTSProvider:
    provider = os.getenv("TTS_PROVIDER", "draft").lower()
    if provider in {"edge", "edge-tts"}:
        return EdgeTTSProvider()
    if provider == "elevenlabs":
        return ElevenLabsTTSProvider()
    if provider == "clova":
        return ClovaTTSProvider()
    return DraftTTSProvider()
