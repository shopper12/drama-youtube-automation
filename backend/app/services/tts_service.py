from __future__ import annotations

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


class DraftTTSProvider(TTSProvider):
    async def synthesize(self, text: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"")
        return output_path
