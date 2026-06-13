from app.models import Drama
from app.services.script_generator_service import generate_script


def test_all_title_candidates_include_required_keyword():
    result = generate_script(Drama(title="비밀의 집"))
    required = ("결말포함", "몰아보기", "줄거리요약")
    assert len(result.title_candidates) == 10
    assert all(any(word in title for word in required) for title in result.title_candidates)


def test_critique_ratio_is_at_most_ten_percent():
    result = generate_script(Drama(title="비밀의 집"))
    assert result.critique_ratio <= 0.10
