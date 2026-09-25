from datetime import datetime

import pytest

FROZEN_NOW = datetime(2026, 1, 5, 12, 0)


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN_NOW


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
