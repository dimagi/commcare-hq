from testil import eq
from corehq.apps.hqwebapp.utils.bootstrap.paths import (
    is_ignored_path,
    get_bootstrap5_path,
    is_bootstrap3_path,
)


def test_is_ignored_path_true():
    path = "/path/to/corehq/apps/hqwebapp/templates/hqwebapp/crispy/radioselect.html"
    app_name = "hqwebapp"
    eq(is_ignored_path(app_name, path), True)


def test_is_ignored_path_false():
    path = "/path/to/corehq/apps/builds/templates/builds/base_builds.html"
    app_name = "builds"
    eq(is_ignored_path(app_name, path), False)


def test_get_bootstrap5_path():
    bootstrap3_path = "reports/bootstrap3/base_template.html"
    bootstrap5_path = "reports/bootstrap5/base_template.html"
    eq(get_bootstrap5_path(bootstrap3_path), bootstrap5_path)


def test_get_bootstrap5_path_none():
    eq(get_bootstrap5_path(None), None)


def test_is_bootstrap3_path():
    bootstrap3_path = "reports/bootstrap3/base_template.html"
    eq(is_bootstrap3_path(bootstrap3_path), True)


def test_is_bootstrap3_path_false_with_none():
    eq(is_bootstrap3_path(None), False)
