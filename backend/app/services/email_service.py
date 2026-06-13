from __future__ import annotations

import asyncio
import base64
import os
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..enums import RightsStatus
from ..models import Drama, LicenseRequest, RightsHolder, utcnow
from ..prompts.email_prompt import EMAIL_PROMPT


@dataclass
class OutgoingEmail:
    to: str
    subject: str
    body: str


class EmailSender(ABC):
    @abstractmethod
    async def send(self, message: OutgoingEmail) -> str:
        raise NotImplementedError


class SMTPEmailSender(EmailSender):
    async def send(self, message: OutgoingEmail) -> str:
        def _send() -> str:
            email = EmailMessage()
            email["From"] = os.environ["SMTP_FROM"]
            email["To"] = message.to
            email["Subject"] = message.subject
            email.set_content(message.body)
            with smtplib.SMTP(
                os.getenv("SMTP_HOST", "smtp.gmail.com"),
                int(os.getenv("SMTP_PORT", "587")),
            ) as client:
                client.starttls()
                client.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
                client.send_message(email)
            return email["Message-ID"] or "smtp-sent"

        return await asyncio.to_thread(_send)


class GmailAPIEmailSender(EmailSender):
    def __init__(self, service):
        self.service = service

    async def send(self, message: OutgoingEmail) -> str:
        email = EmailMessage()
        email["To"] = message.to
        email["Subject"] = message.subject
        email.set_content(message.body)
        raw = base64.urlsafe_b64encode(email.as_bytes()).decode()
        response = await asyncio.to_thread(
            lambda: self.service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )
        return response["id"]


class LoggingEmailSender(EmailSender):
    async def send(self, message: OutgoingEmail) -> str:
        return f"logged:{message.to}"


def get_email_sender() -> EmailSender:
    if os.getenv("EMAIL_PROVIDER", "log") == "smtp":
        return SMTPEmailSender()
    return LoggingEmailSender()


def build_permission_email(drama: Drama, holder: RightsHolder) -> OutgoingEmail:
    channel = os.getenv("YOUTUBE_CHANNEL_NAME", "드라마 시간순삭")
    body = EMAIL_PROMPT.format(
        channel_name=channel,
        drama_title=drama.title,
        monetized="예정",
    ).strip()
    return OutgoingEmail(
        to=holder.contact_email or os.getenv("RIGHTS_FALLBACK_EMAIL", ""),
        subject=f"[사용 허락 요청] {drama.title} 줄거리 요약 영상",
        body=body,
    )


async def discover_rights_holder(drama: Drama, db: AsyncSession) -> RightsHolder:
    query = select(RightsHolder).where(RightsHolder.drama_id == drama.id)
    holder = (await db.execute(query)).scalar_one_or_none()
    if holder is None:
        holder = RightsHolder(
            drama_id=drama.id,
            company_name=drama.platform or "권리자 확인 필요",
            role="ott" if drama.platform else "producer",
            contact_email=os.getenv("RIGHTS_FALLBACK_EMAIL"),
            memo="자동 탐색 결과를 운영자가 검증해야 합니다.",
        )
        db.add(holder)
        await db.flush()
    return holder


async def register_and_send_license_request(
    drama_id: int, db: AsyncSession
) -> LicenseRequest:
    drama = await db.get(Drama, drama_id)
    if drama is None:
        raise ValueError(f"Drama {drama_id} not found")
    holder = await discover_rights_holder(drama, db)
    request = LicenseRequest(
        drama_id=drama.id,
        rights_holder_id=holder.id,
        status=RightsStatus.NOT_SENT,
    )
    db.add(request)
    await db.flush()
    message = build_permission_email(drama, holder)
    await get_email_sender().send(message)
    request.sent_at = utcnow()
    request.status = RightsStatus.SENT
    drama.rights_status = RightsStatus.SENT
    await db.flush()
    from .notification_service import notify

    await notify("메일 발송 완료", f"{drama.title} 저작권 허락 요청 발송")
    return request


async def summarize_reply(text: str) -> str:
    normalized = " ".join(text.split())
    return normalized[:500]


async def send_due_reminders(db: AsyncSession) -> int:
    from datetime import timedelta

    now = utcnow()
    query = (
        select(LicenseRequest)
        .where(LicenseRequest.status == RightsStatus.SENT)
        .options(
            selectinload(LicenseRequest.drama),
            selectinload(LicenseRequest.rights_holder),
        )
    )
    requests = list((await db.scalars(query)).all())
    sent = 0
    auto_send = os.getenv("AUTO_REMINDER_ENABLED", "false").lower() == "true"
    sender = get_email_sender()
    for request in requests:
        age = now - request.sent_at if request.sent_at else timedelta()
        due_field = None
        if age >= timedelta(days=7) and request.reminder_2_at is None:
            due_field = "reminder_2_at"
        elif age >= timedelta(days=3) and request.reminder_1_at is None:
            due_field = "reminder_1_at"
        if due_field is None:
            continue
        if auto_send and request.rights_holder:
            message = build_permission_email(request.drama, request.rights_holder)
            message.subject = f"[리마인더] {message.subject}"
            await sender.send(message)
        setattr(request, due_field, now)
        sent += 1
    await db.flush()
    return sent
