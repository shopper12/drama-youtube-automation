# Unified Content Automation

이 디렉터리는 기존 `shopper12/ai_media_agent`의 범용 콘텐츠 자동화 기능을 `drama-youtube-automation`에 통합한 결과입니다.

## 통합된 기능

- 수익성(EPS)·바이럴 가능성(VPS) 기반 콘텐츠 후보 점수화
- `APPROVE` / `HOLD` / `REJECT` 승인 큐
- 승인된 후보의 Naver Blog 초안과 YouTube Shorts 대본 생성
- n8n에서 호출할 수 있는 FastAPI 엔드포인트
- Naver Blog webhook 및 Meta Graph 발행 어댑터
- 기존 드라마 저작권 요청·라이선스·공개 게이트·YouTube 업로드 기능과 공존

## API

서버 실행 후 `http://localhost:8000/docs`에서 확인합니다.

```text
GET  /content-automation/strategy
POST /content-automation/candidates/generate
GET  /content-automation/queue
POST /content-automation/queue/{candidate_id}/decision
POST /content-automation/assets/{candidate_id}/build
GET  /content-automation/report
```

후보 생성 예시:

```bash
curl -X POST http://localhost:8000/content-automation/candidates/generate \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'
```

승인 예시:

```bash
curl -X POST http://localhost:8000/content-automation/queue/20260711-ai-001/decision \
  -H "Content-Type: application/json" \
  -d '{"decision": "APPROVE", "memo": "최신 가격 검증 후 발행"}'
```

## 디렉터리

```text
automation/
  config/           후보 선정·점수화 전략
  data/             승인 큐 템플릿
  n8n/workflows/    통합 API를 호출하는 n8n 템플릿
  publishers/       Naver·Meta 발행 어댑터
```

생성된 운영 데이터는 기본적으로 `storage/content_automation/`에 저장됩니다. Docker에서는 `/storage/content_automation`을 사용합니다.

## 운영 원칙

- AI가 만든 후보는 자동 공개하지 않습니다.
- `APPROVED` 후보만 발행 자산을 생성할 수 있습니다.
- 건강·금융·부동산 콘텐츠는 발행 직전 최신 근거와 법령을 다시 검증합니다.
- 드라마 원본 소재를 사용하는 경우 기존 저작권 공개 게이트를 우회하지 않습니다.
- 실제 채널 발행은 채널별 자격증명과 사람 승인을 거친 후 수행합니다.

## 원본 저장소 처리

기능 통합 기준 원본은 `shopper12/ai_media_agent`입니다. 통합 완료 후 원본 저장소는 실행 중지 및 삭제 대상으로 취급합니다.
