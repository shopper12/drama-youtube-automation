from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import Drama
from ..prompts.free_automation_prompt import (
    FREE_AUTOMATION_SCRIPT_PROMPT,
    FREE_AUTOMATION_SYSTEM_PROMPT,
    FREE_AUTOMATION_TITLE_PROMPT,
)


@dataclass(frozen=True)
class FreeTool:
    stage: str
    tool: str
    free_use: str
    automation_note: str


FREE_TOOL_STACK: tuple[FreeTool, ...] = (
    FreeTool("기획/트렌드", "YouTube Data API 무료 할당량", "검색어 기반 인기 표본 수집", "기존 /trends 수집기와 연결"),
    FreeTool("대본", "Gemini 무료 티어 또는 로컬 LLM", "프롬프트 기반 초안 생성", "환경변수로 provider 교체"),
    FreeTool("음성", "edge-tts", "무료 Microsoft Edge TTS 음성 합성", "TTS 파일 생성 작업으로 교체 가능"),
    FreeTool("자막", "Whisper.cpp 또는 faster-whisper", "로컬 STT/정렬", "SRT 생성 서비스에 연결"),
    FreeTool("이미지/배경", "Canva 무료·Pexels·Pixabay", "권리 확인 가능한 배경/아이콘", "원본 드라마 소재 사용 금지"),
    FreeTool("편집/렌더", "FFmpeg", "자막·이미지·음성 합성", "기존 렌더 큐에서 실행"),
    FreeTool("업로드", "YouTube Data API", "비공개 업로드 및 예약", "컴플라이언스 게이트 통과 후 공개"),
    FreeTool("알림", "Discord Webhook 또는 Telegram Bot", "무료 운영 알림", "게이트 실패/완료 알림"),
)


def build_free_automation_plan(drama: Drama | None = None) -> dict[str, Any]:
    title = drama.title if drama is not None else "신규 드라마"
    return {
        "title": f"{title} 무료 도구 자동 제작 플랜",
        "guardrails": [
            "허락 전 공개 업로드 금지",
            "원본 클립·원본 음성·공식 이미지 사용 금지(별도 권리 확인 전)",
            "대본은 줄거리 중심 80% 이상, 비평 10% 이하",
            "사람 검수와 라이선스 승인 후에만 공개 예약",
        ],
        "tools": [tool.__dict__ for tool in FREE_TOOL_STACK],
        "prompts": {
            "system": FREE_AUTOMATION_SYSTEM_PROMPT,
            "script": FREE_AUTOMATION_SCRIPT_PROMPT,
            "title": FREE_AUTOMATION_TITLE_PROMPT.format(title=title),
        },
        "workflow": [
            "트렌드 키워드 수집",
            "드라마 등록 및 권리자 허락 요청 자동 발송",
            "무료 LLM/프롬프트로 제목·대본·쇼츠 후보 생성",
            "edge-tts로 내레이션 생성",
            "FFmpeg로 무클립 비공개 초안 렌더",
            "사람 검수·라이선스·소스 권리 체크",
            "YouTube 비공개 업로드 후 공개 게이트 통과 시 예약",
        ],
    }
