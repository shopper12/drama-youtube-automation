from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_DECISIONS = {"APPROVE", "HOLD", "REJECT"}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root() -> Path:
    # Local checkout: <repo>/backend/app/services/this_file.py
    # Docker: /app/app/services/this_file.py with /automation and /storage mounted.
    docker_root = Path("/automation")
    if docker_root.exists():
        return Path("/")
    return Path(__file__).resolve().parents[3]


def automation_root() -> Path:
    configured = os.getenv("CONTENT_AUTOMATION_ROOT")
    if configured:
        return Path(configured)
    root = _repo_root()
    return root / "automation" if root != Path("/") else Path("/automation")


def data_root() -> Path:
    configured = os.getenv("CONTENT_AUTOMATION_DATA_DIR")
    if configured:
        path = Path(configured)
    else:
        root = _repo_root()
        path = root / "storage" / "content_automation" if root != Path("/") else Path("/storage/content_automation")
    path.mkdir(parents=True, exist_ok=True)
    return path


def strategy_path() -> Path:
    configured = os.getenv("CONTENT_AUTOMATION_STRATEGY")
    if configured:
        return Path(configured)
    return automation_root() / "config" / "content_candidate_strategy.json"


def queue_path() -> Path:
    return data_root() / "approval_queue.json"


def load_strategy() -> dict[str, Any]:
    path = strategy_path()
    if not path.exists():
        raise FileNotFoundError(f"Content strategy not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_queue() -> list[dict[str, Any]]:
    path = queue_path()
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else payload.get("items", [])


def _save_queue(items: list[dict[str, Any]]) -> None:
    queue_path().write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _weighted_score(metrics: dict[str, Any], weights: dict[str, Any]) -> float:
    total = 0.0
    weight_sum = 0.0
    for name, raw_weight in weights.items():
        weight = float(raw_weight)
        total += float(metrics.get(name, 0.0)) * weight
        weight_sum += weight
    return round(total / weight_sum, 4) if weight_sum else 0.0


def _format_for(eps: float, vps: float) -> tuple[str, list[str]]:
    if eps >= 0.65 and vps >= 0.80:
        return "Both", ["NAVER_BLOG", "YOUTUBE_SHORTS"]
    if eps >= 0.60 and vps >= 0.65:
        return "Both", ["NAVER_BLOG", "YOUTUBE_SHORTS"]
    if eps >= 0.60:
        return "Blog", ["NAVER_BLOG"]
    if vps >= 0.75:
        return "Shorts", ["YOUTUBE_SHORTS"]
    return "Hold", []


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣]+", "-", value).strip("-").lower()
    return cleaned[:48] or "content"


def generate_candidates(limit: int = 10, category: str | None = None) -> list[dict[str, Any]]:
    strategy = load_strategy()
    scoring = strategy.get("scoring", {})
    eps_weights = scoring.get("expected_profit_score", {}).get("weights", {})
    vps_weights = scoring.get("viral_potential_score", {}).get("weights", {})
    min_eps = float(scoring.get("expected_profit_score", {}).get("min_queue_score", 0.60))

    existing = _load_queue()
    used_keys = {(item.get("category"), item.get("title")) for item in existing}
    generated: list[dict[str, Any]] = []

    for topic in strategy.get("topic_tiers", []):
        topic_category = str(topic.get("category", "General"))
        if category and category != topic_category:
            continue
        metrics = topic.get("base_metrics", {})
        eps = _weighted_score(metrics, eps_weights)
        vps = _weighted_score(metrics, vps_weights)
        if eps < min_eps and vps < 0.75:
            continue

        format_name, channels = _format_for(eps, vps)
        for title in topic.get("title_patterns", []):
            key = (topic_category, title)
            if key in used_keys:
                continue
            candidate_id = f"{datetime.now(timezone.utc):%Y%m%d}-{_slug(topic_category)}-{len(existing) + len(generated) + 1:03d}"
            item = {
                "id": candidate_id,
                "category": topic_category,
                "title": title,
                "tier": topic.get("tier", 99),
                "expected_profit_score": eps,
                "viral_potential_score": vps,
                "recommended_format": format_name,
                "publish_channels": channels,
                "risk_level": topic.get("risk_level", "UNKNOWN"),
                "content_rules": topic.get("content_rules", []),
                "affiliate_program": topic.get("affiliate_program"),
                "owner_decision": "",
                "approval_status": "READY_FOR_OWNER_APPROVAL",
                "created_at": _utcnow(),
                "updated_at": _utcnow(),
            }
            generated.append(item)
            used_keys.add(key)
            if len(generated) >= max(1, min(limit, 50)):
                break
        if len(generated) >= max(1, min(limit, 50)):
            break

    _save_queue(existing + generated)
    return generated


