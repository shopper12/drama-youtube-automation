from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..enums import ProductionStatus
from ..models import Drama, VideoProject


@dataclass
class GeneratedScript:
    title_candidates: list[str]
    thumbnail_text_candidates: list[str]
    video_script: str
    scene_plan: list[dict[str, object]]
    narration_segments: list[dict[str, object]]
    shorts_candidates: list[dict[str, object]]
    critique_word_count: int
    total_word_count: int

    @property
    def critique_ratio(self) -> float:
        return self.critique_word_count / max(self.total_word_count, 1)


def _titles(title: str) -> list[str]:
    formats = [
        "결말포함 | {0} 한방에정리",
        "{0} 몰아보기 | 시간순삭 복수극",
        "{0} 줄거리요약 | 핵사이다 결말",
        "결말포함 {0} | 악역참교육",
        "{0} 몰아보기 | 반전의 끝",
        "줄거리요약 {0} | 재벌가의 비밀",
        "{0} 결말포함 | 출생의비밀",
        "시간순삭 {0} 몰아보기",
        "{0} 줄거리요약 | 복수와 반전",
        "결말포함 | {0} 완전정복",
    ]
    return [item.format(title) for item in formats]


def generate_script(
    drama: Drama,
    trend_analysis: object | None = None,
    scene_memo: str | None = None,
) -> GeneratedScript:
    sections = [
        ("0~15초", "주인공은 가장 믿었던 사람의 배신으로 모든 것을 잃고 복수를 시작합니다."),
        ("15~60초", f"{drama.title}의 인물 관계와 사건의 발단을 빠르게 정리합니다."),
        ("1~4분", "초반 사건이 연속해서 벌어지고 숨겨진 이해관계가 드러납니다."),
        ("4~8분", "갈등이 폭발하며 주인공은 함정에 빠지고 주변 인물도 선택을 강요받습니다."),
        ("8~12분", "주인공이 증거를 모아 반격을 시작하고 악역의 계획을 하나씩 무너뜨립니다."),
        ("12~16분", "모든 사건을 뒤집는 핵심 반전과 인물의 진짜 정체가 밝혀집니다."),
        ("16~18분", "최종 대결 뒤 악역은 대가를 치르고 남은 인물들의 결말이 정리됩니다."),
        ("마지막30초", "짧은 감상입니다. 다음 몰아보기에서 만나보세요."),
    ]
    script = "\n\n".join(f"[{timecode}] {text}" for timecode, text in sections)
    words = script.split()
    critique_words = sections[-1][1].split()
    scene_plan = [
        {"timecode": timecode, "summary": text, "source_media": False}
        for timecode, text in sections
    ]
    narration = [
        {"index": index, "text": text, "timecode": timecode}
        for index, (timecode, text) in enumerate(sections, start=1)
    ]
    shorts = [
        {
            "title": f"{drama.title} 쇼츠 {index}",
            "duration_seconds": 45 + index * 3,
            "script": sections[index][1],
        }
        for index in range(5)
    ]
    return GeneratedScript(
        title_candidates=_titles(drama.title),
        thumbnail_text_candidates=[
            "배신의 대가",
            "마침내 시작된 복수",
            "악역의 최후",
            "숨겨진 진실",
            "한 번에 뒤집힌 판",
            "재벌가의 비밀",
            "끝까지 속였다",
            "출생의 비밀",
            "사이다 반격",
            "충격 반전 결말",
        ],
        video_script=script,
        scene_plan=scene_plan,
        narration_segments=narration,
        shorts_candidates=shorts,
        critique_word_count=len(critique_words),
        total_word_count=len(words),
    )


async def enqueue_script_generation(
    drama_id: int, db: AsyncSession
) -> VideoProject:
    drama = await db.get(Drama, drama_id)
    if drama is None:
        raise ValueError(f"Drama {drama_id} not found")
    result = generate_script(drama, scene_memo=drama.source_memo)
    project = (
        await db.scalars(
            select(VideoProject).where(VideoProject.drama_id == drama_id)
        )
    ).first()
    if project is None:
        project = VideoProject(drama_id=drama_id)
        db.add(project)
    project.title_candidates = result.title_candidates
    project.thumbnail_text_candidates = result.thumbnail_text_candidates
    project.script = result.video_script
    project.scene_plan = result.scene_plan
    project.narration_segments = result.narration_segments
    project.shorts_candidates = result.shorts_candidates
    project.production_status = ProductionStatus.SCRIPT_READY
    drama.production_status = ProductionStatus.SCRIPT_READY
    await db.flush()
    from .notification_service import notify

    await notify("대본 완성", drama.title)
    return project
