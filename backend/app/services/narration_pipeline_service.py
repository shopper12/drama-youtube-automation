"""Narrated draft assembly with per-segment timing, SRT and source-rights gate."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ..enums import ProductionStatus, RightsStatus
from ..models import VideoProject
from .media_pipeline_service import render_licensed_roughcut, storage_root
from .tts_service import get_tts_provider
from .video_render_service import run_ffmpeg


async def audio_duration(path: Path) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(path), stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode:
        raise RuntimeError(stderr.decode(errors="replace")[:300])
    return float(json.loads(stdout).get("format", {}).get("duration", 0))


def srt_time(seconds: float) -> str:
    ms = round(seconds * 1000)
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


async def synthesize_narration(project: VideoProject, db: AsyncSession) -> Path:
    segments = project.narration_segments or []
    if not segments:
        raise ValueError("Generate a storyboard with narration first")
    directory = storage_root() / str(project.drama_id) / "narration" / str(project.id)
    directory.mkdir(parents=True, exist_ok=True)
    provider = get_tts_provider()
    parts: list[Path] = []
    subtitle_lines: list[str] = []
    cursor = 0.0
    for index, segment in enumerate(segments, start=1):
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        if len(text) > 2400:
            raise ValueError("Narration segment exceeds TTS character limit; split the segment")
        part = directory / f"part_{index:04d}.mp3"
        await provider.synthesize(text, part)
        length = await audio_duration(part)
        if length < 0.1:
            raise RuntimeError("Audio duration invalid")
        subtitle_lines.append(
            f"{index}\n{srt_time(cursor)} --> {srt_time(cursor+length)}\n{text}\n"
        )
        cursor += length
        parts.append(part)
    if not parts:
        raise ValueError("All narration segments were empty")
    files = directory / "parts.txt"
    files.write_text("".join(f"file '{part.name}'\n" for part in parts), encoding="utf-8")
    combined = directory / "voice.mp3"
    await run_ffmpeg(["-y", "-f", "concat", "-safe", "0", "-i", str(files),
                      "-c:a", "libmp3lame", "-q:a", "3", str(combined)])
    srt = directory / "narration.srt"
    srt.write_text("\n".join(subtitle_lines), encoding="utf-8")
    project.tts_file_path = str(combined)
    project.subtitle_file_path = str(srt)
    project.production_status = ProductionStatus.VOICE_READY
    project.drama.production_status = ProductionStatus.VOICE_READY
    await db.flush()
    return combined


async def assemble_narrated_draft(project: VideoProject, db: AsyncSession,
                                  budget_seconds: float = 360) -> Path:
    voice = Path(project.tts_file_path or "")
    if not voice.is_file() or voice.stat().st_size < 512:
        raise ValueError("Generate a valid TTS narration first")
    directory = storage_root() / str(project.drama_id) / "renders"
    directory.mkdir(parents=True, exist_ok=True)
    out = directory / f"narrated-{project.id}.mp4"
    drama = project.drama
    source_rights = (drama.rights_status == RightsStatus.APPROVED and
                     drama.human_review_approved and not drama.license_expired and
                     drama.source_rights_check)
    if source_rights:
        visual = await render_licensed_roughcut(project, db, budget_seconds)
        inputs = ["-stream_loop", "-1", "-i", str(visual), "-i", str(voice)]
    else:
        # This preview contains no source clips, images or original audio.
        inputs = ["-f", "lavfi", "-i", "color=c=0x111827:s=1280x720:r=25",
                  "-i", str(voice)]
    subtitle = Path(project.subtitle_file_path or "")
    vf = "format=yuv420p"
    if subtitle.is_file():
        escaped = subtitle.resolve().as_posix().replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        vf = f"subtitles='{escaped}',format=yuv420p"
    await run_ffmpeg(["-y", *inputs, "-map", "0:v:0", "-map", "1:a:0",
                      "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
                      "-c:a", "aac", "-b:a", "128k", "-shortest", str(out)])
    project.render_main_path = str(out)
    project.production_status = ProductionStatus.VIDEO_DRAFT_READY
    drama.production_status = ProductionStatus.VIDEO_DRAFT_READY
    await db.flush()
    return out
