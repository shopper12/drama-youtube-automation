from datetime import datetime, timezone

from app.models import TrendVideo
from app.services.youtube_trend_service import analyze_trends


def video(video_id: str, views: int) -> TrendVideo:
    return TrendVideo(
        video_id=video_id,
        title=f"드라마 결말포함 {video_id}",
        channel_title="channel",
        view_count=views,
        like_count=0,
        duration_seconds=1200,
        published_at=datetime.now(timezone.utc),
        keyword_query="드라마 결말포함",
    )


def test_analysis_sorts_by_view_count_descending():
    result = analyze_trends([video("low", 10), video("high", 100), video("mid", 50)])
    assert [item.view_count for item in result.videos] == [100, 50, 10]
    assert result.label == "검색어 기반 인기 표본"
