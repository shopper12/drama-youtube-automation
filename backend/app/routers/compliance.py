from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services.compliance_service import ComplianceMode, compliance_check

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/{project_id}/check")
async def check_compliance(
    project_id: int,
    mode: ComplianceMode,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await compliance_check(project_id, mode, db)
    await db.commit()
    return {
        "allowed": result.allowed,
        "gate": result.gate.value,
        "reason": result.reason,
    }
