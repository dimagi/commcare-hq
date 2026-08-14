import pytest

from corehq.apps.public_webforms.models import PublicWebform
from corehq.apps.public_webforms.public.forms import (
    PublicWebformLinkRequestForm,
)


def _form(allow_email=True, allow_sms=True, data=None):
    webform = PublicWebform(allow_email=allow_email, allow_sms=allow_sms)
    return PublicWebformLinkRequestForm(webform, data)


@pytest.mark.parametrize('allow_email, allow_sms, expected', [
    (True, False, ['email']),
    (False, True, ['sms']),
    (True, True, ['email', 'sms']),
], ids=['email-only', 'sms-only', 'both'])
def test_delivery_offers_only_the_channels_the_webform_allows(
    allow_email, allow_sms, expected
):
    form = _form(allow_email=allow_email, allow_sms=allow_sms)

    choices = form.fields['delivery'].choices
    assert [choice[0] for choice in choices] == expected


@pytest.mark.parametrize('allow_email, allow_sms, expected', [
    (True, True, True),
    (True, False, False),
    (False, True, False),
], ids=['both', 'email-only', 'sms-only'])
def test_a_choice_is_offered_only_when_both_channels_are_allowed(
    allow_email, allow_sms, expected
):
    form = _form(allow_email=allow_email, allow_sms=allow_sms)

    assert form.can_choose_delivery is expected


@pytest.mark.parametrize('allow_email, allow_sms, delivery', [
    (True, False, 'sms'),
    (False, True, 'email'),
], ids=['sms-not-allowed', 'email-not-allowed'])
def test_a_channel_the_webform_disallows_is_rejected(
    allow_email, allow_sms, delivery
):
    form = _form(
        allow_email=allow_email, allow_sms=allow_sms,
        data={'delivery': delivery},
    )

    assert not form.is_valid()
    assert 'delivery' in form.errors
