from unittest.mock import patch

import pytest

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.public_webforms import form_choices
from corehq.apps.public_webforms.models import PublicWebformType
from corehq.apps.public_webforms.tests.utils import build_app
from corehq.util.test_utils import disable_quickcache


def _patch_released_build(app, live_app_ids=('app-1',)):
    """Serve ``app`` as the latest released build for a single app id."""
    return patch.multiple(
        form_choices,
        get_live_app_ids=lambda domain: set(live_app_ids),
        get_latest_released_build_ids_by_app_id=lambda domain: {'app-1': 'build-1'},
        iter_docs=lambda db, build_ids: [app.to_json() for __ in build_ids],
    )


@disable_quickcache
def test_choices_include_only_eligible_forms():
    data = build_app()
    with _patch_released_build(data.app):
        choices = form_choices.get_public_webform_choices(data.domain)

    assert len(choices) == 1  # top-level (app) choices
    assert choices[0]['id'] == 'app-1'  # the released app id, not a build id
    assert len(choices[0]['menus']) == 2
    forms_by_id = {
        form['id']: form
        for menu in choices[0]['menus']
        for form in menu['forms']
    }
    assert set(forms_by_id) == {data.survey_form_id, data.registration_form_id}


@disable_quickcache
def test_choices_omit_app_with_no_eligible_forms():
    factory = AppFactory(domain='pwf-test', name='No Eligible Forms')
    __, followup_form = factory.new_basic_module('followup', 'patient')
    factory.form_requires_case(followup_form)
    with _patch_released_build(factory.app):
        choices = form_choices.get_public_webform_choices('pwf-test')
    assert choices == []


@disable_quickcache
def test_choices_omit_deleted_app():
    data = build_app()
    with _patch_released_build(data.app, live_app_ids=()):
        choices = form_choices.get_public_webform_choices(data.domain)
    assert choices == []


@pytest.mark.parametrize('form_attr, expected_type', [
    ('survey_form', PublicWebformType.SURVEY),
    ('registration_form', PublicWebformType.REGISTRATION),
])
def test_get_type_classifies_form(form_attr, expected_type):
    data = build_app()
    assert form_choices.get_public_webform_type(getattr(data, form_attr)) == expected_type
