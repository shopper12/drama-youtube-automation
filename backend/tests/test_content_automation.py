import json

from app.services.content_automation_service import (
    apply_decision,
    build_assets,
    generate_candidates,
    list_queue,
    weekly_report,
)


def test_content_candidate_approval_and_asset_flow(tmp_path, monkeypatch):
    strategy = {
        "scoring": {
            "expected_profit_score": {
                "min_queue_score": 0.6,
                "weights": {
                    "affiliate_or_ad_unit_value": 0.5,
                    "search_trend_momentum": 0.5,
                },
            },
            "viral_potential_score": {
                "weights": {
                    "hook_shock_value": 0.5,
                    "relatability_score": 0.5,
                }
            },
        },
        "topic_tiers": [
            {
                "tier": 1,
                "category": "테스트",
                "title_patterns": ["검증 가능한 콘텐츠 후보"],
                "risk_level": "LOW",
                "content_rules": ["과장 금지"],
                "base_metrics": {
                    "affiliate_or_ad_unit_value": 0.8,
                    "search_trend_momentum": 0.8,
                    "hook_shock_value": 0.9,
                    "relatability_score": 0.9,
                },
            }
        ],
    }
    strategy_path = tmp_path / "strategy.json"
    strategy_path.write_text(json.dumps(strategy, ensure_ascii=False), encoding="utf-8")
    data_dir = tmp_path / "data"
    monkeypatch.setenv("CONTENT_AUTOMATION_STRATEGY", str(strategy_path))
    monkeypatch.setenv("CONTENT_AUTOMATION_DATA_DIR", str(data_dir))

    generated = generate_candidates(limit=1)
    assert len(generated) == 1
    candidate_id = generated[0]["id"]
    assert list_queue()[0]["approval_status"] == "READY_FOR_OWNER_APPROVAL"

    approved = apply_decision(candidate_id, "APPROVE", "reviewed")
    assert approved["approval_status"] == "APPROVED"

    manifest = build_assets(candidate_id)
    assert manifest["next_gate"] == "HUMAN_REVIEW_AND_CHANNEL_PUBLISH"
    assert (data_dir / "assets" / candidate_id / "blog.md").exists()
    assert (data_dir / "assets" / candidate_id / "shorts_script.txt").exists()

    report = weekly_report()
    assert report["status_counts"]["APPROVED"] == 1
