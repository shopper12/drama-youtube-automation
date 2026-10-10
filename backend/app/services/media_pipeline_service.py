"""User-supplied episode ingest, reviewable timelines and licensed rough-cut preview."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal
from ..enums import ProductionStatus, RightsStatus
from ..models import Drama, SourceVideo, VideoProject
from .scene_analyzer_service import GeminiVideoAnalyzer, select_highlights
from .video_render_service import LicenseLimits, run_ffmpeg, validate_source_clips

CHUNK_SIZE = 1024 * 1024
SUPPORTED = {".mp4", ".mov", ".m4v", ".webm"}


def storage_root() -> Path:
    return Path(os.getenv("MEDIA_STORAGE_ROOT", "./storage/drama_media")).resolve()


async def probe_video(path: Path) -> float:
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe executable not found")
    process = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name", "-show_entries", "format=duration",
        "-of", "json", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await process.communicate()
    if process.returncode:
        raise ValueError("Invalid video: " + err.decode(errors="replace")[:300])
    info = json.loads(out)
    if not info.get("streams"):
        raise ValueError("No video stream detected")
    duration = float(info.get("format", {}).get("duration", 0))
    if not 1 <= duration <= 3 * 60 * 60:
        raise ValueError("Video duration must be 1 second to 3 hours")
    return duration


async def save_video(drama_id: int, episode_number: int, upload: UploadFile,
                     analysis_authorized: bool, db: AsyncSession) -> SourceVideo:
    if episode_number < 1:
        raise ValueError("episode_number must be positive")
    if not analysis_authorized:
        raise PermissionError("Confirm authorization to process this source with Gemini")
    drama = await db.get(Drama, drama_id)
    if drama is None:
        raise LookupError("Drama not found")
    original = Path(upload.filename or "").name
    extension = Path(original).suffix.lower()
    if extension not in SUPPORTED:
        raise ValueError("Accepted media: MP4, MOV, M4V, WEBM")
    folder = storage_root() / str(drama_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid4().hex}{extension}"
    size_limit = int(os.getenv("MAX_MEDIA_UPLOAD_BYTES", str(2 * 1024 ** 3)))
    digest = hashlib.sha256()
    length = 0
    try:
        with path.open("xb") as dest:
            while chunk := await upload.read(CHUNK_SIZE):
                length += len(chunk)
                if length > size_limit:
                    raise ValueError("Upload exceeds MAX_MEDIA_UPLOAD_BYTES")
                dest.write(chunk)
                digest.update(chunk)
        if length < 1024:
            raise ValueError("Uploaded video is too small")
        duration = await probe_video(path)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    source = SourceVideo(
        drama_id=drama_id, episode_number=episode_number,
        original_filename=original[:255], stored_path=str(path),
        sha256=digest.hexdigest(), duration_seconds=duration,
        status="QUEUED" if os.getenv("AUTO_ANALYZE_ON_UPLOAD", "false").lower() == "true" else "UPLOADED",
        analysis_authorized=True,
    )
    db.add(source)
    await db.flush()
    return source


async def analyze_source_job(source_id: int) -> None:
    """Safe to rerun after worker restart; failures remain inspectable in database."""
    async with AsyncSessionLocal() as db:
        source = await db.get(SourceVideo, source_id)
        if source is None or source.status not in ("UPLOADED", "QUEUED", "FAILED"):
            return
        if not source.analysis_authorized:
            source.status, source.error_message = "FAILED", "Source analysis was not authorized"
            await db.commit()
            return
        source.status, source.error_message = "PROCESSING", None
        await db.commit()

    try:
        # No silent fallback: missing API credentials must be reported, not fabricated.
        scenes = await GeminiVideoAnalyzer().analyze(
            Path(source.stored_path), source.duration_seconds,
            source.id, source.episode_number,
        )
        async with AsyncSessionLocal() as db:
            source = await db.get(SourceVideo, source_id)
            if source is None:
                return
            source.analysis_result = {"scenes": scenes, "analyzer": "gemini", "human_reviewed": False}
            source.status = "ANALYZED"
            project = (await db.scalars(
                select(VideoProject).where(VideoProject.drama_id == source.drama_id).order_by(VideoProject.id)
            )).first()
            if project is None:
                project = VideoProject(drama_id=source.drama_id)
                db.add(project)
            # Re-analysis replaces this source's scenes rather than duplicating them.
            existing = [s for s in (project.scene_plan or []) if s.get("source_id") != source.id]
            project.scene_plan = sorted(existing + scenes,
                key=lambda s: (int(s["episode_number"]), float(s["start_seconds"])))
            if os.getenv("AUTO_BUILD_STORYBOARD", "true").lower() == "true":
                await prepare_storyboard(project, db)
            await db.commit()
    except Exception as exc:
        async with AsyncSessionLocal() as db:
            source = await db.get(SourceVideo, source_id)
            if source:
                source.status = "FAILED"
                source.error_message = f"{type(exc).__name__}: {exc}"[:1000]
                await db.commit()


async def prepare_storyboard(project: VideoProject, db: AsyncSession, budget_seconds: float = 360) -> dict:
    scenes = select_highlights(project.scene_plan or [], budget_seconds)
    if not scenes:
        raise ValueError("No verified source scenes are available. Analyze episodes first.")
    # Factual event recap only; no generic hallucinated reversal/villain template.
    lines = [f"{s['episode_number']}화: {s['event']}" for s in scenes]
    project.script = "\n\n".join(lines)
    project.narration_segments = [
        {"index": i + 1, "text": line, "scene_source_id": s["source_id"],
         "start_seconds": s["start_seconds"], "end_seconds": s["end_seconds"]}
        for i, (s, line) in enumerate(zip(scenes, lines))
    ]
    project.title_candidates = [f"{project.drama.title} 줄거리 몰아보기 | 중요 사건 정리"]
    project.production_status = ProductionStatus.SCRIPT_READY
    project.drama.production_status = ProductionStatus.SCRIPT_READY
    await db.flush()
    return {"project_id": project.id, "selected_scenes": scenes,
            "script": project.script, "review_required": True}


async def render_licensed_roughcut(project: VideoProject, db: AsyncSession,
                                  budget_seconds: float = 360) -> Path:
    """Produces a muted, licensed visual rough cut; not a finished narrated summary."""
    drama = project.drama
    if drama.rights_status != RightsStatus.APPROVED or not drama.human_review_approved or drama.license_expired:
        raise PermissionError("License and human approval required before source-clip rendering")
    if not drama.source_rights_check:
        raise PermissionError("Source rights check has not passed")
    limits = LicenseLimits.from_terms(drama.license_terms)
    chosen = select_highlights(project.scene_plan or [], min(budget_seconds, limits.max_total_clip_seconds))
    if not chosen:
        raise ValueError("No clips selected or license clip budget is zero")
    durations = [float(s["end_seconds"])-float(s["start_seconds"]) for s in chosen]
    validate_source_clips(durations, limits, include_original_audio=False)
    sources = {s.id: s for s in (await db.scalars(
        select(SourceVideo).where(SourceVideo.drama_id == drama.id)
    )).all()}
    folder = storage_root() / str(drama.id) / "renders"
    folder.mkdir(parents=True, exist_ok=True)
    result = folder / f"roughcut-{project.id}.mp4"
    with tempfile.TemporaryDirectory(dir=folder) as tmp:
        temp = Path(tmp)
        cuts: list[Path] = []
        for i, scene in enumerate(chosen):
            source = sources.get(int(scene["source_id"]))
            if source is None or source.status != "ANALYZED":
                raise ValueError("Referenced source was removed or is not analyzed")
            # Guard the stored path against manifest tampering.
            if Path(source.stored_path).resolve().parent != (storage_root() / str(drama.id)).resolve():
                raise PermissionError("Media source escaped project storage")
            cut = temp / f"{i:04d}.mp4"
            await run_ffmpeg([
                "-y", "-ss", str(scene["start_seconds"]),
                "-i", source.stored_path, "-t", str(durations[i]),
                "-an", "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
                "pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                "-r", "25", "-c:v", "libx264", "-preset", "veryfast", str(cut),
            ])
            cuts.append(cut)
        listfile = temp / "concat.txt"
        listfile.write_text("".join(f"file '{c.as_posix()}'\n" for c in cuts), encoding="utf-8")
        await run_ffmpeg(["-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
                          "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(result)])
    project.render_main_path = str(result)
    project.production_status = ProductionStatus.VIDEO_DRAFT_READY
    drama.production_status = ProductionStatus.VIDEO_DRAFT_READY
    await db.flush()
    return result
