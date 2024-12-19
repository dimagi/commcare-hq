from testil import eq
from corehq.apps.hqwebapp.utils.bootstrap.paths import is_ignored_path


def test_is_ignored_path_true():
    path = "/path/to/corehq/apps/hqwebapp/templates/hqwebapp/crispy/radioselect.html"
    app_name = "hqwebapp"
    eq(is_ignored_path(app_name, path), True)


def test_is_ignored_path_false():
    path = "/path/to/corehq/apps/builds/templates/builds/base_builds.html"
    app_name = "builds"
    eq(is_ignored_path(app_name, path), False)
