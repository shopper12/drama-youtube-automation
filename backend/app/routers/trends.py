from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import TrendVideo
from ..services.youtube_trend_service import analyze_trends

router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("/analysis")
async def trend_analysis(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    videos = list((await db.scalars(select(TrendVideo))).all())
    result = analyze_trends(videos)
    return {
        "label": result.label,
        "videos": [
            {"video_id": item.video_id, "title": item.title, "views": item.view_count}
            for item in result.videos
        ],
        "keyword_frequency": result.keyword_frequency,
        "average_views_by_duration": result.average_views_by_duration,
        "title_patterns": result.title_patterns,
        "thumbnail_phrases": result.thumbnail_phrases,
    }
