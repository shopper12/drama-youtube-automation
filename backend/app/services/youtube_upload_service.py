from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from googleapiclient.http import MediaFileUpload
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..enums import ProductionStatus
from ..models import VideoProject
from .compliance_service import ComplianceBlockedError, compliance_check
from .notification_service import notify


class YouTubeGateway(Protocol):
    async def upload(self, body: dict[str, Any], file_path: str) -> str: ...
    async def update_status(self, video_id: str, status: dict[str, Any]) -> None: ...


class GoogleYouTubeGateway:
    def __init__(self, service):
        self.service = service

    async def upload(self, body: dict[str, Any], file_path: str) -> str:
        request = self.service.videos().insert(
            part=["snippet", "status"],
            body=body,
            media_body=MediaFileUpload(file_path, resumable=True),
        )
        response = await asyncio.to_thread(request.execute)
        return response["id"]

    async def update_status(self, video_id: str, status: dict[str, Any]) -> None:
        await asyncio.to_thread(
            lambda: self.service.videos()
            .update(
                part=["status"],
                body={"id": video_id, "status": status},
            )
            .execute()
        )


class LocalYouTubeGateway:
    async def upload(self, body: dict[str, Any], file_path: str) -> str:
        return f"local-{Path(file_path).stem}"

    async def update_status(self, video_id: str, status: dict[str, Any]) -> None:
        return None


_gateway: YouTubeGateway = LocalYouTubeGateway()


def set_youtube_gateway(gateway: YouTubeGateway) -> None:
    global _gateway
    _gateway = gateway


async def _get_project(project_id: int, db: AsyncSession) -> VideoProject:
    query = (
        select(VideoProject)
        .where(VideoProject.id == project_id)
        .options(selectinload(VideoProject.drama))
    )
    project = (await db.execute(query)).scalar_one_or_none()
    if project is None:
        raise ValueError(f"VideoProject {project_id} not found")
    return project


async def _refresh_project(project: VideoProject, db: AsyncSession) -> VideoProject:
    await db.refresh(project, attribute_names=["drama"])
    return project


def _private_upload_body(project: VideoProject) -> dict[str, Any]:
    return {
        "snippet": {
            "title": (project.title_candidates or [project.drama.title])[0],
            "description": "내부 검수용 비공개 초안",
        },
        "status": {"privacyStatus": "private"},
    }


async def _upload_draft_if_needed(project: VideoProject, db: AsyncSession) -> None:
    """Upload the private draft without running compliance_check again."""
    if project.youtube_video_id:
        return
    if not project.render_main_path:
        raise ValueError("Rendered main video is required")
    body = _private_upload_body(project)
    project.youtube_video_id = await _gateway.upload(body, project.render_main_path)
    project.production_status = ProductionStatus.PRIVATE_UPLOADED
    project.drama.production_status = ProductionStatus.PRIVATE_UPLOADED
    await db.flush()
    await notify("private 업로드 완료", project.drama.title)


async def upload_private_draft(
    project_id: int, db: AsyncSession
) -> VideoProject:
    result = await compliance_check(project_id, "private_draft", db)
    if not result.allowed:
        raise ComplianceBlockedError(result)
    project = await _get_project(project_id, db)
    await _refresh_project(project, db)
    await _upload_draft_if_needed(project, db)
    return project


async def schedule_publish(
    project_id: int,
    publish_at: datetime,
    db: AsyncSession,
) -> VideoProject:
    now = datetime.now(timezone.utc)
    if publish_at.tzinfo is None:
        raise ValueError("publish_at must be timezone-aware")
    if publish_at.astimezone(timezone.utc) <= now + timedelta(minutes=60):
        raise ValueError("publish_at must be more than 60 minutes in the future")
    result = await compliance_check(project_id, "schedule_publish", db)
    if not result.allowed:
        raise ComplianceBlockedError(result)
    project = await _get_project(project_id, db)
    await _refresh_project(project, db)
    await _upload_draft_if_needed(project, db)
    project.desired_publish_at = publish_at.astimezone(timezone.utc)
    project.production_status = ProductionStatus.READY_TO_PUBLISH
    project.drama.production_status = ProductionStatus.READY_TO_PUBLISH
    await db.flush()
    return project


async def apply_scheduled_publish(
    project: VideoProject, db: AsyncSession
) -> None:
    if not project.youtube_video_id or not project.desired_publish_at:
        raise ValueError("Private YouTube video and desired_publish_at are required")
    utc_dt = project.desired_publish_at.astimezone(timezone.utc)
    status = {
        "privacyStatus": "private",
        "publishAt": utc_dt.isoformat().replace("+00:00", "Z"),
    }
    await _gateway.update_status(project.youtube_video_id, status)
    await db.flush()


async def publish_now(project_id: int, db: AsyncSession) -> VideoProject:
    result = await compliance_check(project_id, "publish_now", db)
    if not result.allowed:
        raise ComplianceBlockedError(result)
    project = await _get_project(project_id, db)
    await _refresh_project(project, db)
    if not project.youtube_video_id:
        raise ValueError("A private draft must be uploaded first")
    await _gateway.update_status(
        project.youtube_video_id, {"privacyStatus": "public"}
    )
    project.production_status = ProductionStatus.PUBLISHED
    project.drama.production_status = ProductionStatus.PUBLISHED
    await db.flush()
    await notify("공개 완료", project.drama.title)
    return project
