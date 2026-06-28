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


def test_plan_rejects_watermark_workarounds_and_guaranteed_income_claims():
    plan = build_free_automation_plan()
    rejected = plan["review_verdict"]["rejected"]
    assert any("워터마크" in item for item in rejected)
    assert any("월 수익 사례" in item for item in rejected)
    assert "월 $10,000" not in str(plan)
    assert "월 $20,000" not in str(plan)


def test_plan_includes_policy_sources_and_originality_requirements():
    plan = build_free_automation_plan()
    source_names = {source["name"] for source in plan["policy_sources"]}
    script_prompt = plan["prompts"]["script"]
    assert "YouTube Partner Program eligibility" in source_names
    assert "YouTube channel monetization policies" in source_names
    assert "Altered or synthetic content disclosure" in source_names
    assert "original_angle" in script_prompt
    assert "commentary_blocks" in script_prompt
    assert "줄거리 80%" not in script_prompt
