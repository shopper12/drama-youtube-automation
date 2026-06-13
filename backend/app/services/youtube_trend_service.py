from __future__ import annotations

from collections import Counter, defaultdict
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

import isodate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import TrendVideo


SEARCH_QUERIES = (
    "드라마 결말포함",
    "드라마 몰아보기",
    "드라마 줄거리 요약",
    "핵사이다 드라마",
    "악역 참교육 드라마",
    "복수 드라마 결말포함",
    "불륜 드라마 결말포함",
    "재벌 드라마 몰아보기",
    "넷플릭스 드라마 결말포함",
)
TITLE_KEYWORDS = (
    "결말포함",
    "몰아보기",
    "시간순삭",
    "핵사이다",
    "악역",
    "복수",
    "반전",
    "불륜",
    "재벌",
)


@dataclass
class TrendAnalysis:
    label: str
    videos: list[TrendVideo]
    keyword_frequency: dict[str, int]
    average_views_by_duration: dict[str, float]
    title_patterns: list[str]
    thumbnail_phrases: list[str]


class GoogleTrendCollector:
    def __init__(self, service):
        self.service = service

    async def search(self, query: str, max_results: int = 25) -> list[dict[str, Any]]:
        response = await asyncio.to_thread(
            lambda: self.service.search()
            .list(
                part=["snippet"],
                q=query,
                type="video",
                order="viewCount",
                maxResults=max_results,
            )
            .execute()
        )
        return response.get("items", [])

    async def details(self, video_ids: list[str]) -> list[dict[str, Any]]:
        if not video_ids:
            return []
        response = await asyncio.to_thread(
            lambda: self.service.videos()
            .list(
                part=["statistics", "contentDetails", "snippet"],
                id=video_ids,
            )
            .execute()
        )
        return response.get("items", [])


async def collect_trends(
    collector: GoogleTrendCollector,
    db: AsyncSession,
    queries: Iterable[str] = SEARCH_QUERIES,
) -> int:
    stored = 0
    for query in queries:
        search_items = await collector.search(query)
        ids = [item["id"]["videoId"] for item in search_items if "videoId" in item["id"]]
        for item in await collector.details(ids):
            snippet = item["snippet"]
            statistics = item.get("statistics", {})
            duration = isodate.parse_duration(
                item["contentDetails"].get("duration", "PT0S")
            )
            published_at = datetime.fromisoformat(
                snippet["publishedAt"].replace("Z", "+00:00")
            )
            video = await db.scalar(
                select(TrendVideo).where(TrendVideo.video_id == item["id"])
            )
            if video is None:
                video = TrendVideo(video_id=item["id"])
                db.add(video)
            video.title = snippet["title"]
            video.channel_title = snippet["channelTitle"]
            video.view_count = int(statistics.get("viewCount", 0))
            video.like_count = int(statistics.get("likeCount", 0))
            video.duration_seconds = int(duration.total_seconds())
            video.published_at = published_at
            video.thumbnail_url = (
                snippet.get("thumbnails", {}).get("high", {}).get("url")
            )
            video.keyword_query = query
            stored += 1
    await db.flush()
    return stored


def duration_bucket(seconds: int) -> str:
    minutes = seconds / 60
    if minutes < 20:
        return "10분"
    if minutes < 40:
        return "20분"
    if minutes < 60:
        return "40분"
    return "60분↑"


def analyze_trends(videos: Iterable[TrendVideo]) -> TrendAnalysis:
    sorted_videos = sorted(videos, key=lambda item: item.view_count, reverse=True)
    frequencies = {
        keyword: sum(keyword in video.title for video in sorted_videos)
        for keyword in TITLE_KEYWORDS
    }
    views: dict[str, list[int]] = defaultdict(list)
    for video in sorted_videos:
        views[duration_bucket(video.duration_seconds)].append(video.view_count)
    averages = {
        bucket: sum(counts) / len(counts) for bucket, counts in views.items()
    }
    patterns = [video.title for video in sorted_videos[:10]]
    tokens = Counter(
        token
        for video in sorted_videos
        for token in video.title.replace("|", " ").replace("[", " ").replace("]", " ").split()
        if len(token) >= 2
    )
    phrases = [token for token, _ in tokens.most_common(10)]
    return TrendAnalysis(
        label="검색어 기반 인기 표본",
        videos=sorted_videos,
        keyword_frequency=frequencies,
        average_views_by_duration=averages,
        title_patterns=patterns,
        thumbnail_phrases=phrases,
    )
