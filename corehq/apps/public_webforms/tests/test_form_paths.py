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
MENU_NAME = 'Patient Intake'
FORM_NAME = 'Cohort Registration'


@use('db')
@fixture
def app_with_build():
    """An app with one named form, and a build pinning that name."""
    domain_obj = Domain.get_or_create_with_name(DOMAIN)
    factory = AppFactory(DOMAIN, name=APP_NAME, build_version='2.51.0')
    menu, form = factory.new_basic_module('survey', 'patient')
    menu.name = {'en': MENU_NAME}
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
                version=build.version,
                form_unique_id=form.unique_id,
            )
    finally:
        delete_all_apps()
        domain_obj.delete()


def _webform(app, webform_id=1, **kwargs):
    return PublicWebform(**{
        'id': webform_id,
        'domain': DOMAIN,
        'app_id': app.app_id,
        'app_build_id': app.build_id,
        'form_unique_id': app.form_unique_id,
        **kwargs,
    })


def _path(*webforms):
    paths = get_public_webform_form_paths(DOMAIN, webforms)
    return paths[webforms[0].id] if len(webforms) == 1 else paths


@use(app_with_build)
class TestGetPublicWebformPaths:

    def test_get_public_webform_paths(self):
        app = app_with_build()

        path = _path(_webform(app))

        assert path['app_name'] == APP_NAME
        assert path['app_version'] == app.version
        assert path['menu_name'] == MENU_NAME
        assert path['form_name'] == FORM_NAME
        assert path['app_url'].endswith(f'/{app.app_id}/')

    def test_app_uses_current_name(self):
        app = app_with_build()
        canonical = get_app(DOMAIN, app.app_id)
        canonical.name = 'Renamed Program'
        canonical.save()

        assert _path(_webform(app))['app_name'] == 'Renamed Program'

    def test_form_uses_pinned_name(self):
        app = app_with_build()
        canonical = get_app(DOMAIN, app.app_id)
        canonical.get_form(app.form_unique_id).name = {'en': 'Renamed Form'}
        canonical.save()

        assert _path(_webform(app))['form_name'] == FORM_NAME

    def test_app_version_pinned(self):
        app = app_with_build()
        canonical = get_app(DOMAIN, app.app_id)
        canonical.save()  # bumps the app's version past the build's

        assert _path(_webform(app))['app_version'] == app.version
        assert get_app(DOMAIN, app.app_id).version > app.version

    def test_deleted_app_falls_back_to_build_name(self):
        app = app_with_build()
        canonical = get_app(DOMAIN, app.app_id)
        canonical.delete_app()
        canonical.save(increment_version=False)

        path = _path(_webform(app))

        assert path['app_name'] == f'{APP_NAME} (Deleted)'
        assert path['app_url'] is None
        assert path['form_name'] == FORM_NAME
