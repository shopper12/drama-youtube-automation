import pytest

from app.enums import PublicGate, RightsStatus
from app.models import Drama, VideoProject
from app.services.compliance_service import compliance_check


async def make_project(db, **drama_values) -> VideoProject:
    drama = Drama(title="Test Drama", **drama_values)
    project = VideoProject(drama=drama)
    db.add(project)
    await db.commit()
    return project


@pytest.mark.asyncio
async def test_private_draft_allowed_when_source_check_passes(db):
    project = await make_project(db, source_rights_check=True)
    result = await compliance_check(project.id, "private_draft", db)
    assert result.allowed is True
    assert result.gate == PublicGate.ALLOWED


@pytest.mark.asyncio
async def test_private_draft_blocks_unlicensed_source_media(db):
    project = await make_project(
        db, source_rights_check=False, rights_status=RightsStatus.SENT
    )
    result = await compliance_check(project.id, "private_draft", db)
    assert result.gate == PublicGate.BLOCKED_SOURCE_RIGHTS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("values", "gate"),
    [
        ({"rights_status": RightsStatus.REJECTED}, PublicGate.BLOCKED_REJECTED),
        ({"rights_status": RightsStatus.SENT}, PublicGate.BLOCKED_NO_LICENSE),
        (
            {
                "rights_status": RightsStatus.APPROVED,
                "human_review_approved": False,
            },
            PublicGate.BLOCKED_NEEDS_REVIEW,
        ),
        (
            {
                "rights_status": RightsStatus.APPROVED,
                "license_expired": True,
            },
            PublicGate.BLOCKED_LICENSE_EXPIRED,
        ),
    ],
)
async def test_publish_blocking_gates(db, values, gate):
    project = await make_project(db, source_rights_check=True, **values)
    result = await compliance_check(project.id, "publish_now", db)
    assert result.allowed is False
    assert result.gate == gate


@pytest.mark.asyncio
async def test_publish_allowed_when_all_checks_pass(db):
    project = await make_project(
        db,
        source_rights_check=True,
        rights_status=RightsStatus.APPROVED,
        human_review_approved=True,
    )
    result = await compliance_check(project.id, "publish_now", db)
    assert result.allowed is True
    assert result.gate == PublicGate.ALLOWED
