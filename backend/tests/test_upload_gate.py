from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.enums import RightsStatus
from app.models import ComplianceLog, Drama, VideoProject
from app.services.compliance_service import ComplianceBlockedError
from app.services.youtube_upload_service import (
    publish_now,
    schedule_publish,
    set_youtube_gateway,
    upload_private_draft,
)


class RecordingGateway:
    def __init__(self):
        self.upload_body = None
        self.status_updates = []

    async def upload(self, body, file_path):
        self.upload_body = body
        return "youtube-test-id"

    async def update_status(self, video_id, status):
        self.status_updates.append((video_id, status))


async def make_project(db, rights_status=RightsStatus.SENT):
    drama = Drama(
        title="Upload Test",
        rights_status=rights_status,
        source_rights_check=True,
        human_review_approved=rights_status == RightsStatus.APPROVED,
    )
    project = VideoProject(drama=drama, render_main_path="draft.mp4")
    db.add(project)
    await db.commit()
    return project


@pytest.mark.asyncio
async def test_sent_rights_can_upload_private_draft(db):
    gateway = RecordingGateway()
    set_youtube_gateway(gateway)
    project = await make_project(db)
    uploaded = await upload_private_draft(project.id, db)
    assert uploaded.youtube_video_id == "youtube-test-id"


@pytest.mark.asyncio
async def test_sent_rights_cannot_schedule(db):
    project = await make_project(db)
    with pytest.raises(ComplianceBlockedError):
        await schedule_publish(
            project.id, datetime.now(timezone.utc) + timedelta(hours=2), db
        )


@pytest.mark.asyncio
async def test_sent_rights_cannot_publish_now(db):
    project = await make_project(db)
    with pytest.raises(ComplianceBlockedError):
        await publish_now(project.id, db)


@pytest.mark.asyncio
async def test_schedule_rejects_time_within_60_minutes(db):
    project = await make_project(db, RightsStatus.APPROVED)
    with pytest.raises(ValueError):
        await schedule_publish(
            project.id, datetime.now(timezone.utc) + timedelta(minutes=60), db
        )


@pytest.mark.asyncio
async def test_private_upload_never_contains_publish_at(db):
    gateway = RecordingGateway()
    set_youtube_gateway(gateway)
    project = await make_project(db)
    await upload_private_draft(project.id, db)
    assert "publishAt" not in gateway.upload_body["status"]


@pytest.mark.asyncio
async def test_schedule_publish_uploads_draft_without_duplicate_private_check(db):
    gateway = RecordingGateway()
    set_youtube_gateway(gateway)
    project = await make_project(db, RightsStatus.APPROVED)
    await schedule_publish(project.id, datetime.now(timezone.utc) + timedelta(hours=2), db)
    logs = list(
        (
            await db.scalars(
                select(ComplianceLog).where(ComplianceLog.project_id == project.id)
            )
        ).all()
    )
    assert [log.mode for log in logs] == ["schedule_publish"]
