from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..enums import PublicGate, RightsStatus
from ..models import LicenseRequest, utcnow
from ..schemas import LicenseApproval, LicenseReply, LicenseRequestRead

router = APIRouter(prefix="/licenses", tags=["licenses"])


@router.get("", response_model=list[LicenseRequestRead])
async def list_license_requests(
    db: AsyncSession = Depends(get_db),
) -> list[LicenseRequest]:
    query = select(LicenseRequest).order_by(LicenseRequest.id.desc())
    return list((await db.scalars(query)).all())


@router.post("/{request_id}/reply", response_model=LicenseRequestRead)
async def record_reply(
    request_id: int,
    payload: LicenseReply,
    db: AsyncSession = Depends(get_db),
) -> LicenseRequest:
    query = (
        select(LicenseRequest)
        .where(LicenseRequest.id == request_id)
        .options(selectinload(LicenseRequest.drama))
    )
    request = (await db.execute(query)).scalar_one_or_none()
    if request is None:
        raise HTTPException(404, "License request not found")
    from ..services.email_service import summarize_reply

    request.reply_raw_text = payload.reply_raw_text
    request.reply_summary = await summarize_reply(payload.reply_raw_text)
    request.replied_at = utcnow()
    request.status = RightsStatus.REPLIED
    request.drama.rights_status = RightsStatus.REPLIED
    await db.commit()
    await db.refresh(request)
    return request


@router.post("/{request_id}/approval", response_model=LicenseRequestRead)
async def approve_license(
    request_id: int,
    payload: LicenseApproval,
    db: AsyncSession = Depends(get_db),
) -> LicenseRequest:
    query = (
        select(LicenseRequest)
        .where(LicenseRequest.id == request_id)
        .options(selectinload(LicenseRequest.drama))
    )
    request = (await db.execute(query)).scalar_one_or_none()
    if request is None:
        raise HTTPException(404, "License request not found")
    request.human_approved = payload.human_approved
    if payload.human_approved:
        request.status = RightsStatus.APPROVED
        request.drama.human_review_approved = True
        request.drama.rights_status = RightsStatus.APPROVED
        request.drama.license_terms = payload.license_terms
        request.drama.public_gate = (
            PublicGate.ALLOWED
            if request.drama.source_rights_check
            else PublicGate.BLOCKED_SOURCE_RIGHTS
        )
    await db.commit()
    await db.refresh(request)
    return request


@router.post("/{request_id}/reject", response_model=LicenseRequestRead)
async def reject_license(
    request_id: int, db: AsyncSession = Depends(get_db)
) -> LicenseRequest:
    query = (
        select(LicenseRequest)
        .where(LicenseRequest.id == request_id)
        .options(selectinload(LicenseRequest.drama))
    )
    request = (await db.execute(query)).scalar_one_or_none()
    if request is None:
        raise HTTPException(404, "License request not found")
    request.status = RightsStatus.REJECTED
    request.human_approved = False
    request.drama.rights_status = RightsStatus.REJECTED
    request.drama.human_review_approved = False
    request.drama.public_gate = PublicGate.BLOCKED_REJECTED
    await db.commit()
    await db.refresh(request)
    return request
