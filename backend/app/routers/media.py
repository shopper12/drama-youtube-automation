"""Admin-authenticated episode upload, scene review and storyboard API."""
from __future__ import annotations

import os
import secrets
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import SourceVideo, VideoProject
from ..services.media_pipeline_service import (
    analyze_source_job, prepare_storyboard, render_licensed_roughcut, save_video,
)

router = APIRouter(prefix="/media", tags=["media"])


def require_media_admin(x_media_admin_token: Annotated[str | None, Header()] = None) -> None:
    expected = os.getenv("MEDIA_ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(503, "MEDIA_ADMIN_TOKEN must be configured on the server")
    if not x_media_admin_token or not secrets.compare_digest(x_media_admin_token, expected):
        raise HTTPException(401, "Invalid media admin token")


def present_source(source: SourceVideo) -> dict:
    return {
        "id": source.id, "drama_id": source.drama_id,
        "episode_number": source.episode_number,
        "filename": source.original_filename, "sha256": source.sha256,
        "duration_seconds": source.duration_seconds, "status": source.status,
        "analysis_result": source.analysis_result,
        "error_message": source.error_message,
    }


async def get_project(project_id: int, db: AsyncSession) -> VideoProject:
    project = await db.scalar(
        select(VideoProject).where(VideoProject.id == project_id).options(selectinload(VideoProject.drama))
    )
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


@router.post("/dramas/{drama_id}/sources", dependencies=[Depends(require_media_admin)])
async def upload_source(
    drama_id: int, background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    episode_number: int = Form(...),
    analysis_authorized: bool = Form(False),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        source = await save_video(drama_id, episode_number, file, analysis_authorized, db)
        await db.commit()
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if source.status == "QUEUED":
        background_tasks.add_task(analyze_source_job, source.id)
    return present_source(source)


@router.get("/dramas/{drama_id}/sources", dependencies=[Depends(require_media_admin)])
async def list_sources(drama_id: int, db: AsyncSession = Depends(get_db)) -> list[dict]:
    sources = (await db.scalars(
        select(SourceVideo).where(SourceVideo.drama_id == drama_id)
        .order_by(SourceVideo.episode_number, SourceVideo.id)
    )).all()
    return [present_source(source) for source in sources]


@router.post("/sources/{source_id}/analyze", dependencies=[Depends(require_media_admin)])
async def analyze_source(
    source_id: int, background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    source = await db.get(SourceVideo, source_id)
    if source is None:
        raise HTTPException(404, "Source not found")
    if source.status == "PROCESSING":
        raise HTTPException(409, "Analysis is already running")
    if not source.analysis_authorized:
        raise HTTPException(403, "Analysis has not been authorized")
    source.status = "QUEUED"
    source.error_message = None
    await db.commit()
    background_tasks.add_task(analyze_source_job, source.id)
    return {"source_id": source.id, "status": "QUEUED"}


@router.get("/sources/{source_id}", dependencies=[Depends(require_media_admin)])
async def source_status(source_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    source = await db.get(SourceVideo, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    return present_source(source)


class PlanRequest(BaseModel):
    seconds_budget: float = Field(default=360, ge=30, le=3600)


@router.post("/projects/{project_id}/storyboard", dependencies=[Depends(require_media_admin)])
async def storyboard(project_id: int, payload: PlanRequest,
                     db: AsyncSession = Depends(get_db)) -> dict:
    project = await get_project(project_id, db)
    try:
        result = await prepare_storyboard(project, db, payload.seconds_budget)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await db.commit()
    return result


@router.post("/projects/{project_id}/roughcut", dependencies=[Depends(require_media_admin)])
async def roughcut(project_id: int, payload: PlanRequest,
                   db: AsyncSession = Depends(get_db)) -> dict:
    project = await get_project(project_id, db)
    try:
        file = await render_licensed_roughcut(project, db, payload.seconds_budget)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    await db.commit()
    return {"project_id": project_id, "render_main_path": str(file),
            "format": "silent_licensed_roughcut", "requires_final_review": True}


@router.post("/projects/{project_id}/narrate", dependencies=[Depends(require_media_admin)])
async def narrate(project_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    from ..services.narration_pipeline_service import synthesize_narration
    project = await get_project(project_id, db)
    try:
        path = await synthesize_narration(project, db)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    await db.commit()
    return {"project_id": project_id, "tts_file_path": str(path), "status": "VOICE_READY"}


@router.post("/projects/{project_id}/assemble", dependencies=[Depends(require_media_admin)])
async def assemble(project_id: int, payload: PlanRequest,
                   db: AsyncSession = Depends(get_db)) -> dict:
    from ..services.narration_pipeline_service import assemble_narrated_draft
    project = await get_project(project_id, db)
    try:
        path = await assemble_narrated_draft(project, db, payload.seconds_budget)
    except (ValueError, RuntimeError, PermissionError) as exc:
        raise HTTPException(422, str(exc)) from exc
    await db.commit()
    return {"project_id": project_id, "render_main_path": str(path),
            "status": "VIDEO_DRAFT_READY", "public": False}


@router.post("/projects/{project_id}/produce", dependencies=[Depends(require_media_admin)])
async def produce(project_id: int, payload: PlanRequest,
                  db: AsyncSession = Depends(get_db)) -> dict:
    """Story outline -> voice -> optional licensed visual -> private local draft."""
    from ..services.narration_pipeline_service import synthesize_narration, assemble_narrated_draft
    project = await get_project(project_id, db)
    try:
        await prepare_storyboard(project, db, payload.seconds_budget)
        await synthesize_narration(project, db)
        path = await assemble_narrated_draft(project, db, payload.seconds_budget)
    except (ValueError, RuntimeError, PermissionError) as exc:
        raise HTTPException(422, str(exc)) from exc
    await db.commit()
    return {"project_id": project_id, "render_main_path": str(path),
            "status": "VIDEO_DRAFT_READY", "requires_final_review": True}


class OpusClipRequest(BaseModel):
    source_url: str
    confirm_paid_processing: bool = False


@router.post("/projects/{project_id}/shorts/opusclip", dependencies=[Depends(require_media_admin)])
async def submit_opusclip(
    project_id: int, payload: OpusClipRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    from ..enums import RightsStatus
    from ..services.opusclip_service import OpusClipClient
    project = await get_project(project_id, db)
    drama = project.drama
    terms = drama.license_terms or {}
    external_rights = bool(
        drama.rights_status == RightsStatus.APPROVED
        and drama.human_review_approved and drama.source_rights_check
        and not drama.license_expired
        and terms.get("allow_external_processing", False)
    )
    try:
        result = await OpusClipClient().create_shorts(
            payload.source_url,
            billing_confirmed=payload.confirm_paid_processing,
            rights_verified=external_rights,
            prompt=f"Highlights of {drama.title}: reversals, dramatic turning points, important choices",
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        from httpx import HTTPError
        if isinstance(exc, HTTPError):
            raise HTTPException(502, f"OpusClip API failed: {type(exc).__name__}") from exc
        raise
    # OpusClip's paid submission is a candidate only, not a published Shorts video.
    project.shorts_candidates = [*(project.shorts_candidates or []),
        {"provider": "opusclip", "submitted": True, "result": result,
         "public_upload_allowed": False}]
    await db.commit()
    return {"submitted": True, "provider": "opusclip", "result": result,
            "requires_human_review": True}


@router.get("/opusclip/{opus_project_id}/clips", dependencies=[Depends(require_media_admin)])
async def opusclip_clips(opus_project_id: str) -> dict:
    from ..services.opusclip_service import OpusClipClient
    from httpx import HTTPError
    try:
        return await OpusClipClient().list_shorts(opus_project_id)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except HTTPError as exc:
        raise HTTPException(502, f"OpusClip API failed: {type(exc).__name__}") from exc


@router.get("/projects/{project_id}/timeline", dependencies=[Depends(require_media_admin)])
async def timeline(project_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    project = await get_project(project_id, db)
    return {"project_id": project.id, "drama": project.drama.title,
            "scene_plan": project.scene_plan or [],
            "narration_segments": project.narration_segments or [],
            "render_main_path": project.render_main_path,
            "production_status": project.production_status.value,
            "rights_status": project.drama.rights_status.value}
