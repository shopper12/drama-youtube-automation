from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..models import Drama
from ..prompts.free_automation_prompt import (
    FREE_AUTOMATION_SCRIPT_PROMPT,
    FREE_AUTOMATION_SYSTEM_PROMPT,
    FREE_AUTOMATION_TITLE_PROMPT,
)


@dataclass(frozen=True)
class ToolRecommendation:
    stage: str
    tool: str
    free_use: str
    automation_note: str
    policy_note: str


@dataclass(frozen=True)
class ManualOrAvoidTool:
    tool: str
    status: str
    reason: str
    safer_default: str


FREE_TOOL_STACK: tuple[ToolRecommendation, ...] = (
    ToolRecommendation(
        "기획/트렌드",
        "YouTube Data API 무료 할당량",
        "검색어 기반 인기 표본 수집",
        "기존 /trends 수집기와 연결",
        "search.list 표본은 전체 인기 순위가 아니므로 사람이 주제 적합성을 검수",
    ),
    ToolRecommendation(
        "대본",
        "Gemini 무료 티어 또는 로컬 LLM",
        "프롬프트 기반 초안 생성",
        "환경변수로 provider 교체",
        "초안은 원본 해설·맥락을 더한 뒤 공개 전 사람이 검수",
    ),
    ToolRecommendation(
        "음성",
        "edge-tts",
        "무료 Microsoft Edge TTS 음성 합성",
        "TTS 파일 생성 작업으로 교체 가능",
        "AI 음성 사용 사실과 채널 톤이 시청자를 오도하지 않는지 확인",
    ),
    ToolRecommendation(
        "자막",
        "Whisper.cpp 또는 faster-whisper",
        "로컬 STT/정렬",
        "SRT 생성 서비스에 연결",
        "자막 오류로 사실관계·인물명이 바뀌지 않는지 검수",
    ),
    ToolRecommendation(
        "이미지/배경",
        "Canva 무료·Pexels·Pixabay",
        "권리 확인 가능한 배경/아이콘",
        "원본 드라마 소재 사용 금지",
        "라이선스 조건과 AI 이미지 표시 필요 여부를 작업마다 기록",
    ),
    ToolRecommendation(
        "편집/렌더",
        "FFmpeg",
        "자막·이미지·음성 합성",
        "기존 렌더 큐에서 실행",
        "반복 슬라이드쇼가 되지 않도록 챕터별 정보 시각화와 해설 블록 포함",
    ),
    ToolRecommendation(
        "업로드",
        "YouTube Data API",
        "비공개 업로드 및 예약",
        "컴플라이언스 게이트 통과 후 공개",
        "허락·사람 검수·소스 권리 확인 전 공개 예약 금지",
    ),
    ToolRecommendation(
        "알림",
        "Discord Webhook 또는 Telegram Bot",
        "무료 운영 알림",
        "게이트 실패/완료 알림",
        "권리·정책 실패 알림은 자동 재시도하지 않고 사람이 판단",
    ),
)

AVOID_OR_MANUAL_TOOLS: tuple[ManualOrAvoidTool, ...] = (
    ManualOrAvoidTool(
        "Pictory AI",
        "optional_manual",
        "무료 트라이얼·워터마크·상업 이용 조건이 바뀔 수 있어 필수 자동화 의존성으로 두지 않음",
        "FFmpeg 렌더와 권리 확인 가능한 무료 스톡/그래픽",
    ),
    ManualOrAvoidTool(
        "Runway ML",
        "optional_manual",
        "무료 크레딧과 출력 조건이 제한적이며 반복 생성물은 수익화 심사 리스크가 있음",
        "정적 그래픽, 차트, 지도, 직접 만든 모션 템플릿",
    ),
    ManualOrAvoidTool(
        "ElevenLabs 무료 플랜",
        "optional_manual",
        "무료 문자 수와 상업 이용 조건이 변동될 수 있어 보조 선택지로만 사용",
        "edge-tts 또는 사용 조건을 확인한 로컬/무료 TTS",
    ),
    ManualOrAvoidTool(
        "CapCut 워터마크 우회",
        "avoid",
        "워터마크 제거를 줌인으로 가리는 방식은 약관·품질·신뢰 리스크가 큼",
        "워터마크 없는 FFmpeg 렌더",
    ),
    ManualOrAvoidTool(
        "TubeBuddy/VidIQ 무료 플랜",
        "optional_manual",
        "키워드 참고 도구로는 유용하지만 API 기반 자동 의사결정의 필수 조건은 아님",
        "YouTube Data API 표본 + 사람이 니치/제목 검수",
    ),
)

REVIEW_VERDICT = {
    "summary": "무료 도구 조합은 가능하지만, 수익 보장·워터마크 우회·반복 요약 대량 생산은 제외한다.",
    "good": [
        "얼굴 없는 채널 운영, 니치 선정, 대본·TTS·자막·렌더 자동화는 이 MVP 구조와 잘 맞음",
        "한국 드라마를 영어권 시청자에게 해설하는 방향은 차별화 포인트가 있음",
        "YouTube Data API, edge-tts, FFmpeg, 로컬 STT처럼 무료로 반복 실행 가능한 도구를 중심에 둘 수 있음",
    ],
    "risky": [
        "Pictory, Runway, ElevenLabs, TubeBuddy, VidIQ 등은 무료 조건이 변할 수 있어 선택 도구로만 취급",
        "단순 줄거리 재가공이나 반복 슬라이드쇼는 재사용·반복 콘텐츠로 판단될 위험이 있음",
        "AI 합성 장면, 인물 유사 이미지, 과장된 썸네일은 공개 전 표시·오인 가능성을 확인해야 함",
    ],
    "rejected": [
        "월 수익 사례를 보장처럼 제시하는 문구",
        "CapCut 또는 다른 도구의 워터마크를 줌인으로 가리는 우회",
        "권리 확인 없는 원본 클립·공식 이미지·원본 음성 사용",
        "사람 검수 없는 공개 예약과 반복 템플릿 대량 업로드",
    ],
}

