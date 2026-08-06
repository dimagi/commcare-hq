from datetime import datetime
from unittest.mock import patch

import pytest
import pytz

from corehq.apps.public_webforms.forms import CreatePublicWebformForm

DOMAIN = 'public-webform-forms'
TIMEZONE = pytz.timezone('America/New_York')


def _form(data=None, has_sms_privilege=False):
    """Patches the privilege check, which is the form's only database read."""
    args = [data] if data is not None else []
    with patch(
        'corehq.apps.public_webforms.forms.domain_has_privilege',
        return_value=has_sms_privilege,
    ):
        form = CreatePublicWebformForm(DOMAIN, TIMEZONE, *args)
    form.is_valid()
    return form


def _post_data(**kwargs):
    return {
        'label': 'Antenatal visit',
        'expires_at': '2026-09-01 17:00:00',
        'link_choices': ['allow_email'],
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
