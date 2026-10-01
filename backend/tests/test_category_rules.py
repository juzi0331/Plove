import json
from types import SimpleNamespace

import pytest

from app.core.errors import AppError, ErrorCode
from app.services.site_control_service import check_category_allowed


class FakeStore:
    def __init__(self, rules):
        self._config = SimpleNamespace(category_rules_json=json.dumps({"rules": rules}))

    def config(self, _key):
        return self._config


def test_visible_category_is_not_rejected_after_rules_are_saved():
    store = FakeStore([
        {"tid": "10", "hidden": False, "subcategories": []},
        {"tid": "11", "hidden": True, "subcategories": []},
    ])

    check_category_allowed("demo", "10", store)


def test_hidden_category_is_rejected():
    store = FakeStore([{"tid": "11", "hidden": True, "subcategories": []}])

    with pytest.raises(AppError) as exc:
        check_category_allowed("demo", "11", store)

    assert exc.value.code == ErrorCode.FORBIDDEN
