from types import SimpleNamespace
from unittest.mock import patch

import pytest

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.public_webforms import form_choices
from corehq.apps.public_webforms.models import PublicWebformType


def _build_app():
    """An app with one of each relevant form: an eligible survey form, an
    eligible registration form, an ineligible case-requiring form, and a form
    in an advanced (non-basic) menu."""
    factory = AppFactory(domain='pwf-test', name='Public Forms App')
    __, survey_form = factory.new_basic_module('survey', 'patient')
    __, registration_form = factory.new_basic_module('registration', 'patient')
    factory.form_opens_case(registration_form, 'patient')
    __, followup_form = factory.new_basic_module('followup', 'patient')
    factory.form_requires_case(followup_form)
    __, advanced_form = factory.new_advanced_module('advanced', 'patient')
    return SimpleNamespace(
        app=factory.app,
        domain=factory.app.domain,
        survey_form=survey_form,
        registration_form=registration_form,
        survey_form_id=survey_form.unique_id,
        registration_form_id=registration_form.unique_id,
        followup_form_id=followup_form.unique_id,
        advanced_form_id=advanced_form.unique_id,
    )


def _patch_released_build(app):
    """Serve ``app`` as the latest released build for a single app id."""
    return patch.multiple(
        form_choices,
        get_latest_released_app_versions_by_app_id=lambda domain: {'app-1': 1},
        get_latest_released_app=lambda domain, app_id: app,
    )


def test_choices_include_only_eligible_forms():
    data = _build_app()
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


def test_choices_omit_app_with_no_eligible_forms():
    factory = AppFactory(domain='pwf-test', name='No Eligible Forms')
    __, followup_form = factory.new_basic_module('followup', 'patient')
    factory.form_requires_case(followup_form)
    with _patch_released_build(factory.app):
        choices = form_choices.get_public_webform_choices('pwf-test')
    assert choices == []


@pytest.mark.parametrize('form_id_attr', ['survey_form_id', 'registration_form_id'])
def test_eligible_form_resolves_selection(form_id_attr):
    data = _build_app()
    with patch.object(form_choices, 'get_latest_released_app', return_value=data.app):
        form = form_choices.get_public_webform_eligible_form(
            data.domain, 'ignored-app-id', getattr(data, form_id_attr))
    assert form is not None
    assert form.unique_id == getattr(data, form_id_attr)


@pytest.mark.parametrize('form_id_or_attr', [
    'followup_form_id',
    'advanced_form_id',
    'missing-form',
], ids=['requires-case', 'advanced-menu', 'not-in-app'])
def test_eligible_form_rejects_invalid_selection(form_id_or_attr):
    data = _build_app()
    # Attribute names resolve to a real form id; anything else is used as-is
    # (a form id that doesn't exist in the released build).
    form_unique_id = getattr(data, form_id_or_attr, form_id_or_attr)
    with patch.object(form_choices, 'get_latest_released_app', return_value=data.app):
        form = form_choices.get_public_webform_eligible_form(
            data.domain, 'ignored-app-id', form_unique_id)
    assert form is None


def test_eligible_form_rejects_app_without_released_build():
    with patch.object(form_choices, 'get_latest_released_app', return_value=None):
        form = form_choices.get_public_webform_eligible_form(
            'pwf-test', 'unreleased-app', 'any-form')
    assert form is None


@pytest.mark.parametrize('form_attr, expected_type', [
    ('survey_form', PublicWebformType.SURVEY),
    ('registration_form', PublicWebformType.REGISTRATION),
])
def test_get_type_classifies_form(form_attr, expected_type):
    data = _build_app()
    assert form_choices.get_public_webform_type(getattr(data, form_attr)) == expected_type
