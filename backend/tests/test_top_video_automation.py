from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.enums import ProductionStatus, PublicGate, RightsStatus
from app.models import Drama, TrendVideo
from app.services import top_video_automation_service as automation
from app.services.top_video_automation_service import (
    AutomationPreflightError,
    extract_drama_title,
    run_top_video_automation,
    select_top_trend_video,
)
from app.services.youtube_upload_service import LocalYouTubeGateway, set_youtube_gateway


class RecordingGateway:
    def __init__(self):
        self.upload_body = None
        self.status_updates = []

    async def upload(self, body, file_path):
        self.upload_body = body
        return "youtube-top-video"

    async def update_status(self, video_id, status):
        self.status_updates.append((video_id, status))


def trend(video_id: str, title: str, views: int, days_old: int = 0) -> TrendVideo:
    now = datetime.now(timezone.utc)
    return TrendVideo(
        video_id=video_id,
        title=title,
        channel_title="인기 채널",
        view_count=views,
        like_count=views // 10,
        duration_seconds=1200,
        published_at=now - timedelta(days=days_old),
        fetched_at=now - timedelta(days=days_old),
        thumbnail_url="https://example.com/thumb.jpg",
        keyword_query="드라마 결말포함",
    )


@pytest.fixture(autouse=True)
def reset_youtube_gateway():
    yield
    set_youtube_gateway(LocalYouTubeGateway())


@pytest.fixture
def automation_env(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("TTS_PROVIDER", "draft")
    monkeypatch.setenv("YOUTUBE_PUBLISH_ENABLED", "false")
    monkeypatch.setattr(automation, "resolve_ffmpeg_executable", lambda: "ffmpeg")

    async def fake_render(output_path: Path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake video")
        return output_path

    monkeypatch.setattr(automation, "render_draft", fake_render)
    return tmp_path


def test_extract_drama_title_removes_youtube_title_noise():
    title = extract_drama_title("[결말포함] 비밀의 집 몰아보기 | 시간순삭 드라마")
    assert title == "비밀의 집"


@pytest.mark.asyncio
async def test_select_top_trend_video_uses_recent_view_count(db):
    db.add_all(
        [
            trend("old", "오래된 드라마 결말포함", 1000, days_old=60),
            trend("low", "낮은 드라마 결말포함", 10),
            trend("high", "높은 드라마 결말포함", 100),
        ]
    )
    await db.commit()

    selected = await select_top_trend_video(db, recent_days=30)

    assert selected.video_id == "high"


@pytest.mark.asyncio
async def test_top_video_run_publishes_when_gate_is_allowed(db, automation_env):
    gateway = RecordingGateway()
    set_youtube_gateway(gateway)
    db.add(trend("top", "비밀의 집 결말포함", 500))
    db.add(
        Drama(
            title="비밀의 집",
            rights_status=RightsStatus.APPROVED,
            source_rights_check=True,
            human_review_approved=True,
        )
    )
    await db.commit()

    result = await run_top_video_automation(db)

    assert result["selected_trend"]["video_id"] == "top"
    assert result["drama_created"] is False
    assert result["youtube_gateway"] == "local"
    assert result["final_status"] == ProductionStatus.PUBLISHED.value
    assert result["public_gate"] == PublicGate.ALLOWED.value
    assert result["publication_blocked"] is None
    assert gateway.upload_body["status"] == {"privacyStatus": "private"}
    assert gateway.status_updates == [
        ("youtube-top-video", {"privacyStatus": "public"})
    ]


@pytest.mark.asyncio
async def test_top_video_run_stops_after_private_upload_without_license(
    db, automation_env
):
    gateway = RecordingGateway()
    set_youtube_gateway(gateway)
    db.add(trend("top", "새 드라마 결말포함", 500))
    await db.commit()

    result = await run_top_video_automation(db)

    assert result["drama_created"] is True
    assert result["final_status"] == ProductionStatus.PRIVATE_UPLOADED.value
    assert result["publication_blocked"]["gate"] == PublicGate.BLOCKED_NO_LICENSE.value
    assert gateway.upload_body["status"] == {"privacyStatus": "private"}
    assert gateway.status_updates == []


@pytest.mark.asyncio
async def test_top_video_run_reports_missing_ffmpeg(db, monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("YOUTUBE_PUBLISH_ENABLED", "false")
    monkeypatch.setattr(automation, "resolve_ffmpeg_executable", lambda: None)
    db.add(trend("top", "비밀의 집 결말포함", 500))
    await db.commit()

    with pytest.raises(AutomationPreflightError) as error:
        await run_top_video_automation(db)

    assert error.value.missing == ["FFmpeg executable"]
