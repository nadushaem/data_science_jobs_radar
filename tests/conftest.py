from datetime import datetime

import pytest

from storage import db

FROZEN_NOW = datetime(2026, 1, 5, 12, 0)


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN_NOW


# у каждого теста своя пустая база во временной папке.
# autouse — чтобы ни один тест случайно не записал в настоящую data/radar.db
@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    db.init_db()


# подменяет datetime в переданном модуле, возвращает «текущее» время
@pytest.fixture
def freeze_now(monkeypatch):
    def _freeze(module):
        monkeypatch.setattr(module, "datetime", _FrozenDatetime)
        return FROZEN_NOW

    return _freeze


# минимальная вакансия, поля переопределяются через kwargs
@pytest.fixture
def make_vacancy():
    def _make(**overrides):
        vacancy = {"title": "data scientist", "company": "acme", "url": "https://x/1"}
        vacancy.update(description=None, skills=[], salary_min=None, salary_max=None)
        vacancy.update(overrides)
        return vacancy

    return _make
