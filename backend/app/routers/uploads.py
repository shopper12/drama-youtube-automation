from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services.compliance_service import ComplianceBlockedError
from ..services.youtube_upload_service import (
    publish_now,
    schedule_publish,
    upload_private_draft,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])


def blocked_error(error: ComplianceBlockedError) -> HTTPException:
    return HTTPException(
        409,
        {
            "gate": error.result.gate.value,
            "reason": error.result.reason,
        },
    )


@router.post("/{project_id}/private")
async def private_upload(
    project_id: int, db: AsyncSession = Depends(get_db)
) -> dict[str, object]:
    try:
        project = await upload_private_draft(project_id, db)
        await db.commit()
        return {"id": project.id, "youtube_video_id": project.youtube_video_id}
    except ComplianceBlockedError as error:
        raise blocked_error(error) from error


@router.post("/{project_id}/schedule")
async def schedule(
    project_id: int,
    publish_at: datetime,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        project = await schedule_publish(project_id, publish_at, db)
        await db.commit()
        return {"id": project.id, "desired_publish_at": project.desired_publish_at}
    except ComplianceBlockedError as error:
        raise blocked_error(error) from error


@router.post("/{project_id}/publish")
async def publish(
    project_id: int, db: AsyncSession = Depends(get_db)
) -> dict[str, object]:
    try:
        project = await publish_now(project_id, db)
        await db.commit()
        return {"id": project.id, "status": project.production_status.value}
    except ComplianceBlockedError as error:
        raise blocked_error(error) from error
