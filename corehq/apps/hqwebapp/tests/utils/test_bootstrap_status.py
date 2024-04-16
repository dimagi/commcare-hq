from testil import eq

from corehq.apps.hqwebapp.utils.bootstrap.status import (
    is_app_completed,
    get_completed_templates_for_app,
    get_completed_javascript_for_app,
)


def test_is_app_completed_for_builds():
    is_completed = is_app_completed("builds")
    eq(is_completed, True)


def test_get_completed_templates_for_app_relative_paths():
    completed_templates = get_completed_templates_for_app("builds", use_full_paths=False)
    eq(completed_templates, [
        "edit_menu.html"
    ])


def test_get_completed_javascript_for_app_relative_paths():
    completed_templates = get_completed_javascript_for_app("builds", use_full_paths=False)
    eq(completed_templates, [
        "js/edit_builds.js"
    ])
