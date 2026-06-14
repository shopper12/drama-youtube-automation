from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..enums import PublicGate, RightsStatus
from ..models import ComplianceLog, VideoProject, utcnow


ComplianceMode = Literal["private_draft", "schedule_publish", "publish_now"]


@dataclass(frozen=True)
class ComplianceResult:
    allowed: bool
    gate: PublicGate
    reason: str


class ComplianceBlockedError(RuntimeError):
    def __init__(self, result: ComplianceResult):
        self.result = result
        super().__init__(f"{result.gate.value}: {result.reason}")


async def _persist_result(
    project: VideoProject,
    mode: ComplianceMode,
    result: ComplianceResult,
    db: AsyncSession,
) -> ComplianceResult:
    checked_at = utcnow()
    await db.flush()
    entries = list(project.compliance_log or [])
    entries.append(
        {
            "checked_at": checked_at.isoformat(),
            "mode": mode,
            "gate": result.gate.value,
            "allowed": result.allowed,
            "reason": result.reason,
        }
    )
    project.compliance_log = entries
    if mode != "private_draft" and project.drama.public_gate != result.gate:
        project.drama.public_gate = result.gate
    db.add(
        ComplianceLog(
            project_id=project.id,
            checked_at=checked_at,
            mode=mode,
            gate=result.gate,
            allowed=result.allowed,
            reason=result.reason,
        )
    )
    await db.flush()
    return result


async def compliance_check(
    project_id: int,
    mode: ComplianceMode,
    db: AsyncSession,
) -> ComplianceResult:
    query = (
        select(VideoProject)
        .where(VideoProject.id == project_id)
        .options(selectinload(VideoProject.drama))
    )
    project = (await db.execute(query)).scalar_one_or_none()
    if project is None:
        raise ValueError(f"VideoProject {project_id} not found")

    drama = project.drama
    if mode == "private_draft":
        result = (
            ComplianceResult(True, PublicGate.ALLOWED, "Source rights check passed")
            if drama.source_rights_check
            else ComplianceResult(
                False,
                PublicGate.BLOCKED_SOURCE_RIGHTS,
                "Draft contains source media without verified permission",
            )
        )
        return await _persist_result(project, mode, result, db)

    if drama.rights_status == RightsStatus.REJECTED:
        result = ComplianceResult(
            False, PublicGate.BLOCKED_REJECTED, "Rights request was rejected"
        )
    elif drama.rights_status != RightsStatus.APPROVED:
        result = ComplianceResult(
            False, PublicGate.BLOCKED_NO_LICENSE, "License is not approved"
        )
    elif drama.license_expired:
        result = ComplianceResult(
            False, PublicGate.BLOCKED_LICENSE_EXPIRED, "License has expired"
        )
    elif not drama.human_review_approved:
        result = ComplianceResult(
            False,
            PublicGate.BLOCKED_NEEDS_REVIEW,
            "Human approval is required",
        )
    elif not drama.source_rights_check:
        result = ComplianceResult(
            False,
            PublicGate.BLOCKED_SOURCE_RIGHTS,
            "Source rights check failed",
        )
    else:
        result = ComplianceResult(True, PublicGate.ALLOWED, "All checks passed")

    return await _persist_result(project, mode, result, db)
