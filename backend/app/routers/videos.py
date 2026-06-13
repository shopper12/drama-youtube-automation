from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import VideoProject

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("")
async def list_projects(db: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    query = select(VideoProject).options(selectinload(VideoProject.drama))
    projects = list((await db.scalars(query)).all())
    return [
        {
            "id": project.id,
            "drama_id": project.drama_id,
            "drama_title": project.drama.title,
            "production_status": project.production_status.value,
            "public_gate": project.drama.public_gate.value,
            "rights_status": project.drama.rights_status.value,
            "youtube_video_id": project.youtube_video_id,
            "desired_publish_at": project.desired_publish_at,
        }
        for project in projects
    ]
