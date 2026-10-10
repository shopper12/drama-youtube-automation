from contextlib import asynccontextmanager
import os
import secrets

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from .routers import compliance, content_automation, dramas, media, licenses, rights, scripts, trends, uploads, videos


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .workers.scheduler import scheduler
    from .services.youtube_gateway_factory import configure_youtube_gateway

    configure_youtube_gateway()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Unified Media Automation",
    version="0.2.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Existing rights / publishing routes must not be editable by unauthenticated users.
# The separate content-automation webhook is unchanged for backward compatibility.
@app.middleware("http")
async def require_admin_for_drama_mutations(request: Request, call_next):
    protected = ("/dramas", "/rights", "/licenses", "/scripts",
                 "/videos", "/uploads", "/compliance", "/media")
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path.startswith(protected):
        expected = os.getenv("MEDIA_ADMIN_TOKEN", "")
        if not expected:
            return JSONResponse({"detail": "MEDIA_ADMIN_TOKEN is not configured"}, status_code=503)
        provided = request.headers.get("X-Media-Admin-Token", "")
        if not provided or not secrets.compare_digest(provided, expected):
            return JSONResponse({"detail": "Admin authorization required"}, status_code=401)
    return await call_next(request)


app.include_router(dramas.router)
app.include_router(rights.router)
app.include_router(licenses.router)
app.include_router(compliance.router)
app.include_router(trends.router)
app.include_router(scripts.router)
app.include_router(videos.router)
app.include_router(uploads.router)
app.include_router(content_automation.router)
app.include_router(media.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
