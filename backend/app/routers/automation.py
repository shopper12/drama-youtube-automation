from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Drama
from ..schemas import TopVideoAutomationRun
from ..services.free_automation_service import build_free_automation_plan
from ..services.top_video_automation_service import (
    AutomationPreflightError,
    NoTrendVideoError,
    run_top_video_automation,
)

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


@router.post("/top-video/run")
async def run_top_video(
    payload: TopVideoAutomationRun = Body(default_factory=TopVideoAutomationRun),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        result = await run_top_video_automation(
            db,
            recent_days=payload.recent_days,
            publish_mode=payload.publish_mode,
            publish_at=payload.publish_at,
        )
        await db.commit()
        return result
    except AutomationPreflightError as error:
        raise HTTPException(503, {"missing": error.missing}) from error
    except NoTrendVideoError as error:
        raise HTTPException(404, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(400, str(error)) from error
