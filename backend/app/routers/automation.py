from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Drama
from ..services.free_automation_service import build_free_automation_plan

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get("/free-tool-plan")
async def free_tool_plan() -> dict[str, object]:
    return build_free_automation_plan()


@router.get("/free-tool-plan/{drama_id}")
async def drama_free_tool_plan(
    drama_id: int, db: AsyncSession = Depends(get_db)
) -> dict[str, object]:
    drama = await db.get(Drama, drama_id)
    if drama is None:
        raise HTTPException(404, "Drama not found")
    return build_free_automation_plan(drama)
