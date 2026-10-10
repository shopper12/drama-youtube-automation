import pytest
from sqlalchemy import select

from app.models import Drama, SourceVideo


@pytest.mark.asyncio
async def test_source_video_persists_episode_status_and_checksum(db):
    drama = Drama(title="2화짜리 드라마")
    source = SourceVideo(drama=drama, episode_number=2, original_filename="ep2.mp4",
                         stored_path="/storage/2/uuid.mp4", sha256="f"*64,
                         duration_seconds=3600.0, status="UPLOADED", analysis_authorized=True)
    db.add(source)
    await db.commit()
    got = await db.scalar(select(SourceVideo).where(SourceVideo.drama_id == drama.id))
    assert got is not None
    assert got.episode_number == 2
    assert got.status == "UPLOADED"
    assert got.analysis_result is None
