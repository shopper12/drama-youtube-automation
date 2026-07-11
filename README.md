# Unified Media Automation

`drama-youtube-automation`과 `ai_media_agent`의 기능을 하나로 합친 FastAPI + Next.js + n8n 콘텐츠 자동화 플랫폼입니다.

기존 드라마 줄거리 채널의 저작권 요청·제작 초안·비공개 업로드·공개 게이트 기능을 유지하면서, 범용 콘텐츠 후보 점수화·승인 큐·Naver Blog·YouTube Shorts·Meta 발행 준비 기능을 추가했습니다.

## 통합 기능

### 드라마 전용 제작·권리 관리

- 권리자 탐색 및 허락 요청
- 라이선스 상태·답변·만료 관리
- LLM 대본, TTS, SRT, 썸네일, 영상 초안
- YouTube 비공개 업로드 및 예약 공개
- 공개 직전 저작권·사람 승인·소스 권리 재검증

### 범용 콘텐츠 자동화

- 예상 수익성 점수(EPS)와 바이럴 점수(VPS) 기반 후보 생성
- `APPROVE` / `HOLD` / `REJECT` 승인 큐
- 승인된 후보의 Naver Blog 초안과 Shorts 대본 생성
- Naver Blog webhook 및 Meta Graph 발행 어댑터
- n8n 오케스트레이션 템플릿
- 주간 후보·승인 상태 보고

세부 내용은 `automation/README.md`를 참고합니다.

## 설치

Python 3.12, FFmpeg, Node.js 20 이상을 준비합니다.

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
```

```bash
cd frontend
npm install
```

## 환경 설정

`.env.example`을 `.env`로 복사하고 Gmail/SMTP, YouTube, LLM(OpenAI 또는 Gemini), TTS(ElevenLabs 또는 Clova), Telegram 또는 Discord 값을 설정합니다.

범용 콘텐츠 기능을 실제 채널과 연결하려면 다음 값도 설정합니다.

```env
NAVER_BLOG_BRIDGE_URL=
NAVER_BLOG_BRIDGE_TOKEN=
META_PAGE_ID=
META_PAGE_ACCESS_TOKEN=
```

기본 `EMAIL_PROVIDER=log`는 실제 메일 대신 개발 로그 어댑터를 사용합니다.

## 전체 스택 실행

```bash
docker compose up --build
```

- API 문서: `http://localhost:8000/docs`
- 관리자 화면: `http://localhost:3000`
- n8n: `http://localhost:5678`

n8n에서 `automation/n8n/workflows/weekly_content_pipeline.json`을 import하면 통합 API를 호출할 수 있습니다.

## 범용 콘텐츠 API

```text
GET  /content-automation/strategy
POST /content-automation/candidates/generate
GET  /content-automation/queue
POST /content-automation/queue/{candidate_id}/decision
POST /content-automation/assets/{candidate_id}/build
GET  /content-automation/report
```

예시:

```bash
curl -X POST http://localhost:8000/content-automation/candidates/generate \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'
```

## Alembic

```bash
cd backend
alembic upgrade head
```

새 마이그레이션은 `alembic revision --autogenerate -m "message"`로 생성합니다.

## Gmail API OAuth2

Google Cloud Console에서 Gmail API를 활성화하고 OAuth 데스크톱 클라이언트를 생성합니다. 내려받은 JSON 경로를 `GMAIL_CLIENT_SECRET_FILE`에, 최초 동의 후 생성할 토큰 경로를 `GMAIL_TOKEN_FILE`에 설정합니다. 운영 전송은 Gmail API 어댑터를 주 구현으로 사용하고 장애 시 `EMAIL_PROVIDER=smtp`로 전환합니다.

## YouTube Data API v3

Google Cloud 프로젝트에서 YouTube Data API v3를 활성화하고 OAuth 클라이언트를 생성합니다. `YOUTUBE_CLIENT_SECRET_FILE`, `YOUTUBE_TOKEN_FILE`을 설정하며 업로드 계정에 채널 권한이 있어야 합니다. 트렌드의 `search.list` 결과는 전체 인기 순위가 아니라 검색어 기반 인기 표본입니다. 조회수와 길이는 `videos.list(part=["statistics","contentDetails"])`로 별도 조회해야 합니다.

## 저작권·공개 게이트 정책

- 드라마 등록 즉시 허락 요청을 발송하고, 답변 대기 중 대본/TTS/SRT/썸네일/무클립 초안을 병렬 제작합니다.
- 허락 전 private draft는 원본 클립, 원본 음성, 공식 이미지가 없거나 별도 권리가 확인되어 `source_rights_check=true`인 경우만 가능합니다.
- 허락 전 공개와 공개 예약은 금지합니다. `APPROVED`, 사람 승인, 유효 라이선스, 소스 권리 검사를 모두 통과해야 합니다.
- 범용 콘텐츠 역시 승인 큐에서 `APPROVED`가 되어야 발행 자산을 생성합니다.
- 건강·금융·부동산 콘텐츠는 발행 직전 최신 사실·가격·법령을 다시 검증합니다.
- APScheduler가 매시간 공개 1시간 전 컴플라이언스를 재검증합니다. 실패하면 예약을 취소하고 알림을 보냅니다.

## SQLite에서 PostgreSQL로 전환

코드 변경 없이 `DATABASE_URL`만 변경합니다.

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/drama
```

변경 후 `alembic upgrade head`를 실행합니다.

## 개별 실행

```bash
cd backend
uvicorn app.main:app --reload
```

```bash
cd frontend
npm run dev
```

## 테스트

```bash
cd backend
pytest -v
```

FFmpeg 렌더 테스트를 로컬에서 실행하려면 FFmpeg가 PATH에 있어야 합니다.

## 저장소 통합 상태

최종 운영 저장소는 `shopper12/drama-youtube-automation`입니다. 기존 `shopper12/ai_media_agent`의 범용 콘텐츠 기능은 이 저장소의 `automation/`과 `/content-automation` API로 이전됐습니다.
