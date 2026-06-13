from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .enums import ProductionStatus, PublicGate, RightsHolderRole, RightsStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Drama(TimestampMixin, Base):
    __tablename__ = "dramas"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    original_title: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100))
    platform: Mapped[str | None] = mapped_column(String(100))
    episode_count: Mapped[int | None] = mapped_column(Integer)
    source_memo: Mapped[str | None] = mapped_column(Text)
    rights_status: Mapped[RightsStatus] = mapped_column(
        Enum(RightsStatus), default=RightsStatus.NOT_SENT
    )
    production_status: Mapped[ProductionStatus] = mapped_column(
        Enum(ProductionStatus), default=ProductionStatus.IDEA
    )
    public_gate: Mapped[PublicGate] = mapped_column(
        Enum(PublicGate), default=PublicGate.BLOCKED_NO_LICENSE
    )
    human_review_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    license_expired: Mapped[bool] = mapped_column(Boolean, default=False)
    source_rights_check: Mapped[bool] = mapped_column(Boolean, default=False)
    license_terms: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    rights_holders: Mapped[list[RightsHolder]] = relationship(
        back_populates="drama", cascade="all, delete-orphan"
    )
    license_requests: Mapped[list[LicenseRequest]] = relationship(
        back_populates="drama", cascade="all, delete-orphan"
    )
    video_projects: Mapped[list[VideoProject]] = relationship(
        back_populates="drama", cascade="all, delete-orphan"
    )


class RightsHolder(Base):
    __tablename__ = "rights_holders"

    id: Mapped[int] = mapped_column(primary_key=True)
    drama_id: Mapped[int] = mapped_column(ForeignKey("dramas.id", ondelete="CASCADE"))
    company_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[RightsHolderRole] = mapped_column(Enum(RightsHolderRole))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    source_url: Mapped[str | None] = mapped_column(Text)
    verified_status: Mapped[bool] = mapped_column(Boolean, default=False)
    memo: Mapped[str | None] = mapped_column(Text)

    drama: Mapped[Drama] = relationship(back_populates="rights_holders")
    license_requests: Mapped[list[LicenseRequest]] = relationship(
        back_populates="rights_holder"
    )


class LicenseRequest(Base):
    __tablename__ = "license_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    drama_id: Mapped[int] = mapped_column(ForeignKey("dramas.id", ondelete="CASCADE"))
    rights_holder_id: Mapped[int | None] = mapped_column(
        ForeignKey("rights_holders.id", ondelete="SET NULL")
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_1_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_2_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reply_raw_text: Mapped[str | None] = mapped_column(Text)
    reply_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[RightsStatus] = mapped_column(
        Enum(RightsStatus), default=RightsStatus.NOT_SENT
    )
    human_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    memo: Mapped[str | None] = mapped_column(Text)

    drama: Mapped[Drama] = relationship(back_populates="license_requests")
    rights_holder: Mapped[RightsHolder | None] = relationship(
        back_populates="license_requests"
    )


class TrendVideo(Base):
    __tablename__ = "trend_videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    channel_title: Mapped[str] = mapped_column(String(255))
    view_count: Mapped[int] = mapped_column(BigInteger, default=0)
    like_count: Mapped[int] = mapped_column(BigInteger, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    keyword_query: Mapped[str] = mapped_column(String(255))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class VideoProject(TimestampMixin, Base):
    __tablename__ = "video_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    drama_id: Mapped[int] = mapped_column(ForeignKey("dramas.id", ondelete="CASCADE"))
    title_candidates: Mapped[list[str]] = mapped_column(JSON, default=list)
    thumbnail_text_candidates: Mapped[list[str]] = mapped_column(JSON, default=list)
    script: Mapped[str | None] = mapped_column(Text)
    scene_plan: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    narration_segments: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list
    )
    shorts_candidates: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list
    )
    tts_file_path: Mapped[str | None] = mapped_column(Text)
    subtitle_file_path: Mapped[str | None] = mapped_column(Text)
    thumbnail_draft_path: Mapped[str | None] = mapped_column(Text)
    render_main_path: Mapped[str | None] = mapped_column(Text)
    render_shorts_path: Mapped[str | None] = mapped_column(Text)
    youtube_video_id: Mapped[str | None] = mapped_column(String(64))
    desired_publish_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    compliance_log: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    production_status: Mapped[ProductionStatus] = mapped_column(
        Enum(ProductionStatus), default=ProductionStatus.IDEA
    )

    drama: Mapped[Drama] = relationship(back_populates="video_projects")
    compliance_logs: Mapped[list[ComplianceLog]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ComplianceLog(Base):
    __tablename__ = "compliance_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("video_projects.id", ondelete="CASCADE")
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    mode: Mapped[str] = mapped_column(String(32))
    gate: Mapped[PublicGate] = mapped_column(Enum(PublicGate))
    allowed: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(Text)

    project: Mapped[VideoProject] = relationship(back_populates="compliance_logs")
