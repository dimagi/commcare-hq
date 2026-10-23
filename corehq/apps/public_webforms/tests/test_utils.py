from unittest.mock import Mock, patch

import pytest
from unmagic import use

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.public_webforms import utils
from corehq.apps.public_webforms.tests.utils import (
    DOMAIN,
    build_app,
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


def _patch_released_app(app, is_app_live=True):
    """Serve ``app`` as the latest released build of any app id."""
    return patch.multiple(
        utils,
        is_app_live=lambda domain, app_id: is_app_live,
        get_latest_released_app=lambda domain, app_id: app,
    )


@pytest.mark.parametrize('form_id_attr', ['survey_form_id', 'registration_form_id'])
def test_eligible_form_resolves_selection(form_id_attr):
    data = build_app()
    with _patch_released_app(data.app):
        form = utils.get_latest_released_eligible_form(
            data.domain, 'app-1', getattr(data, form_id_attr))
    assert form is not None
    assert form.unique_id == getattr(data, form_id_attr)


@pytest.mark.parametrize('form_id_or_attr', [
    'followup_form_id',
    'advanced_form_id',
    'missing-form',
], ids=['requires-case', 'advanced-menu', 'not-in-app'])
def test_eligible_form_rejects_invalid_selection(form_id_or_attr):
    data = build_app()
    # Attribute names resolve to a real form id; anything else is used as-is
    # (a form id that doesn't exist in the released build).
    form_unique_id = getattr(data, form_id_or_attr, form_id_or_attr)
    with _patch_released_app(data.app):
        form = utils.get_latest_released_eligible_form(
            data.domain, 'app-1', form_unique_id)
    assert form is None


def test_eligible_form_rejects_app_without_released_build():
    data = build_app()
    with _patch_released_app(None):
        form = utils.get_latest_released_eligible_form(
            data.domain, 'app-1', data.survey_form_id)
    assert form is None


def test_eligible_form_rejects_a_release_that_cannot_generate_session_endpoints():
    data = build_app()
    with (
        _patch_released_app(data.app),
        patch.object(Application, 'can_generate_session_endpoints', False),
    ):
        form = utils.get_latest_released_eligible_form(
            data.domain, 'app-1', data.survey_form_id)
    assert form is None


def test_eligible_form_rejects_deleted_app():
    data = build_app()
    with _patch_released_app(data.app, is_app_live=False):
        form = utils.get_public_webform_eligible_form(
            data.domain, 'app-1', data.survey_form_id)
    assert form is None


@patch('corehq.apps.public_webforms.utils.can_access_public_webforms', lambda *args: True)
@patch('corehq.apps.public_webforms.utils.get_latest_released_eligible_form', lambda *args: True)
def test_create_url_preselects_the_form():
    factory = AppFactory(domain='pwf-test')
    factory.app._id = 'app-1'
    __, form = factory.new_basic_module('survey', 'patient')

    url = get_create_public_webform_url(Mock(), form)

    assert url == f'/a/pwf-test/public_webforms/create/?app_id=app-1&form_unique_id={form.unique_id}'


@patch('corehq.apps.public_webforms.utils.can_access_public_webforms', lambda *args: True)
@patch('corehq.apps.public_webforms.utils.get_latest_released_eligible_form', lambda *args: None)
def test_create_url_is_not_offered_for_an_ineligible_form():
    factory = AppFactory(domain='pwf-test')
    __, form = factory.new_basic_module('survey', 'patient')

    assert get_create_public_webform_url(Mock(), form) is None
