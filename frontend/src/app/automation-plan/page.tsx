import { PageShell } from "../../components/PageShell";

const verdict = {
  summary:
    "무료 도구 조합은 가능하지만, 수익 보장·워터마크 우회·반복 요약 대량 생산은 제외합니다.",
  good: [
    "얼굴 없는 채널 운영, 니치 선정, 대본·TTS·자막·렌더 자동화는 현재 MVP와 잘 맞습니다.",
    "한국 드라마를 영어권 시청자에게 해설하는 방향은 차별화 포인트가 있습니다.",
    "YouTube Data API, edge-tts, FFmpeg, 로컬 STT처럼 반복 실행 가능한 무료 도구를 중심에 둡니다."
  ],
  risky: [
    "Pictory, Runway, ElevenLabs, TubeBuddy, VidIQ 등은 무료 조건이 바뀔 수 있어 선택 도구로만 둡니다.",
    "단순 줄거리 재가공이나 반복 슬라이드쇼는 재사용·반복 콘텐츠로 판단될 위험이 있습니다.",
    "AI 합성 장면, 인물 유사 이미지, 과장된 썸네일은 공개 전 표시·오인 가능성을 확인해야 합니다."
  ],
  rejected: [
    "월 수익 사례를 보장처럼 제시하는 문구",
    "CapCut 또는 다른 도구의 워터마크를 줌인으로 가리는 우회",
    "권리 확인 없는 원본 클립·공식 이미지·원본 음성 사용",
    "사람 검수 없는 공개 예약과 반복 템플릿 대량 업로드"
  ]
};

const tools = [
  ["기획/트렌드", "YouTube Data API 무료 할당량", "검색어 기반 인기 표본 수집"],
  ["대본", "Gemini 무료 티어 또는 로컬 LLM", "원본 해설·맥락이 있는 초안 생성"],
  ["음성", "edge-tts", "무료 Microsoft Edge TTS 음성 합성"],
  ["자막", "Whisper.cpp 또는 faster-whisper", "로컬 STT/정렬"],
  ["이미지/배경", "Canva 무료·Pexels·Pixabay", "권리 확인 가능한 배경/아이콘"],
  ["편집/렌더", "FFmpeg", "자막·이미지·음성 합성"],
  ["업로드", "YouTube Data API", "비공개 업로드 및 예약"],
  ["알림", "Discord Webhook 또는 Telegram Bot", "게이트 실패/완료 알림"]
];

const pipeline = [
  "한국 드라마 영어 해설처럼 원본 관점이 있는 니치로 제한",
  "YouTube Data API 표본과 수동 리서치로 제목 패턴·시청자 질문 검토",
  "무료 LLM 또는 로컬 LLM으로 초안을 만들고 해설·비교·맥락 블록 추가",
  "권리 확인 가능한 소재와 직접 만든 그래픽으로 무클립 화면 구성",
  "edge-tts, Whisper.cpp/faster-whisper, FFmpeg로 음성·자막·렌더 자동 생성",
  "비공개 업로드 후 저작권, AI 표시, 광고성, 사람 검수 게이트 통과 시 예약"
];

const monetization = [
  ["YPP 광고 수익", "요건 충족 후 신청. 승인·수익은 보장하지 않습니다."],
  ["제휴 마케팅", "설명란에 광고성/제휴 고지를 명확히 표시합니다."],
  ["디지털 제품", "원작 저작물·공식 이미지·대사집을 상품에 포함하지 않습니다."],
  ["브랜드 스폰서십", "협찬·광고 표시와 채널 신뢰도를 우선합니다."]
];

export default function AutomationPlanPage() {
  return (
    <PageShell
      title="Automation Plan"
      description="무료 AI 유튜브 자동화 제안을 정책 안전 기준으로 검토하고 실행 가능한 운영 플랜으로 정리합니다."
    >
      <section className="plan-band">
        <div>
          <div className="label">검토 결론</div>
          <h2>{verdict.summary}</h2>
        </div>
        <a className="text-link" href="http://localhost:8000/automation/free-tool-plan">
          API 응답 보기
        </a>
      </section>

      <section className="risk-grid">
        <VerdictColumn title="채택" items={verdict.good} tone="allowed" />
        <VerdictColumn title="주의" items={verdict.risky} tone="warn" />
        <VerdictColumn title="제외" items={verdict.rejected} tone="blocked" />
      </section>

      <section className="section-block">
        <h2>추천 무료 스택</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>단계</th>
                <th>도구</th>
                <th>용도</th>
              </tr>
            </thead>
            <tbody>
              {tools.map(([stage, tool, use]) => (
                <tr key={`${stage}-${tool}`}>
                  <td>{stage}</td>
                  <td>{tool}</td>
                  <td>{use}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="two-column">
        <div className="section-block">
          <h2>운영 흐름</h2>
          <ol className="number-list">
            {pipeline.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </div>
        <div className="section-block">
          <h2>수익화 트랙</h2>
          <div className="compact-list">
            {monetization.map(([track, note]) => (
              <div key={track}>
                <strong>{track}</strong>
                <span>{note}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </PageShell>
  );
}

function VerdictColumn({
  title,
  items,
  tone
}: {
  title: string;
  items: string[];
  tone: "allowed" | "warn" | "blocked";
}) {
  return (
    <div className="plan-card">
      <span className={`badge ${tone}`}>{title}</span>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
