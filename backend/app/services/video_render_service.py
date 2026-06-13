from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LicenseLimits:
    max_total_clip_seconds: float = 0
    max_single_clip_seconds: float = 0
    allow_audio: bool = False
    allow_thumbnail: bool = False
    required_credit: str = ""

    @classmethod
    def from_terms(cls, terms: dict[str, Any] | None) -> "LicenseLimits":
        terms = terms or {}
        return cls(
            max_total_clip_seconds=float(terms.get("max_total_clip_seconds", 0)),
            max_single_clip_seconds=float(terms.get("max_single_clip_seconds", 0)),
            allow_audio=bool(terms.get("allow_audio", False)),
            allow_thumbnail=bool(terms.get("allow_thumbnail", False)),
            required_credit=str(terms.get("required_credit", "")),
        )


async def run_ffmpeg(arguments: list[str]) -> None:
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise RuntimeError("FFmpeg executable was not found")
    process = await asyncio.create_subprocess_exec(
        executable,
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(stderr.decode(errors="replace"))


def validate_source_clips(
    clip_durations: list[float],
    limits: LicenseLimits,
    include_original_audio: bool,
) -> None:
    if any(duration > limits.max_single_clip_seconds for duration in clip_durations):
        raise ValueError("A source clip exceeds max_single_clip_seconds")
    if sum(clip_durations) > limits.max_total_clip_seconds:
        raise ValueError("Source clips exceed max_total_clip_seconds")
    if include_original_audio and not limits.allow_audio:
        raise ValueError("Original audio is not licensed")


async def render_draft(
    output_path: Path,
    subtitle_path: Path | None = None,
    vertical: bool = False,
    duration_seconds: int = 60,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    size = "1080x1920" if vertical else "1920x1080"
    args = [
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=0x111827:s={size}:d={duration_seconds}",
        "-vf",
        "format=yuv420p",
        "-c:v",
        "libx264",
        str(output_path),
    ]
    await run_ffmpeg(args)
    return output_path
