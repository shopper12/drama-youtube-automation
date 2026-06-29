# Drama YouTube Automation MVP

드라마 줄거리 요약 채널의 저작권 요청, 제작 초안, 비공개 업로드, 공개 게이트를 관리하는 FastAPI + Next.js MVP입니다.

## 설치

Python 3.12와 FFmpeg, Node.js 20 이상을 준비합니다.

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

`.env.example`을 `.env`로 복사하고 Gmail/SMTP, YouTube, LLM(OpenAI 또는 Gemini), TTS(ElevenLabs 또는 Clova), Telegram 또는 Discord 값을 설정합니다. 기본 `EMAIL_PROVIDER=log`는 실제 메일 대신 개발 로그 어댑터를 사용합니다.

## Alembic

```bash
cd backend
alembic upgrade head
```

새 마이그레이션은 `alembic revision --autogenerate -m "message"`로 생성합니다.

## Gmail API OAuth2

Google Cloud Console에서 Gmail API를 활성화하고 OAuth 데스크톱 클라이언트를 생성합니다. 내려받은 JSON 경로를 `GMAIL_CLIENT_SECRET_FILE`에, 최초 동의 후 생성할 토큰 경로를 `GMAIL_TOKEN_FILE`에 설정합니다. 운영 전송은 Gmail API 어댑터를 주 구현으로 사용하고 장애 시 `EMAIL_PROVIDER=smtp`로 전환합니다.

## YouTube Data API v3

Google Cloud 프로젝트에서 YouTube Data API v3를 활성화하고 OAuth 클라이언트를 생성합니다. `YOUTUBE_CLIENT_SECRET_FILE`, `YOUTUBE_TOKEN_FILE`을 설정하며 업로드 계정에 채널 권한이 있어야 합니다. 트렌드의 `search.list` 결과는 전체 인기 순위가 아니라 **검색어 기반 인기 표본**입니다. 조회수와 길이는 `videos.list(part=["statistics","contentDetails"])`로 별도 조회해야 합니다.

## 저작권 게이트 정책

- 드라마 등록 즉시 허락 요청을 발송하고, 답변 대기 중 대본/TTS/SRT/썸네일/무클립 초안을 병렬 제작합니다.
- 허락 전 private draft는 원본 클립, 원본 음성, 공식 이미지가 없거나 별도 권리가 확인되어 `source_rights_check=true`인 경우만 가능합니다.
- 허락 전 공개와 공개 예약은 금지합니다. `APPROVED`, 사람 승인, 유효 라이선스, 소스 권리 검사를 모두 통과해야 합니다.
- 예약 시각은 현재 UTC보다 60분을 초과해 미래여야 합니다. 최초 업로드에는 `publishAt`을 넣지 않습니다.
- APScheduler가 매시간 공개 1시간 전 컴플라이언스를 재검증합니다. 실패하면 예약을 취소하고 알림을 보냅니다.

## SQLite에서 PostgreSQL로 전환

코드 변경 없이 `DATABASE_URL`만 변경합니다.

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/drama
```

변경 후 `alembic upgrade head`를 실행합니다.

## 무료 도구 자동 제작 플랜

`GET /automation/free-tool-plan`은 YouTube 드라마 요약 채널을 무료/프리티어 도구로 운영하기 위한 도구 스택, 프롬프트, 워크플로, 수익화 검토 포인트를 반환합니다. 드라마별 플랜은 `GET /automation/free-tool-plan/{drama_id}`에서 확인합니다.

기본 스택은 YouTube Data API 무료 할당량, Gemini 무료 티어 또는 로컬 LLM, edge-tts, Whisper.cpp/faster-whisper, Canva 무료·Pexels·Pixabay, FFmpeg, Discord Webhook/Telegram Bot입니다. 모든 단계는 기존 저작권 게이트 정책을 따라 허락 전 공개 업로드와 원본 클립·공식 이미지 사용을 차단합니다.

이 플랜은 "완전 자동 수익 보장" 구조가 아닙니다. Pictory, Runway, ElevenLabs 무료 플랜, CapCut, TubeBuddy, VidIQ처럼 무료 조건·워터마크·상업 이용 조건이 바뀔 수 있는 SaaS는 선택 또는 수동 도구로만 분류합니다. 특히 워터마크를 줌인으로 가리는 방식, 수익 보장 문구, 반복 템플릿 대량 업로드, 권리 확인 없는 원본 소재 사용은 금지 항목으로 반환됩니다.

수익화 검토는 YouTube Partner Program, 제휴 마케팅, 디지털 제품, 브랜드 스폰서십으로 나누되 승인·수익을 보장하지 않습니다. 공개 전에는 YouTube 수익화 정책, 재사용·반복 콘텐츠 리스크, AI 합성/변형 콘텐츠 표시 필요 여부, 제휴/광고 고지를 사람이 확인해야 합니다.

## 인기 영상 자동 제작/게시

`POST /automation/top-video/run`은 최근 YouTube 드라마 요약/결말 표본에서 조회수 1위 소재를 고르고, 무클립 대본·TTS·자막·렌더 초안을 만든 뒤 YouTube 비공개 업로드까지 실행합니다. 요청 본문은 선택 사항이며 기본값은 `{"recent_days": 30, "publish_mode": "publish_now"}`입니다.

실제 공개 게시에는 `YOUTUBE_PUBLISH_ENABLED=true`, `YOUTUBE_CLIENT_SECRET_FILE`, `YOUTUBE_TOKEN_FILE`이 필요합니다. 값이 없으면 local gateway로 동작해 실수로 공개 업로드하지 않습니다. 공개 게시와 예약 게시는 기존 게이트와 동일하게 라이선스 승인, 사람 검수, 소스 권리 확인을 모두 통과한 경우에만 진행됩니다.

렌더에는 FFmpeg가 필요합니다. PATH에 없으면 `FFMPEG_BINARY`에 실행 파일 경로를 지정합니다.

## Render 클라우드 배포

루트의 `render.yaml`은 Render Blueprint용 설정입니다. GitHub 저장소를 Render Dashboard의 **New > Blueprint**로 연결하면 다음 리소스가 생성됩니다.

- `drama-youtube-api`: FastAPI 백엔드 Docker web service
- `drama-youtube-admin`: Next.js 관리자 Docker web service
- `drama-youtube-db`: Render Postgres database

초기 생성 화면에서 `sync: false`로 표시된 비밀값을 입력합니다. 최소 실행에는 `YOUTUBE_API_KEY`만 있으면 되고, 실제 YouTube 공개 업로드까지 켜려면 `YOUTUBE_PUBLISH_ENABLED=true`, `YOUTUBE_CLIENT_SECRET_JSON`, `YOUTUBE_TOKEN_JSON`을 추가합니다. `YOUTUBE_TOKEN_JSON`은 refresh token이 포함된 authorized user JSON이어야 합니다.

## MVP 실행

```bash
cd backend
uvicorn app.main:app --reload
```

```bash
cd frontend
npm run dev
```

또는 루트에서 `docker compose up --build`를 실행합니다. API 문서는 `http://localhost:8000/docs`, 관리자 화면은 `http://localhost:3000`입니다.

## 테스트

```bash
cd backend
pytest -v
```

FFmpeg 렌더 테스트를 로컬에서 실행하려면 FFmpeg가 PATH에 있어야 합니다.
