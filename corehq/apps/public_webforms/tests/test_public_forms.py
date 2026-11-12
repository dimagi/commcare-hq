import pytest
from unmagic import use
from unittest.mock import patch

from corehq.apps.public_webforms.models import PublicWebform
from corehq.apps.public_webforms.public.forms import (
    PublicWebformLinkRequestForm,
)
from corehq.apps.public_webforms.tests.utils import (
    create_webform,
    skip_turnstile,
)


@use(skip_turnstile)
class TestPublicWebformLinkRequestForm:

    @pytest.mark.parametrize('allow_email, allow_sms, expected', [
        (True, False, ['email']),
        (False, True, ['sms']),
        (True, True, ['email', 'sms']),
    ], ids=['email-only', 'sms-only', 'both'])
    def test_delivery_offers_only_the_channels_the_webform_allows(
        self, allow_email, allow_sms, expected
    ):
        form = self._form(allow_email=allow_email, allow_sms=allow_sms)

        choices = form.fields['delivery'].choices
        assert [choice[0] for choice in choices] == expected

    def test_sms_is_not_offered_when_the_project_cannot_send_sms(self):
        form = self._form(allow_email=True, allow_sms=True, project_can_send_sms=False)

        choices = form.fields['delivery'].choices
        assert [choice[0] for choice in choices] == ['email']

    @pytest.mark.parametrize('allow_email, allow_sms, expected', [
        (True, True, True),
        (True, False, False),
        (False, True, False),
    ], ids=['both', 'email-only', 'sms-only'])
    def test_a_choice_is_offered_only_when_both_channels_are_allowed(
        self, allow_email, allow_sms, expected
    ):
        form = self._form(allow_email=allow_email, allow_sms=allow_sms)

        assert form.can_choose_delivery is expected

    @pytest.mark.parametrize('allow_email, allow_sms, delivery', [
        (True, False, 'sms'),
        (False, True, 'email'),
    ], ids=['sms-not-allowed', 'email-not-allowed'])
    def test_a_channel_the_webform_disallows_is_rejected(
        self, allow_email, allow_sms, delivery
    ):
        form = self._form(
            allow_email=allow_email, allow_sms=allow_sms,
            data={'delivery': delivery},
        )

        assert not form.is_valid()
        assert 'delivery' in form.errors

    @pytest.mark.parametrize('delivery, missing', [
        ('email', 'email'),
        ('sms', 'phone_number'),
    ], ids=['email', 'sms'])
    def test_the_chosen_channel_needs_contact_information(self, delivery, missing):
        form = self._form(data={'delivery': delivery})

        assert not form.is_valid()
        assert missing in form.errors

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
    def test_the_channel_not_chosen_is_discarded(self, data, expected_discarded):
        # both inputs are submitted whichever one is on screen, so switching
        # between them must not leave the other one's value behind
        form = self._form(data=data)

        assert form.is_valid(), form.errors
        assert form.cleaned_data[expected_discarded] == ''

    @pytest.mark.parametrize('entered, expected', [
        ('+254712345678', '254712345678'),
        ('+1 (555) 123-4567', '15551234567'),
        ('  15551234567  ', '15551234567'),
    ], ids=['international', 'punctuation', 'whitespace'])
    def test_phone_number_is_reduced_to_its_digits(self, entered, expected):
        form = self._form(data={'delivery': 'sms', 'phone_number': entered})

        assert form.is_valid(), form.errors
        assert form.cleaned_data['phone_number'] == expected

    @pytest.mark.parametrize('entered', [
        '  ',
        '555-CALL-NOW',
    ], ids=['only-punctuation', 'letters'])
    def test_phone_number_rejects_non_digits(self, entered):
        form = self._form(data={'delivery': 'sms', 'phone_number': entered})

        assert not form.is_valid()
        assert 'phone_number' in form.errors

    @use('db')
    @pytest.mark.parametrize('data, email, phone_number', [
        ({'delivery': 'email', 'email': 'respondent@example.com'},
         'respondent@example.com', None),
        ({'delivery': 'sms', 'phone_number': '+15551234567'},
         None, '15551234567'),
    ], ids=['email', 'sms'])
    def test_a_session_records_contact_info(
        self, data, email, phone_number
    ):
        webform = create_webform(allow_sms=True)
        with patch('corehq.apps.public_webforms.public.forms.domain_can_send_sms', return_value=True):
            form = PublicWebformLinkRequestForm(webform, data)
            assert form.is_valid(), form.errors

        session = form.get_or_create_session()

        assert session.public_webform == webform
        assert session.email == email
        assert session.phone_number == phone_number

    @use('db')
    def test_asking_twice_returns_the_link_already_sent(self):
        webform = create_webform()
        form = PublicWebformLinkRequestForm(
            webform, {'delivery': 'email', 'email': 'respondent@example.com'}
        )
        assert form.is_valid(), form.errors

        first = form.get_or_create_session()
        second = form.get_or_create_session()

        assert second == first

    def _form(self, allow_email=True, allow_sms=True, project_can_send_sms=True, data=None):
        webform = PublicWebform(allow_email=allow_email, allow_sms=allow_sms)
        with patch(
            'corehq.apps.public_webforms.public.forms.domain_can_send_sms',
            return_value=project_can_send_sms,
        ):
            return PublicWebformLinkRequestForm(webform, data)
