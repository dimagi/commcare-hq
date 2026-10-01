from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import pytz
from django.db import DatabaseError
from unmagic import use

from corehq.apps.public_webforms import forms
from corehq.apps.public_webforms.models import (
    PublicWebform,
    PublicWebformStatus,
    PublicWebformType,
)
from corehq.apps.public_webforms.tests.utils import create_webform

DOMAIN = 'public-webform-forms'
TIMEZONE = pytz.timezone('America/New_York')
SURVEY_FORM = SimpleNamespace(is_registration_form=lambda: False)
REGISTRATION_FORM = SimpleNamespace(is_registration_form=lambda: True)


def _filter(**params):
    queryset = PublicWebform.objects.with_status()
    return list(forms.PublicWebformFilterForm(params).filter(queryset))


@use('db')
@pytest.mark.parametrize('params', [
    {'search': 'natal'},
    {'status': PublicWebformStatus.CLOSED},
    {'session_type': PublicWebformType.REGISTRATION},
], ids=['search', 'status', 'session_type'])
def test_each_filter_narrows_the_list(params):
    wanted = create_webform(
        label='Antenatal visit',
        session_type=PublicWebformType.REGISTRATION,
        is_disabled=True,
    )
    create_webform(
        label='Household survey',
        session_type=PublicWebformType.SURVEY,
        is_disabled=False,
    )

    assert _filter(**params) == [wanted]


@use('db')
def test_a_value_that_is_not_offered_is_ignored():
    # The query string is linkable, so a hand-edited filter must not break it.
    webform = create_webform()

    assert _filter(status='not-a-status') == [webform]


@pytest.mark.parametrize('params, expected', [
    ({}, False),
    ({'search': ''}, False),
    ({'search': 'natal'}, True),
    ({'status': 'not-a-status'}, False),
], ids=['unfiltered', 'blank', 'searching', 'not-offered'])
def test_is_filtering_reports_whether_the_list_was_narrowed(params, expected):
    assert forms.PublicWebformFilterForm(params).is_filtering is expected


def _form(data=None, has_sms_privilege=False, eligible_form=SURVEY_FORM):
    """Stubs the reads that go to the database or to released builds."""
    args = [data] if data is not None else []
    with patch.multiple(
        forms,
        domain_has_privilege=Mock(return_value=has_sms_privilege),
        get_public_webform_choices=Mock(return_value=[]),
        get_public_webform_eligible_form=Mock(return_value=eligible_form),
    ):
        form = forms.CreatePublicWebformForm(DOMAIN, TIMEZONE, *args)
        form.is_valid()
    return form


def _post_data(**kwargs):
    return {
        'label': 'Antenatal visit',
        'expires_at': '2026-09-01 17:00:00',
        'link_choices': ['allow_email'],
        'app_id': 'app-1',
        'form_unique_id': 'form-1',
        **kwargs,
    }


@pytest.mark.parametrize('entered, expected_utc', [
    ('2026-09-01 17:00:00', datetime(2026, 9, 1, 21, 0)),
    ('2026-12-01 17:00:00', datetime(2026, 12, 1, 22, 0)),
], ids=['daylight-saving-utc-4', 'standard-time-utc-5'])
def test_expires_at_is_stored_as_utc(entered, expected_utc):
    form = _form(_post_data(expires_at=entered))
    assert form.is_valid(), form.errors
    assert form.cleaned_data['expires_at'] == expected_utc


def test_expires_at_defaults_to_the_datepicker_format():
    initial = _form().fields['expires_at'].initial
    # any other format makes the datepicker treat it as invalid and clear it
    assert datetime.strptime(initial, '%Y-%m-%d %H:%M:%S')


def test_a_delivery_option_is_required():
    form = _form(_post_data(link_choices=[]))
    assert not form.is_valid()
    assert 'link_choices' in form.errors


@pytest.mark.parametrize('has_sms_privilege', [True, False])
def test_sms_is_offered_only_with_the_privilege(has_sms_privilege):
    form = _form(has_sms_privilege=has_sms_privilege)
    rendered = dict(form.fields['link_choices'].widget.choices)
    assert ('allow_sms' in rendered) == has_sms_privilege
    assert 'allow_email' in rendered


@pytest.mark.parametrize('eligible_form, expected_type', [
    (SURVEY_FORM, PublicWebformType.SURVEY),
    (REGISTRATION_FORM, PublicWebformType.REGISTRATION),
])
def test_session_type_comes_from_the_selected_form(eligible_form, expected_type):
    form = _form(_post_data(), eligible_form=eligible_form)
    assert form.is_valid(), form.errors
    assert form.cleaned_data['session_type'] == expected_type


@pytest.mark.parametrize('missing', ['app_id', 'form_unique_id'])
def test_an_application_and_form_are_required(missing):
    form = _form(_post_data(**{missing: ''}))
    assert not form.is_valid()
    assert form.non_field_errors() == ["Please select an application, menu, and form."]


