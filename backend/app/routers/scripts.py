from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services.script_generator_service import enqueue_script_generation

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.post("/{drama_id}/generate")
async def generate(
    drama_id: int, db: AsyncSession = Depends(get_db)
) -> dict[str, object]:
    project = await enqueue_script_generation(drama_id, db)
    await db.commit()
    return {
        "project_id": project.id,
        "title_candidates": project.title_candidates,
        "script": project.script,
    }
