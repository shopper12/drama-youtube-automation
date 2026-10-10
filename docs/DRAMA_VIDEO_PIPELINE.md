# Drama Video-to-YouTube Pipeline — Implementation Architecture

## Goal
Build factual *episode-aware* Korean drama recaps from authorized source files. Preserve a separate licensing track: email and script preparation may proceed while waiting, but using copyrighted footage in exports or making a video public requires verified rights and human approval.

## Current live paths
```
POST /dramas
        |-- VideoProject(IDEA) immediately
        |-- RightsHolder verification -> LicenseRequest(NOT_SENT|SENT)
        +-- source file intake (media API)
              -> VideoSource(UPLOADED|QUEUED)
              -> Gemini Files API / multimodal scene understanding
              -> validated scene timestamps, event summaries, confidence
              -> VideoProject.scene_plan (per source episode, chronological)
              -> VideoProject.script + narration_segments (factual outline, review required)
              -> ElevenLabs or Naver CLOVA TTS + timed SRT
              -> FFmpeg local preview
                    |-- licensed source scenes: approved silent roughcut + narration
                    |-- no clip rights: self-produced monochrome graphic + narration
              -> private draft upload (existing /uploads service)
              -> compliance gate, human review, publication
```

## Implemented backend layout
| File | Responsibility |
|---|---|
| `models.py` | SourceVideo model linked to Drama; source status and analysis JSON |
| `alembic/versions/0002_video_sources.py` | Explicit source table migration |
| `routers/media.py` | Authenticated MP4/MOV uploads, async analysis, timeline, storyboarding, voice/roughcut/draft |
| `services/media_pipeline_service.py` | Streaming disk import, SHA256, ffprobe validation, persistent scene links, licensed roughcut |
| `services/scene_analyzer_service.py` | Gemini Files + interactions API and bounded, validated timeline parsing |
| `services/narration_pipeline_service.py` | Real per-segment TTS, ffprobe-aligned subtitles, FFmpeg narrated draft |
| `services/tts_service.py` | ElevenLabs / CLOVA adapters; draft mode fails closed |
| `frontend/src/app/media/page.tsx` | Episode ingest/status/timeline/production controls |
| `workers/scheduler.py` | Reclaim queued scene analysis and existing license/trend/YouTube schedule jobs |
| `main.py` | Admin authentication for all drama write endpoints |
| `tests/test_scene_pipeline.py` | Scene time, overlap, selection, truthful storyboard, license gate |

## Environment and startup
From repository root, copy `.env.example` to `.env` and configure:
```dotenv
MEDIA_ADMIN_TOKEN=<unique-long-random-secret>
GEMINI_API_KEY=<gemini-api-key>
GEMINI_VIDEO_MODEL=gemini-3.8-flash
MEDIA_STORAGE_ROOT=./storage/drama_media
AUTO_ANALYZE_ON_UPLOAD=false
AUTO_BUILD_STORYBOARD=true
TTS_PROVIDER=clova
CLOVA_CLIENT_ID=<ncloud-client-id>
CLOVA_CLIENT_SECRET=<ncloud-client-secret>
CLOVA_VOICE=nara
EMAIL_PROVIDER=log
```
For ElevenLabs, set `TTS_PROVIDER=elevenlabs`, `ELEVENLABS_API_KEY`,
`ELEVENLABS_VOICE_ID`, optionally `ELEVENLABS_MODEL`.

```bash
docker compose up --build
# run after setup: http://localhost:3000/media
# API documentation: http://localhost:8000/docs
# Python tests: cd backend && python -m pytest -q
```
**Important:** New `/media` API and all drama-mutating routes require the
`X-Media-Admin-Token` header; an unset token blocks writes.
The bundled Docker volume must retain `/app/storage` and database state.

## Upload/analyze/produce sequence
1. Add a drama via `POST /dramas` or the existing administration API.
2. Register and verify the actual rights-holder contact address (do not guess email).
3. On the **AI 영상 제작** screen, supply token, drama, episode number, authorized MP4/MOV and check the *permission to send footage for analysis* declaration. This authorization **does not** constitute YouTube redistribution rights.
4. Press **원본 업로드**; server streams with size limit, writes a randomized filename, hashes SHA256, and verifies video duration through ffprobe.
5. Press **분석/재분석** (or enable AUTO_ANALYZE_ON_UPLOAD=true). Server stores PROCESSING/ANALYZED/FAILED; errors are visible. The scheduler reclaims QUEUED jobs after process restarts.
6. Gemini returns source-grounded scenes as `start_seconds,end_seconds,event,characters,importance,confidence`. Invalid or impossible timestamps are rejected; a human must verify plot accuracy.
7. Use storyboard to select within a time budget and generate factual narration segments. *This is an outline*, not a polished 20-minute prose narration.
8. Use `/media/projects/{id}/produce` to synthesize the voice, create timed SRT, and assemble a preview. If footage license is absent, the preview contains **no original footage**. With verified license, the visual roughcut uses only clips within `license_terms.max_total_clip_seconds`, `max_single_clip_seconds`, and disables source audio.
9. Existing `/uploads/{id}/private` is subject to the independent source-rights check. Existing `/uploads/{id}/schedule` and `/uploads/{id}/publish` require approved licensing and human review; never bypass.
10. **Before public release:** verify all plot claims, license scope, thumbnail/image rights, music, scene and audio timing, and YouTube monetization/reused-content policy.

