from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr

from .enums import ProductionStatus, PublicGate, RightsHolderRole, RightsStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DramaCreate(BaseModel):
    title: str
    original_title: str | None = None
    country: str | None = None
    platform: str | None = None
    episode_count: int | None = None
    source_memo: str | None = None


class DramaRead(DramaCreate, ORMModel):
    id: int
    rights_status: RightsStatus
    production_status: ProductionStatus
    public_gate: PublicGate
    human_review_approved: bool
    license_expired: bool
    source_rights_check: bool
    license_terms: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class DramaUpdate(BaseModel):
    title: str | None = None
    original_title: str | None = None
    country: str | None = None
    platform: str | None = None
    episode_count: int | None = None
    source_memo: str | None = None
    source_rights_check: bool | None = None
    license_terms: dict[str, Any] | None = None


class RightsHolderCreate(BaseModel):
    drama_id: int
    company_name: str
    role: RightsHolderRole
    contact_email: EmailStr | None = None
    source_url: str | None = None
    verified_status: bool = False
    memo: str | None = None


class RightsHolderRead(RightsHolderCreate, ORMModel):
    id: int


class LicenseReply(BaseModel):
    reply_raw_text: str


class LicenseApproval(BaseModel):
    human_approved: bool
    license_terms: dict[str, Any] | None = None


class LicenseRequestRead(ORMModel):
    id: int
    drama_id: int
    rights_holder_id: int | None
    sent_at: datetime | None
    reminder_1_at: datetime | None
    reminder_2_at: datetime | None
    replied_at: datetime | None
    reply_raw_text: str | None
    reply_summary: str | None
    status: RightsStatus
    human_approved: bool
    memo: str | None
