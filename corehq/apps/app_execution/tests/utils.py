import json

from corehq.apps.app_manager.tests.views.test_apply_patch import assert_no_diff


def assert_json_dict_equal(expected, actual):
    if expected != actual:
        assert_no_diff(json.dumps(expected, indent=2), json.dumps(actual, indent=2))