def list_queue(status: str | None = None) -> list[dict[str, Any]]:
    items = _load_queue()
    if status:
        return [item for item in items if item.get("approval_status") == status]
    return items


def apply_decision(candidate_id: str, decision: str, memo: str | None = None) -> dict[str, Any]:
    normalized = decision.strip().upper()
    if normalized not in VALID_DECISIONS:
        raise ValueError(f"decision must be one of {sorted(VALID_DECISIONS)}")

    items = _load_queue()
    for item in items:
        if item.get("id") != candidate_id:
            continue
        item["owner_decision"] = normalized
        item["approval_status"] = {
            "APPROVE": "APPROVED",
            "HOLD": "ON_HOLD",
            "REJECT": "REJECTED",
        }[normalized]
        item["decision_memo"] = memo or ""
        item["updated_at"] = _utcnow()
        _save_queue(items)
        return item
    raise KeyError(f"candidate not found: {candidate_id}")


def build_assets(candidate_id: str) -> dict[str, Any]:
    item = next((row for row in _load_queue() if row.get("id") == candidate_id), None)
    if item is None:
        raise KeyError(f"candidate not found: {candidate_id}")
    if item.get("approval_status") != "APPROVED":
        raise PermissionError("Only APPROVED candidates can generate publish assets")

    out_dir = data_root() / "assets" / candidate_id
    out_dir.mkdir(parents=True, exist_ok=True)
    title = str(item["title"])
    category = str(item["category"])
    rules = "\n".join(f"- {rule}" for rule in item.get("content_rules", []))

    blog = f"""# {title}\n\n## 핵심 요약\n\n{category} 주제의 승인된 콘텐츠 초안입니다. 발행 전 최신 수치와 사실관계를 검증하세요.\n\n## 본문 구성\n\n1. 독자가 바로 이해할 수 있는 문제 상황\n2. 핵심 수치 또는 비교 기준\n3. 실행 가능한 단계\n4. 반론·예외·주의사항\n5. 결론과 체크리스트\n\n## 준수 규칙\n\n{rules or '- 과장·보장 표현 금지'}\n\n## 고지\n\n제휴 링크가 포함될 수 있으며, 가격·정책·기능은 발행 시점에 재확인해야 합니다.\n"""
    shorts = f"""[0-3초 HOOK]\n{title}\n\n[3-15초 문제]\n대부분이 놓치는 핵심 조건을 한 문장으로 제시합니다.\n\n[15-45초 해결]\n숫자와 단계 중심으로 세 가지 포인트를 설명합니다.\n\n[45-55초 주의]\n개인 상황과 최신 정책에 따라 결과가 달라질 수 있음을 알립니다.\n\n[55-60초 CTA]\n필요하면 저장하고 최신 기준을 다시 확인하세요.\n"""

    blog_path = out_dir / "blog.md"
    shorts_path = out_dir / "shorts_script.txt"
    manifest_path = out_dir / "manifest.json"
    blog_path.write_text(blog, encoding="utf-8")
    shorts_path.write_text(shorts, encoding="utf-8")
    manifest = {
        "candidate": item,
        "generated_at": _utcnow(),
        "files": [str(blog_path), str(shorts_path)],
        "next_gate": "HUMAN_REVIEW_AND_CHANNEL_PUBLISH",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def weekly_report() -> dict[str, Any]:
    items = _load_queue()
    counts: dict[str, int] = {}
    for item in items:
        key = str(item.get("approval_status", "UNKNOWN"))
        counts[key] = counts.get(key, 0) + 1
    approved = [item for item in items if item.get("approval_status") == "APPROVED"]
    return {
        "generated_at": _utcnow(),
        "total_candidates": len(items),
        "status_counts": counts,
        "approved_expected_profit_score_avg": round(
            sum(float(item.get("expected_profit_score", 0.0)) for item in approved) / len(approved), 4
        ) if approved else 0.0,
        "approved_viral_potential_score_avg": round(
            sum(float(item.get("viral_potential_score", 0.0)) for item in approved) / len(approved), 4
        ) if approved else 0.0,
        "approved_ids": [item.get("id") for item in approved],
    }
