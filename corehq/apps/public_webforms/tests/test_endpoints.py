from types import SimpleNamespace

from unmagic import fixture, use

from corehq.apps.app_manager.dbaccessors import get_app, get_latest_build_id
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    delete_all_apps,
    get_simple_form,
    patch_validate_xform,
)
from corehq.apps.domain.models import Domain
from corehq.apps.public_webforms.endpoints import (
    create_public_webform_endpoint,
)

DOMAIN = 'public-webform-endpoints'


@use('db')
@fixture
def released_app():
    """A released build of an app with a basic survey form and no endpoint."""
    domain_obj = Domain.get_or_create_with_name(DOMAIN)
    # session endpoints require CommCare 2.51+ (feature_support)
    factory = AppFactory(DOMAIN, name='PWF App', build_version='2.51.0')
    __, form = factory.new_basic_module('survey', 'patient')
    form.source = get_simple_form(xmlns=form.unique_id)
    try:
        # patch covers the test body too (generate rebuilds, which validates forms)
        with patch_validate_xform():
            app = factory.app
            app.save()
            build = app.make_build()
            build.is_released = True
            build.save()
            yield SimpleNamespace(
                domain=DOMAIN,
                app_id=app.get_id,
                build_id=build.get_id,
                form_unique_id=form.unique_id,
            )
    finally:
        delete_all_apps()
        domain_obj.get_db().delete_doc(domain_obj.get_id)


@use(released_app)
class TestCreatePublicWebformEndpoint:

    def test_generates_detached_build_emitting_the_endpoint(self):
        app = released_app()
        build_id, endpoint_id = create_public_webform_endpoint(
            app.domain, app.app_id, app.form_unique_id)

        assert build_id != app.build_id
        new_build = get_app(app.domain, build_id)
        # detached from the app's lineage, but traceable back to it
        assert new_build.copy_of == f'{app.app_id}__public_webform'
        suite = new_build.fetch_attachment('files/suite.xml')
        if isinstance(suite, bytes):
            suite = suite.decode('utf-8')
        assert endpoint_id in suite

    def test_canonical_is_never_written(self):
        app = released_app()
        version_before = get_app(app.domain, app.app_id).version
        create_public_webform_endpoint(app.domain, app.app_id, app.form_unique_id)
        canonical = get_app(app.domain, app.app_id)
        assert canonical.version == version_before
        assert canonical.get_form(app.form_unique_id).session_endpoint_id is None

    def test_detached_build_stays_out_of_the_lineage(self):
        app = released_app()
        create_public_webform_endpoint(app.domain, app.app_id, app.form_unique_id)
        # the generated build must not become the app's latest build
        assert get_latest_build_id(app.domain, app.app_id) == app.build_id

    def test_released_build_is_untouched(self):
        app = released_app()
        create_public_webform_endpoint(app.domain, app.app_id, app.form_unique_id)
        released = get_app(app.domain, app.build_id)
        assert released.get_form(app.form_unique_id).session_endpoint_id is None

    def test_always_generates_an_endpoint(self):
        """Reusing an endpoint would pin a build a user can delete."""
        app = released_app()
        released = get_app(app.domain, app.build_id)
        released.get_form(app.form_unique_id).session_endpoint_id = 'existing-endpoint'
        released.save(increment_version=False)
        assert get_app(app.domain, app.build_id).get_form(
            app.form_unique_id).session_endpoint_id == 'existing-endpoint'

        build_id, endpoint_id = create_public_webform_endpoint(
            app.domain, app.app_id, app.form_unique_id)

        assert build_id != app.build_id
        assert endpoint_id != 'existing-endpoint'
