import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "reports.db"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