RECOMMENDED_PIPELINE = [
    "니치 후보를 한국 드라마 영어 해설, 한국 법률·문화 맥락, 에너지/금융 분석처럼 원본 관점이 있는 주제로 제한",
    "YouTube Data API 표본과 수동 리서치로 제목 패턴·시청자 질문·경쟁 채널을 검토",
    "무료 LLM 또는 로컬 LLM으로 초안을 만들되 원본 해설·비교·맥락 블록을 반드시 추가",
    "Canva/Pexels/Pixabay 등 권리 확인 가능한 소재와 직접 만든 그래픽으로 무클립 화면 구성",
    "edge-tts, Whisper.cpp/faster-whisper, FFmpeg로 음성·자막·렌더를 자동 생성",
    "비공개 업로드 후 저작권, AI 표시, 광고성, 제휴 링크, 사람 검수 게이트를 통과할 때만 예약",
    "YPP 전에는 디지털 제품·뉴스레터·제휴 링크를 실험하되 수익 보장 표현 없이 고지",
]

MONETIZATION_TRACKS = [
    {
        "track": "YPP 광고 수익",
        "when_available": "YouTube Partner Program 요건 충족 후 신청",
        "notes": "요건과 심사는 변동 가능하며 승인·수익을 보장하지 않음",
        "gate": "재사용·반복 콘텐츠 리스크와 저작권 허락 여부를 먼저 통과",
    },
    {
        "track": "제휴 마케팅",
        "when_available": "관련성 있는 도구·도서·서비스가 있을 때",
        "notes": "설명란에 광고성/제휴 고지를 명확히 표시",
        "gate": "드라마 권리와 무관한 과장 추천, 금융·투자 보장 표현 금지",
    },
    {
        "track": "디지털 제품",
        "when_available": "프롬프트 팩, 체크리스트, 리서치 템플릿이 검증된 뒤",
        "notes": "Gumroad 등 무료 시작 가능한 판매 채널을 선택 가능",
        "gate": "원작 저작물, 공식 이미지, 대사집을 상품에 포함하지 않음",
    },
    {
        "track": "브랜드 스폰서십",
        "when_available": "시청자와 조회수 데이터가 누적된 뒤",
        "notes": "협찬·광고 표시와 채널 신뢰도를 우선",
        "gate": "시청자를 오도하는 AI 장면, 허위 성과, 미표시 광고 금지",
    },
]

POLICY_SOURCES = [
    {
        "name": "YouTube Partner Program eligibility",
        "url": "https://support.google.com/youtube/answer/72851",
        "note": "YPP 가입 요건과 신청 기준은 공식 도움말을 기준으로 확인",
    },
    {
        "name": "YouTube channel monetization policies",
        "url": "https://support.google.com/youtube/answer/1311392",
        "note": "재사용·반복 콘텐츠, 광고 친화성, 품질 원칙 검토",
    },
    {
        "name": "Altered or synthetic content disclosure",
        "url": "https://support.google.com/youtube/answer/14328491",
        "note": "AI 합성·변형 콘텐츠의 표시 필요 여부 확인",
    },
    {
        "name": "YouTube Data API quota costs",
        "url": "https://developers.google.com/youtube/v3/determine_quota_cost",
        "note": "자동 수집·업로드 작업의 무료 할당량 사용량 산정",
    },
]


def build_free_automation_plan(drama: Drama | None = None) -> dict[str, Any]:
    title = drama.title if drama is not None else "신규 드라마"
    return {
        "title": f"{title} 정책 안전 무료 자동화 플랜",
        "review_verdict": REVIEW_VERDICT,
        "guardrails": [
            "허락 전 공개 업로드 금지",
            "원본 클립·원본 음성·공식 이미지 사용 금지(별도 권리 확인 전)",
            "수익 보장·확정 CPM·과장 성과 문구 금지",
            "워터마크 우회와 약관 회피 방식 금지",
            "단순 줄거리 반복 대신 원본 해설·맥락·분석을 포함",
            "AI 합성·변형 콘텐츠는 공개 전 표시 필요 여부 확인",
            "사람 검수와 라이선스 승인 후에만 공개 예약",
        ],
        "tools": [asdict(tool) for tool in FREE_TOOL_STACK],
        "recommended_pipeline": RECOMMENDED_PIPELINE,
        "avoid_or_manual_tools": [asdict(tool) for tool in AVOID_OR_MANUAL_TOOLS],
        "monetization_tracks": MONETIZATION_TRACKS,
        "policy_sources": POLICY_SOURCES,
        "prompts": {
            "system": FREE_AUTOMATION_SYSTEM_PROMPT,
            "script": FREE_AUTOMATION_SCRIPT_PROMPT,
            "title": FREE_AUTOMATION_TITLE_PROMPT.format(title=title),
        },
        "workflow": [
            "트렌드 키워드와 경쟁 채널 표본 수집",
            "드라마 등록 및 권리자 허락 요청 자동 발송",
            "무료 LLM/프롬프트로 제목·대본·쇼츠 후보와 원본 해설 관점 생성",
            "edge-tts로 내레이션 생성",
            "권리 확인 가능한 소재와 FFmpeg로 무클립 비공개 초안 렌더",
            "사람 검수·라이선스·소스 권리·AI 표시 필요 여부 체크",
            "YouTube 비공개 업로드 후 공개 게이트 통과 시 예약",
        ],
    }
