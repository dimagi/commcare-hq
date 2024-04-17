from testil import eq

from corehq.apps.hqwebapp.utils.bootstrap.status import (
    get_completed_status,
    get_completed_templates_for_app,
    get_completed_javascript_for_app,
)


def test_get_completed_status_for_builds():
    is_completed = get_completed_status("builds")
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
