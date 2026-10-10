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


@router.get("/projects/{project_id}/timeline", dependencies=[Depends(require_media_admin)])
async def timeline(project_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    project = await get_project(project_id, db)
    return {"project_id": project.id, "drama": project.drama.title,
            "scene_plan": project.scene_plan or [],
            "narration_segments": project.narration_segments or [],
            "render_main_path": project.render_main_path,
            "production_status": project.production_status.value,
            "rights_status": project.drama.rights_status.value}
