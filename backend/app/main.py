from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import automation, compliance, dramas, licenses, rights, scripts, trends, uploads, videos


def cors_origins() -> list[str]:
    origins = {
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    }
    configured = os.getenv("CORS_ALLOW_ORIGINS", "")
    origins.update(origin.strip() for origin in configured.split(",") if origin.strip())
    frontend_hostname = os.getenv("FRONTEND_EXTERNAL_HOSTNAME")
    if frontend_hostname:
        origins.add(f"https://{frontend_hostname}")
    return sorted(origins)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .workers.scheduler import scheduler

    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Drama YouTube Automation",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(automation.router)
app.include_router(dramas.router)
app.include_router(rights.router)
app.include_router(licenses.router)
app.include_router(compliance.router)
app.include_router(trends.router)
app.include_router(scripts.router)
app.include_router(videos.router)
app.include_router(uploads.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
