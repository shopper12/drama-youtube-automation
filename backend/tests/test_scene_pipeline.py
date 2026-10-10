import json
import pytest
from sqlalchemy import select

from app.enums import RightsStatus
from app.models import ComplianceLog, Drama, SourceVideo, VideoProject
from app.services.media_pipeline_service import prepare_storyboard, render_licensed_roughcut
from app.services.scene_analyzer_service import SCENE_PROMPT, parse_scenes, select_highlights, seconds


def sample(start="00:05", end="00:12", event="주인공이 편지를 발견한다", importance=5, confidence=0.9):
    return {"start": start, "end": end, "event": event,
            "importance": importance, "confidence": confidence, "characters": ["주인공"]}


def test_gemini_prompt_has_valid_template():
    assert "24 scenes" in SCENE_PROMPT.format(limit=24)
    assert '{"start"' in SCENE_PROMPT.format(limit=24)


def test_timestamp_parser_accepts_two_and_three_part_formats():
    assert seconds("01:02") == 62
    assert seconds("01:02:03") == 3723
    with pytest.raises(ValueError):
        seconds("not-a-time")


def test_scenes_reject_out_of_range_and_overlapping_times():
    raw = json.dumps({"scenes": [
        sample(),
        sample(start="00:07", end="00:13", event="겹친 사건", importance=2),
        sample(start="09:59", end="10:05", event="범위 초과"),
    ]}, ensure_ascii=False)
    scenes = parse_scenes(raw, 600, 3, 2)
    assert len(scenes) == 1
    assert scenes[0]["source_id"] == 3
    assert scenes[0]["start_seconds"] == 5
    assert scenes[0]["human_reviewed"] is False


def test_highlights_ranks_by_importance_but_restores_episode_order():
    scenes = [
        {"episode_number": 1, "start_seconds": 2, "end_seconds": 22, "importance": 1, "confidence": 1.0},
        {"episode_number": 2, "start_seconds": 5, "end_seconds": 15, "importance": 5, "confidence": 0.9},
        {"episode_number": 1, "start_seconds": 40, "end_seconds": 50, "importance": 4, "confidence": 0.8},
    ]
    chosen = select_highlights(scenes, seconds_budget=21)
    assert [s["importance"] for s in chosen] == [4, 5]


@pytest.mark.asyncio
async def test_storyboard_uses_real_scene_events_not_generic_plot(db):
    drama = Drama(title="테스트 드라마")
    project = VideoProject(drama=drama, scene_plan=[
        {"source_id": 1, "episode_number": 1, "start_seconds": 5,
         "end_seconds": 12, "event": "어머니가 실종 신고를 한다",
         "importance": 5, "confidence": 0.9},
    ])
    db.add(project)
    await db.flush()
    result = await prepare_storyboard(project, db)
    assert "어머니가 실종 신고를 한다" in result["script"]
    assert "모든 것을 잃고 복수" not in result["script"]
    assert result["review_required"] is True


@pytest.mark.asyncio
async def test_render_original_clips_is_blocked_before_license(db):
    drama = Drama(title="미허락 작품", rights_status=RightsStatus.SENT)
    project = VideoProject(drama=drama)
    db.add(project)
    await db.flush()
    with pytest.raises(PermissionError):
        await render_licensed_roughcut(project, db)
