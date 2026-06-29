from app.database import normalize_database_url


def test_normalize_render_postgres_url_for_async_sqlalchemy():
    url = "postgresql://user:pass@host:5432/db"

    assert normalize_database_url(url) == "postgresql+asyncpg://user:pass@host:5432/db"


def test_normalize_database_url_keeps_sqlite_url():
    url = "sqlite+aiosqlite:///./drama_automation.db"

    assert normalize_database_url(url) == url
