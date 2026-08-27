import pytest
from unmagic import use

from corehq.apps.public_webforms.models import PublicWebform
from corehq.apps.public_webforms.public.forms import (
    PublicWebformLinkRequestForm,
)
from corehq.apps.public_webforms.tests.utils import (
    create_webform,
    skip_turnstile,
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


@use(skip_turnstile)
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


@use(skip_turnstile)
@pytest.mark.parametrize('delivery, missing', [
    ('email', 'email'),
    ('sms', 'phone_number'),
], ids=['email', 'sms'])
def test_the_chosen_channel_needs_contact_information(delivery, missing):
    form = _form(data={'delivery': delivery})

    assert not form.is_valid()
    assert missing in form.errors


@use(skip_turnstile)
@pytest.mark.parametrize('data, expected_discarded', [
    (
        {'delivery': 'email', 'email': 'respondent@example.com', 'phone_number': '+15551234567'},
        'phone_number'
    ),
    (
        {'delivery': 'sms', 'phone_number': '+15551234567', 'email': 'respondent@example.com'},
        'email'
    ),
], ids=['email-chosen', 'sms-chosen'])
def test_the_channel_not_chosen_is_discarded(data, expected_discarded):
    # both inputs are submitted whichever one is on screen, so switching
    # between them must not leave the other one's value behind
    form = _form(data=data)

    assert form.is_valid(), form.errors
    assert form.cleaned_data[expected_discarded] == ''


@use(skip_turnstile)
@pytest.mark.parametrize('entered, expected', [
    ('+254712345678', '254712345678'),
    ('+1 (555) 123-4567', '15551234567'),
    ('  15551234567  ', '15551234567'),
], ids=['international', 'punctuation', 'whitespace'])
def test_phone_number_is_reduced_to_its_digits(entered, expected):
    form = _form(data={'delivery': 'sms', 'phone_number': entered})

    assert form.is_valid(), form.errors
    assert form.cleaned_data['phone_number'] == expected


@use(skip_turnstile)
@pytest.mark.parametrize('entered', [
    '  ',
    '555-CALL-NOW',
], ids=['only-punctuation', 'letters'])
def test_phone_number_rejects_non_digits(entered):
    form = _form(data={'delivery': 'sms', 'phone_number': entered})

    assert not form.is_valid()
    assert 'phone_number' in form.errors


@use('db', skip_turnstile)
@pytest.mark.parametrize('data, email, phone_number', [
    ({'delivery': 'email', 'email': 'respondent@example.com'},
     'respondent@example.com', ''),
    ({'delivery': 'sms', 'phone_number': '+15551234567'},
     '', '15551234567'),
], ids=['email', 'sms'])
def test_create_session_records_contact_info(
    data, email, phone_number
):
    webform = create_webform(allow_sms=True)
    form = PublicWebformLinkRequestForm(webform, data)
    assert form.is_valid(), form.errors

    session = form.create_session()

    assert session.public_webform == webform
    assert session.email == email
    assert session.phone_number == phone_number
