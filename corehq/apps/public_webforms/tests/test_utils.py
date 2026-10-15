from unittest.mock import Mock, patch

from unmagic import use

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.public_webforms.tests.utils import (
    DOMAIN,
    saved_app,
    webform_domain,
)
from corehq.apps.public_webforms.utils import (
    get_create_public_webform_url,
    is_app_live,
    public_webforms_enabled,
)
from corehq.privileges import PUBLIC_WEBFORMS
from corehq.util.test_utils import flag_enabled, privilege_enabled


@use('db', webform_domain)
class TestPublicWebformsEnabled:

    @flag_enabled('PUBLIC_WEBFORMS')
    @privilege_enabled(PUBLIC_WEBFORMS)
    def test_enabled_for_an_active_project_with_the_flag_and_privilege(self):
        assert public_webforms_enabled(webform_domain().name)

    @privilege_enabled(PUBLIC_WEBFORMS)
    def test_not_enabled_without_the_flag(self):
        assert not public_webforms_enabled(webform_domain().name)

    @flag_enabled('PUBLIC_WEBFORMS')
    def test_not_enabled_without_the_privilege(self):
        assert not public_webforms_enabled(webform_domain().name)

    @flag_enabled('PUBLIC_WEBFORMS')
    @privilege_enabled(PUBLIC_WEBFORMS)
    def test_not_enabled_for_an_inactive_project(self):
        domain_obj = webform_domain()
        domain_obj.is_active = False
        domain_obj.save()

        assert not public_webforms_enabled(domain_obj.name)


@use(saved_app)
def test_a_saved_app_is_live():
    assert is_app_live(DOMAIN, saved_app()._id)


@use(saved_app)
def test_a_deleted_app_is_not_live():
    app = saved_app()
    app.delete_app()
    app.save()

    assert not is_app_live(DOMAIN, app._id)


@patch('corehq.apps.public_webforms.utils.can_access_public_webforms', new=lambda request, domain: True)
def test_create_url_preselects_the_form():
    factory = AppFactory(domain='pwf-test', build_version='2.51.0')
    factory.app._id = 'app-1'
    __, form = factory.new_basic_module('survey', 'patient')

    url = get_create_public_webform_url(Mock(), form)

    assert url == f'/a/pwf-test/public_webforms/create/?app_id=app-1&form_unique_id={form.unique_id}'


@patch('corehq.apps.public_webforms.utils.can_access_public_webforms', new=lambda request, domain: True)
def test_create_url_is_not_offered_for_an_ineligible_form():
    factory = AppFactory(domain='pwf-test', build_version='2.51.0')
    __, form = factory.new_basic_module('followup', 'patient')
    factory.form_requires_case(form)

    assert get_create_public_webform_url(Mock(), form) is None


@patch('corehq.apps.public_webforms.utils.can_access_public_webforms', new=lambda request, domain: True)
def test_create_url_is_not_offered_below_commcare_2_51():
    factory = AppFactory(domain='pwf-test', build_version='2.50.0')
    __, form = factory.new_basic_module('survey', 'patient')

    assert get_create_public_webform_url(Mock(), form) is None
