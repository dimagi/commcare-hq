from types import SimpleNamespace

from unmagic import fixture, use

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    delete_all_apps,
    get_simple_form,
    patch_validate_xform,
)
from corehq.apps.domain.models import Domain
from corehq.apps.public_webforms.form_paths import (
    get_public_webform_form_paths,
)
from corehq.apps.public_webforms.models import PublicWebform

DOMAIN = 'public-webform-form-paths'
APP_NAME = 'Frontline Program'
MENU_NAME = 'Registration'
FORM_NAME = 'Cohort Registration'


@use('db')
@fixture
def app_with_build():
    """An app with one named menu and form, and a build pinning those names."""
    domain_obj = Domain.get_or_create_with_name(DOMAIN)
    factory = AppFactory(DOMAIN, name=APP_NAME, build_version='2.51.0')
    module, form = factory.new_basic_module('survey', 'patient')
    module.name = {'en': MENU_NAME}
    form.name = {'en': FORM_NAME}
    form.source = get_simple_form(xmlns=form.unique_id)
    try:
        with patch_validate_xform():
            app = factory.app
            app.save()
            build = app.make_build()
            build.save()
            yield SimpleNamespace(
                app_id=app.get_id,
                build_id=build.get_id,
                form_unique_id=form.unique_id,
            )
    finally:
        delete_all_apps()
        domain_obj.get_db().delete_doc(domain_obj.get_id)


def _webform(app, webform_id=1, **kwargs):
    return PublicWebform(**{
        'id': webform_id,
        'domain': DOMAIN,
        'app_id': app.app_id,
        'app_build_id': app.build_id,
        'form_unique_id': app.form_unique_id,
        **kwargs,
    })


def _path(*webforms, domain=DOMAIN):
    paths = get_public_webform_form_paths(domain, webforms)
    return paths[webforms[0].id] if len(webforms) == 1 else paths


def _names(path):
    return [segment.name for segment in path]


def _deleted(path):
    return [segment.name for segment in path if segment.is_deleted]


@use(app_with_build)
class TestGetPublicWebformFormPaths:

    def test_the_whole_path_is_named_and_linked(self):
        app = app_with_build()

        path = _path(_webform(app))

        assert _names(path) == [APP_NAME, MENU_NAME, FORM_NAME]
        assert all(segment.url for segment in path)
        assert not _deleted(path)

    def test_names_are_the_ones_the_build_pinned(self):
        """Respondents get the build, so renaming the app doesn't rename this."""
        app = app_with_build()
        canonical = get_app(DOMAIN, app.app_id)
        canonical.name = 'Renamed Program'
        canonical.get_module(0).name = {'en': 'Renamed Menu'}
        canonical.get_form(app.form_unique_id).name = {'en': 'Renamed Form'}
        canonical.save()

        assert _names(_path(_webform(app))) == [APP_NAME, MENU_NAME, FORM_NAME]

    def test_a_form_removed_from_the_app_is_marked(self):
        """The webform still works — it serves the build, not the app."""
        app = app_with_build()
        canonical = get_app(DOMAIN, app.app_id)
        canonical.get_module(0).forms = []
        canonical.save()

        path = _path(_webform(app))

        assert _deleted(path) == [FORM_NAME]
        assert path[0].url and path[1].url

    def test_a_menu_removed_from_the_app_is_marked_once(self):
        """Its forms went with it, so only the menu is called out."""
        app = app_with_build()
        canonical = get_app(DOMAIN, app.app_id)
        canonical.modules = []
        canonical.save()

        path = _path(_webform(app))

        assert _deleted(path) == [MENU_NAME]
        assert _names(path) == [APP_NAME, MENU_NAME, FORM_NAME]

    def test_a_deleted_app_is_marked_once(self):
        app = app_with_build()
        canonical = get_app(DOMAIN, app.app_id)
        canonical.delete_app()
        canonical.save(increment_version=False)

        path = _path(_webform(app))

        assert _deleted(path) == [APP_NAME]
        assert not any(segment.url for segment in path)

    def test_a_missing_build_falls_back_to_the_app(self):
        """A dashboard row is worth less than the whole page failing."""
        app = app_with_build()

        path = _path(_webform(app, app_build_id='no-such-build'))

        assert _names(path) == [APP_NAME, MENU_NAME, FORM_NAME]

    def test_an_app_in_another_domain_is_not_read(self):
        app = app_with_build()

        path = _path(_webform(app), domain='other-domain')

        assert _names(path) == ['', '', '']
        assert not _deleted(path)
