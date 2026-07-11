from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..services.content_automation_service import (
    apply_decision,
    build_assets,
    generate_candidates,
    list_queue,
    load_strategy,
    weekly_report,
)


router = APIRouter(prefix="/content-automation", tags=["content-automation"])


class GenerateCandidatesRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)
    category: str | None = None


class DecisionRequest(BaseModel):
    decision: str
    memo: str | None = None


@router.get("/strategy")
async def strategy() -> dict[str, Any]:
    try:
        return load_strategy()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/candidates/generate")
async def candidates_generate(payload: GenerateCandidatesRequest) -> dict[str, Any]:
    try:
        items = generate_candidates(limit=payload.limit, category=payload.category)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"generated": len(items), "items": items}


@router.get("/queue")
async def queue(status: str | None = Query(default=None)) -> dict[str, Any]:
    items = list_queue(status=status)
    return {"count": len(items), "items": items}


@router.post("/queue/{candidate_id}/decision")
async def queue_decision(candidate_id: str, payload: DecisionRequest) -> dict[str, Any]:
    try:
        return apply_decision(candidate_id, payload.decision, payload.memo)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/assets/{candidate_id}/build")
async def assets_build(candidate_id: str) -> dict[str, Any]:
    try:
        return build_assets(candidate_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/report")
async def report() -> dict[str, Any]:
    return weekly_report()
