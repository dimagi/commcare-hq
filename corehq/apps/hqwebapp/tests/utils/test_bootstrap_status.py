from testil import eq

from corehq.apps.hqwebapp.utils.bootstrap.status import (
    is_app_completed,
    get_completed_templates_for_app,
    get_completed_javascript_for_app,
    is_app_in_progress,
    get_apps_completed_or_in_progress,
)


def test_is_app_completed_for_builds():
    is_completed = is_app_completed("builds")
    eq(is_completed, True)


def test_is_app_in_progress_for_hqwebapp():
    # we base this test on hqwebapp because it will be the final app to be completed in this migration
    is_in_progress = is_app_in_progress("hqwebapp")
    eq(is_in_progress, True)


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


def test_hqwebapp_is_in_get_apps_completed_or_in_progress():
    apps_completed_or_in_progress = get_apps_completed_or_in_progress()
    eq("hqwebapp" in apps_completed_or_in_progress, True)
