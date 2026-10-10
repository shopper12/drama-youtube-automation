"""Real TTS adapters. Draft mode intentionally fails instead of writing an empty MP3."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

import httpx


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, output_path: Path) -> Path:
        raise NotImplementedError


async def _save_audio(response: httpx.Response, path: Path) -> Path:
    response.raise_for_status()
    if not response.headers.get("content-type", "").lower().startswith(("audio/", "application/octet-stream")):
        raise RuntimeError("TTS returned non-audio content")
    if len(response.content) < 512:
        raise RuntimeError("TTS returned an empty or invalid audio file")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return path


class ElevenLabsTTSProvider(TTSProvider):
    async def synthesize(self, text: str, output_path: Path) -> Path:
        key = os.getenv("ELEVENLABS_API_KEY")
        voice = os.getenv("ELEVENLABS_VOICE_ID")
        if not key or not voice:
            raise RuntimeError("ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID required")
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                headers={"xi-api-key": key, "Content-Type": "application/json"},
                params={"output_format": "mp3_44100_128"},
                json={"text": text, "model_id": os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")},
            )
        return await _save_audio(response, output_path)


class ClovaTTSProvider(TTSProvider):
    async def synthesize(self, text: str, output_path: Path) -> Path:
        client_id = os.getenv("CLOVA_CLIENT_ID")
        client_secret = os.getenv("CLOVA_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise RuntimeError("CLOVA_CLIENT_ID and CLOVA_CLIENT_SECRET required")
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts",
                headers={"X-NCP-APIGW-API-KEY-ID": client_id,
                         "X-NCP-APIGW-API-KEY": client_secret},
                data={"speaker": os.getenv("CLOVA_VOICE", "nara"),
                      "text": text, "volume": "0", "speed": "0",
                      "pitch": "0", "format": "mp3"},
            )
        return await _save_audio(response, output_path)


class DraftTTSProvider(TTSProvider):
    async def synthesize(self, text: str, output_path: Path) -> Path:
        raise RuntimeError("TTS_PROVIDER=draft does not generate audio; configure elevenlabs or clova")


def get_tts_provider() -> TTSProvider:
    provider = os.getenv("TTS_PROVIDER", "draft").lower()
    if provider == "elevenlabs":
        return ElevenLabsTTSProvider()
    if provider == "clova":
        return ClovaTTSProvider()
    if provider == "draft":
        return DraftTTSProvider()
    raise ValueError(f"Unsupported TTS_PROVIDER: {provider}")
