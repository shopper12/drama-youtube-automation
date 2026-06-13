from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import compliance, dramas, licenses, rights, scripts, trends, uploads, videos


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
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