def test_an_ineligible_form_is_rejected():
    """The selection is posted from hidden inputs, so it is re-checked."""
    form = _form(_post_data(), eligible_form=None)
    assert not form.is_valid()
    assert form.non_field_errors() == ["The selected form can't be used for a public webform."]


def _create_webform(**post_data):
    """Stubs generating the endpoint, which builds a copy of a released app.
    SMS is granted so delivery options can be exercised independently of it."""
    form = _form(_post_data(**post_data), has_sms_privilege=True)
    assert form.is_valid(), form.errors
    with patch.object(
        forms, 'create_public_webform_build',
        return_value=('build-1', 'endpoint-1'),
    ):
        return form.create_public_webform()


def test_create_deletes_the_generated_build_if_the_webform_is_not_saved():
    """Otherwise the build is left behind with nothing referencing it."""
    form = _form(_post_data())
    assert form.is_valid(), form.errors
    with (
        patch.object(
            forms, 'create_public_webform_build',
            return_value=('build-1', 'endpoint-1'),
        ),
        patch.object(
            forms.PublicWebform.objects, 'create', side_effect=DatabaseError,
        ),
        patch.object(forms, 'delete_public_webform_build') as delete_build,
    ):
        with pytest.raises(DatabaseError):
            form.create_public_webform()

    delete_build.assert_called_once_with(DOMAIN, 'build-1')


@use('db')
def test_create_stores_the_selection_and_generated_endpoint():
    webform = _create_webform()

    assert webform.domain == DOMAIN
    assert webform.label == 'Antenatal visit'
    assert webform.app_id == 'app-1'
    assert webform.form_unique_id == 'form-1'
    assert webform.app_build_id == 'build-1'
    assert webform.endpoint_id == 'endpoint-1'
    assert webform.session_type == PublicWebformType.SURVEY
    assert webform.expires_at == datetime(2026, 9, 1, 21, 0)
    assert webform.is_disabled


@use('db')
@pytest.mark.parametrize('link_choices, allow_email, allow_sms', [
    (['allow_email'], True, False),
    (['allow_sms'], False, True),
    (['allow_email', 'allow_sms'], True, True),
])
def test_create_maps_link_choices_to_delivery_options(link_choices, allow_email, allow_sms):
    webform = _create_webform(link_choices=link_choices)

    assert webform.allow_email == allow_email
    assert webform.allow_sms == allow_sms


def _webform(**kwargs):
    return PublicWebform(**{
        'id': 1,
        'domain': DOMAIN,
        'label': 'Antenatal visit',
        'expires_at': datetime(2026, 9, 1, 21, 0),
        'allow_email': True,
        'allow_sms': False,
        'is_disabled': False,
        **kwargs,
    })


def _edit_form(webform, data=None, has_sms_privilege=False):
    """Stubs the build read that names the app, menu, and form."""
    args = [data] if data is not None else []
    with patch.multiple(
        forms,
        domain_has_privilege=Mock(return_value=has_sms_privilege),
        get_public_webform_form_paths=Mock(return_value={webform.id: {
            'app_name': 'Frontline Program',
            'app_version': '12',
            'menu_name': 'Registration',
            'form_name': 'Cohort Registration',
        }}),
    ):
        form = forms.EditPublicWebformForm(
            webform.domain, TIMEZONE, webform, *args)
        form.is_valid()
    return form


def _edit_data(**kwargs):
    return {
        'label': 'Antenatal visit',
        'expires_at': '2026-09-01 17:00:00',
        'link_choices': ['allow_email'],
        **kwargs,
    }


def test_edit_prefills():
    form = _edit_form(_webform())

    assert form.initial['app_name'] == 'Frontline Program (v12)'
    assert form.initial['menu_name'] == 'Registration'
    assert form.initial['form_name'] == 'Cohort Registration'
    assert form.initial['label'] == 'Antenatal visit'
    # stored as UTC, offered back in the project's timezone
    assert form.fields['expires_at'].initial == '2026-09-01 17:00:00'
    assert form.initial['link_choices'] == ['allow_email']
    assert form.initial['open_to_requests'] is True


def test_edit_drops_a_delivery_option_the_project_can_no_longer_use():
    form = _edit_form(_webform(allow_sms=True), has_sms_privilege=False)

    assert form.initial['link_choices'] == ['allow_email']


@use('db')
def test_edit_updates_the_webform():
    webform = create_webform()
    form = _edit_form(
        webform,
        _edit_data(
            label='Antenatal visit, round two',
            expires_at='2026-12-01 17:00:00',
            link_choices=['allow_sms'],
            is_disabled=True,
        ),
        has_sms_privilege=True,
    )
    assert form.is_valid(), form.errors

    updated = form.update_public_webform()
    updated.refresh_from_db()

    assert updated.label == 'Antenatal visit, round two'
    assert updated.expires_at == datetime(2026, 12, 1, 22, 0)
    assert not updated.allow_email
    assert updated.allow_sms
    assert updated.is_disabled
