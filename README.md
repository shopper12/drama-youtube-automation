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

`GET /automation/free-tool-plan`은 YouTube 드라마 요약 채널을 무료/프리티어 도구로 끝까지 운영하기 위한 도구 스택, 프롬프트, 워크플로를 반환합니다. 드라마별 플랜은 `GET /automation/free-tool-plan/{drama_id}`에서 확인합니다.

기본 스택은 YouTube Data API 무료 할당량, Gemini 무료 티어 또는 로컬 LLM, edge-tts, Whisper.cpp/faster-whisper, Canva 무료·Pexels·Pixabay, FFmpeg, Discord Webhook/Telegram Bot입니다. 모든 단계는 기존 저작권 게이트 정책을 따라 허락 전 공개 업로드와 원본 클립·공식 이미지 사용을 차단합니다.

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