### Example upload (admin key needed)
```bash
curl -X POST "http://localhost:8000/media/dramas/1/sources" \
  -H "X-Media-Admin-Token: $MEDIA_ADMIN_TOKEN" \
  -F "episode_number=1" -F "analysis_authorized=true" \
  -F "file=@episode01.mp4"
```

### Example generation
```bash
curl -X POST "http://localhost:8000/media/projects/1/produce" \
  -H "X-Media-Admin-Token: $MEDIA_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"seconds_budget":360}'
```

## Legal / technical safety
- Never infer usage permission from mere possession of a file, an outreach email, or a private YouTube upload. Gemini analysis requires operator confirmation that external processing is authorized.
- YouTube Content ID may scan private uploads. Keep original media local while approvals are pending.
- No DRM bypassing, OTT ripping, watermark removal, or copyright-claim evasion.
- Unknown metadata, model failure, TTS failure and source duration mismatch fail with an explicit error. **No fake success files**.
- This MVP relies on a shared `VideoProject.scene_plan` for chronology, while SourceVideo is a per-episode audit record.
- Uploaded video files and generated material may contain personal / contract-sensitive content; protect storage, token and logs; provide a retention/deletion policy.

## Remaining production-grade work (not claimed as implemented)
1. **Editorial quality:** full-length LLM retelling with character continuity, cross-episode plot conflict checks, model grounding citations, and automated factual QA, plus manual correction UI.
2. **Advanced edit:** subtitle layout, source dialog ducking, actual cinematic transitions, image rights management, scene-level editor, horizontal and vertical cut variants.
3. **Scalable orchestration:** durable Redis/Celery queue; separate GPU/video worker, resumable multipart uploads directly to object storage, exactly-once jobs.
4. **Service operations:** verified Gmail OAuth bootstrap (a valid Gmail token must first exist), properly configured Google YouTube OAuth and real GoogleYouTubeGateway (default remains LocalYouTubeGateway, which **raises an error rather than pretending to upload**).
5. **Business analytics:** YouTube Analytics API CTR/retention/A-B thumbnail performance, quality dashboard and data-backed channel selection.
6. **Security:** user accounts/RBAC, audit trail, CSRF where cookie-based auth is added, malware scanning, expiring signed asset URLs, removal/retention controls.

See API service code and tests for exact method contracts.

### Enable real YouTube uploads (operator action required)
1. Configure Google Cloud YouTube Data API v3 and OAuth client credentials.
2. On a trusted local machine, set `YOUTUBE_CLIENT_SECRET_FILE` and `YOUTUBE_TOKEN_FILE` and run `cd backend && python scripts/init_youtube_oauth.py`. Request the `youtube` OAuth scope because changing publication status uses `videos.update` in addition to `videos.insert`.
3. Keep the OAuth token outside the repository, mounted securely into the backend container, and set `YOUTUBE_PROVIDER=google` plus `YOUTUBE_TOKEN_FILE=/path/in/container`.
4. Uploaded videos are private by default. Published videos require existing `compliance_check` plus all human approvals. A YouTube API project may require platform verification to enable public scheduling.

## Optional OpusClip ClipAnything (explicit paid opt-in)
Set `OPUSCLIP_API_KEY`, then `POST /media/projects/{id}/shorts/opusclip` with
`{"source_url":"https://operator-controlled-source.example/video.mp4","confirm_paid_processing":true}`.
The request is **blocked unless** the underlying drama is approved, human-reviewed,
source_rights_check passes, and `license_terms.allow_external_processing=true`.
It sends the supplied HTTPS URL to an external paid API; the system does not automatically
upload files or publish the generated clip. Query clips using
`GET /media/opusclip/{opus_project_id}/clips`, then manually verify and route
approved Shorts through existing YouTube publication compliance.
API reference: https://github.com/opus-pro/opus-skills/blob/main/skills/opusclip/references/api-reference.md
