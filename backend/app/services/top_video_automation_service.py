from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..enums import ProductionStatus
from ..models import Drama, TrendVideo, VideoProject
from .compliance_service import ComplianceBlockedError
from .email_service import register_and_send_license_request
from .script_generator_service import enqueue_script_generation
from .subtitle_service import create_srt
from .tts_service import get_tts_provider
from .video_render_service import render_draft, resolve_ffmpeg_executable
from .youtube_trend_service import GoogleTrendCollector, collect_trends
from .youtube_upload_service import (
    configure_youtube_gateway_from_env,
    publish_now,
    schedule_publish,
    upload_private_draft,
)

PublishMode = Literal["private_only", "publish_now", "schedule_publish"]


class AutomationPreflightError(RuntimeError):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("Missing automation dependencies: " + ", ".join(missing))


class NoTrendVideoError(RuntimeError):
    pass


TITLE_NOISE_PATTERNS = (
    r"\[[^\]]+\]",
    r"\([^)]*\)",
    r"결말\s*포함",
    r"결말포함",
    r"몰아보기",
    r"줄거리\s*요약",
    r"줄거리요약",
    r"한방에\s*정리",
    r"한방에정리",
    r"시간순삭",
    r"드라마",
    r"요약",
    r"리뷰",
    r"명장면",
)


def storage_root() -> Path:
    return Path(os.getenv("STORAGE_ROOT", "storage"))


def _slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", value).strip("-").lower()
    return slug[:80] or "top-video"


def extract_drama_title(video_title: str) -> str:
    title = video_title
    for separator in ("|", "｜", "-", "–", "—"):
        title = title.split(separator)[0]
    for pattern in TITLE_NOISE_PATTERNS:
        title = re.sub(pattern, " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip(" :,-_")
    return title or video_title.strip()[:80] or "인기 드라마"


async def select_top_trend_video(
    db: AsyncSession, recent_days: int = 30
) -> TrendVideo | None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=recent_days)
    recent_query = (
        select(TrendVideo)
        .where(TrendVideo.fetched_at >= cutoff)
        .order_by(TrendVideo.view_count.desc(), TrendVideo.like_count.desc())
    )
    video = (await db.scalars(recent_query)).first()
    if video is not None:
        return video
    fallback_query = select(TrendVideo).order_by(
        TrendVideo.view_count.desc(), TrendVideo.like_count.desc()
    )
    return (await db.scalars(fallback_query)).first()


async def collect_trends_from_env(db: AsyncSession) -> int:
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return 0
    from googleapiclient.discovery import build

    service = build("youtube", "v3", developerKey=api_key)
    return await collect_trends(GoogleTrendCollector(service), db)


async def choose_top_trend_video(
    db: AsyncSession, recent_days: int = 30
) -> TrendVideo:
    video = await select_top_trend_video(db, recent_days)
    if video is not None:
        return video
    await collect_trends_from_env(db)
    video = await select_top_trend_video(db, recent_days)
    if video is None:
        raise NoTrendVideoError(
            "No trend videos are available. Configure YOUTUBE_API_KEY or seed trends."
        )
    return video


async def _get_or_create_drama(
    title: str, trend_video: TrendVideo, db: AsyncSession
) -> tuple[Drama, bool]:
    drama = (
        await db.scalars(select(Drama).where(Drama.title == title).order_by(Drama.id))
    ).first()
    if drama is not None:
        drama.source_rights_check = True
        return drama, False

    drama = Drama(
        title=title,
        source_memo=(
            "자동 인기 소재 선택: 원본 영상 클립/공식 이미지를 사용하지 않는 "
            f"무클립 초안. 기준 영상: {trend_video.title}"
        ),
        source_rights_check=True,
    )
    db.add(drama)
    await db.flush()
    await register_and_send_license_request(drama.id, db)
    return drama, True


def _preflight() -> None:
    missing = []
    if resolve_ffmpeg_executable() is None:
        missing.append("FFmpeg executable")
    if missing:
        raise AutomationPreflightError(missing)


async def _create_assets(project: VideoProject, db: AsyncSession) -> VideoProject:
    root = storage_root()
    project_slug = f"{project.id}-{_slug(project.drama.title)}"
    narration_text = project.script or "\n".join(
        str(segment.get("text", "")) for segment in project.narration_segments
    )

    tts_path = root / "drafts" / f"{project_slug}.mp3"
    await get_tts_provider().synthesize(narration_text, tts_path)
    project.tts_file_path = str(tts_path)
    project.production_status = ProductionStatus.VOICE_READY
    project.drama.production_status = ProductionStatus.VOICE_READY
    await db.flush()

    subtitle_path = root / "subtitles" / f"{project_slug}.srt"
    await create_srt(project.narration_segments, subtitle_path)
    project.subtitle_file_path = str(subtitle_path)

    render_path = root / "rendered" / f"{project_slug}.mp4"
    await render_draft(render_path, subtitle_path=subtitle_path, duration_seconds=60)
    project.render_main_path = str(render_path)
    project.production_status = ProductionStatus.VIDEO_DRAFT_READY
    project.drama.production_status = ProductionStatus.VIDEO_DRAFT_READY
    await db.flush()
    return project


def _trend_payload(video: TrendVideo) -> dict[str, Any]:
    return {
        "video_id": video.video_id,
        "title": video.title,
        "channel_title": video.channel_title,
        "views": video.view_count,
        "likes": video.like_count,
        "published_at": video.published_at,
        "thumbnail_url": video.thumbnail_url,
        "keyword_query": video.keyword_query,
    }


async def run_top_video_automation(
    db: AsyncSession,
    recent_days: int = 30,
    publish_mode: PublishMode = "publish_now",
    publish_at: datetime | None = None,
) -> dict[str, Any]:
    _preflight()
    real_gateway_enabled = configure_youtube_gateway_from_env()
    trend_video = await choose_top_trend_video(db, recent_days)
    drama_title = extract_drama_title(trend_video.title)
    drama, created = await _get_or_create_drama(drama_title, trend_video, db)

    project = await enqueue_script_generation(drama.id, db)
    await db.refresh(project, attribute_names=["drama"])
    project = await _create_assets(project, db)

    blocked: dict[str, str] | None = None
    uploaded = await upload_private_draft(project.id, db)

    if publish_mode == "publish_now":
        try:
            uploaded = await publish_now(project.id, db)
        except ComplianceBlockedError as error:
            blocked = {
                "gate": error.result.gate.value,
                "reason": error.result.reason,
            }
    elif publish_mode == "schedule_publish":
        scheduled_at = publish_at or datetime.now(timezone.utc) + timedelta(hours=2)
        try:
            uploaded = await schedule_publish(project.id, scheduled_at, db)
        except ComplianceBlockedError as error:
            blocked = {
                "gate": error.result.gate.value,
                "reason": error.result.reason,
            }

    await db.refresh(uploaded, attribute_names=["drama"])
    return {
        "selected_trend": _trend_payload(trend_video),
        "drama_id": drama.id,
        "drama_title": drama.title,
        "drama_created": created,
        "project_id": uploaded.id,
        "publish_mode": publish_mode,
        "youtube_gateway": "google" if real_gateway_enabled else "local",
        "youtube_video_id": uploaded.youtube_video_id,
        "render_main_path": uploaded.render_main_path,
        "tts_file_path": uploaded.tts_file_path,
        "subtitle_file_path": uploaded.subtitle_file_path,
        "final_status": uploaded.production_status.value,
        "public_gate": uploaded.drama.public_gate.value,
        "publication_blocked": blocked,
    }
