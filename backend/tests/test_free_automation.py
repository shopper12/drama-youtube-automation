from app.models import Drama
from app.services.free_automation_service import FREE_TOOL_STACK, build_free_automation_plan


def test_free_tool_stack_uses_only_free_or_free_tier_tools():
    names = {tool.tool for tool in FREE_TOOL_STACK}
    assert "FFmpeg" in names
    assert "edge-tts" in names
    assert "YouTube Data API" in names


def test_free_automation_plan_contains_prompts_and_rights_guardrails():
    plan = build_free_automation_plan(Drama(title="비밀의 집"))
    assert "비밀의 집" in plan["title"]
    assert "script" in plan["prompts"]
    assert any("허락 전 공개" in item for item in plan["guardrails"])
    assert any("원본 클립" in item for item in plan["guardrails"])
