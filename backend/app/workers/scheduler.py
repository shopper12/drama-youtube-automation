from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..database import AsyncSessionLocal
from ..enums import PublicGate
from ..models import Drama, TrendVideo, VideoProject
from ..services.compliance_service import compliance_check
from ..services.email_service import send_due_reminders
from ..services.notification_service import notify
from ..services.youtube_upload_service import apply_scheduled_publish

KST = ZoneInfo("Asia/Seoul")
scheduler = AsyncIOScheduler(timezone=KST)


async def reminder_job() -> None:
    async with AsyncSessionLocal() as db:
        await send_due_reminders(db)
        await db.commit()


async def scheduled_publish_revalidation_job() -> None:
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=1)
    async with AsyncSessionLocal() as db:
        query = (
            select(VideoProject)
            .where(
                VideoProject.desired_publish_at.is_not(None),
                VideoProject.desired_publish_at <= cutoff,
                VideoProject.desired_publish_at > now,
            )
            .options(selectinload(VideoProject.drama))
        )
        projects = list((await db.scalars(query)).all())
        for project in projects:
            result = await compliance_check(project.id, "schedule_publish", db)
            if result.allowed:
                await apply_scheduled_publish(project, db)
            else:
                project.desired_publish_at = None
                await notify(
                    "예약 재검증 실패",
                    f"{project.drama.title}: {result.gate.value} - {result.reason}",
                )
        await db.commit()


async def license_expiry_job() -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        dramas = list((await db.scalars(select(Drama))).all())
        for drama in dramas:
            expires_at = (drama.license_terms or {}).get("expires_at")
            if not expires_at:
                continue
            expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if expiry <= now:
                drama.license_expired = True
                drama.public_gate = PublicGate.BLOCKED_LICENSE_EXPIRED
        await db.commit()


async def trend_collection_job() -> None:
    # API collection is credential-dependent; persisted samples are analyzed by the service.
    async with AsyncSessionLocal() as db:
        await db.execute(select(TrendVideo).limit(1))


scheduler.add_job(
    reminder_job,
    "cron",
    hour=9,
    minute=0,
    id="license-reminders",
    replace_existing=True,
)
scheduler.add_job(
    scheduled_publish_revalidation_job,
    "cron",
    minute=0,
    id="publish-revalidation",
    replace_existing=True,
)
scheduler.add_job(
    license_expiry_job,
    "cron",
    hour=0,
    minute=0,
    id="license-expiry",
    replace_existing=True,
)
scheduler.add_job(
    trend_collection_job,
    "cron",
    day_of_week="mon",
    hour=8,
    minute=0,
    id="trend-collection",
    replace_existing=True,
)
