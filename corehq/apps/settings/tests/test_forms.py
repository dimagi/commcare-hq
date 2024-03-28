from django.test import SimpleTestCase, override_settings
from ..forms import HQTwoFactorMethodForm, HQApiKeyForm
from freezegun import freeze_time
from datetime import datetime
from zoneinfo import ZoneInfo


@override_settings(TWO_FACTOR_CALL_GATEWAY=True, TWO_FACTOR_SMS_GATEWAY=True)
class TestHQTwoFactorMethodForm(SimpleTestCase):
    def test_when_phone_support_is_enabled_all_options_are_shown(self):
        form = HQTwoFactorMethodForm(allow_phone_2fa=True)
        choices = self._get_choice_values(form.fields['method'].choices)
        self.assertSetEqual(choices, {'generator', 'call', 'sms'})

    def test_when_phone_support_is_disabled_phone_and_sms_are_not_listed(self):
        form = HQTwoFactorMethodForm(allow_phone_2fa=False)
        choices = self._get_choice_values(form.fields['method'].choices)
        self.assertNotIn('call', choices)
        self.assertNotIn('sms', choices)

    def test_when_fields_are_valid_form_is_valid(self):
        form = HQTwoFactorMethodForm(data={'method': 'call'}, allow_phone_2fa=True)
        self.assertTrue(form.is_valid())

    def test_when_phone_support_is_disabled_phone_is_invalid(self):
        form = HQTwoFactorMethodForm(data={'method': 'call'}, allow_phone_2fa=False)
        self.assertFalse(form.is_valid())

    def test_when_phone_support_is_disabled_sms_is_invalid(self):
        form = HQTwoFactorMethodForm(data={'method': 'sms'}, allow_phone_2fa=False)
        self.assertFalse(form.is_valid())

    @staticmethod
    def _get_choice_values(choices):
        return {choice[0] for choice in choices}


class HQApiKeyTests(SimpleTestCase):
    def test_form_domain_list(self):
        form = HQApiKeyForm(user_domains=['domain1', 'domain2'])
        domain_choices = form.fields['domain'].choices
        self.assertEqual(domain_choices, [('', 'All Projects'), ('domain1', 'domain1'), ('domain2', 'domain2')])

    def test_expiration_date_is_not_required_by_default(self):
        form = HQApiKeyForm()
        self.assertFalse(form.fields['expiration_date'].required)

    def test_when_expiration_is_specified_expiration_date_is_required(self):
        form = HQApiKeyForm(max_allowed_expiration_days=30)
        self.assertTrue(form.fields['expiration_date'].required)

    def test_when_expiration_is_specified_expiration_is_autopopulated_to_max_expiration(self):
        current_time = datetime(year=2023, month=1, day=1)
        with freeze_time(current_time):
            form = HQApiKeyForm(max_allowed_expiration_days=30)
            self.assertEqual(form.fields['expiration_date'].initial, '2023-01-31')

    def test_default_expiration_helptext(self):
        form = HQApiKeyForm()
        self.assertEqual(
            form.fields['expiration_date'].help_text,
            'Date and time the API key should expire on'
        )

    def test_when_expiration_is_specified_help_text_includes_max_expiration(self):
        current_time = datetime(year=2023, month=1, day=1)
        with freeze_time(current_time):
            form = HQApiKeyForm(max_allowed_expiration_days=30)
            self.assertEqual(
                form.fields['expiration_date'].help_text,
                'Date and time the API key should expire on. '
                'Must be no later than 30 days from today: Jan 31, 2023'
            )

    def test_expiration_supports_year_values(self):
        current_time = datetime(year=2023, month=1, day=1)
        with freeze_time(current_time):
            form = HQApiKeyForm(max_allowed_expiration_days=365)
            self.assertEqual(
                form.fields['expiration_date'].help_text,
                'Date and time the API key should expire on. '
                'Must be no later than 1 year from today: Jan 01, 2024'
            )

    def test_expiration_supports_unofficial_expiration_windows(self):
        current_time = datetime(year=2023, month=1, day=1)
        with freeze_time(current_time):
            form = HQApiKeyForm(max_allowed_expiration_days=22)
            self.assertEqual(
                form.fields['expiration_date'].help_text,
                'Date and time the API key should expire on. '
                'Must be no later than 22 days from today: Jan 23, 2023'
            )

    def test_no_expiration_date_is_valid(self):
        form = HQApiKeyForm(self._form_data(expiration_date=None))
        self.assertTrue(form.is_valid())

    def test_valid_expiration_date_with_maximum_expiration_window(self):
        current_time = datetime(year=2023, month=1, day=1)
        with freeze_time(current_time):
            form = HQApiKeyForm(self._form_data(expiration_date='2023-01-31'), max_allowed_expiration_days=30)
            self.assertTrue(form.is_valid())

    def test_expired_key_is_not_valid(self):
        current_time = datetime(year=2023, month=1, day=2)
        with freeze_time(current_time):
            form = HQApiKeyForm(self._form_data(expiration_date='2023-01-01'))
            self.assertFalse(form.is_valid())
            self.assertEqual(form.errors['expiration_date'], ['Expiration Date must be in the future'])

    def test_expiration_dates_greater_than_maximum_are_invalid(self):
        current_time = datetime(year=2023, month=1, day=1)
        with freeze_time(current_time):
            form = HQApiKeyForm(self._form_data(expiration_date='2023-02-01'), max_allowed_expiration_days=30)
            self.assertFalse(form.is_valid())
            self.assertEqual(
                form.errors['expiration_date'],
                ['Your Identity Provider does not allow expiration dates beyond Jan 31, 2023']
            )

    def test_expiration_date_is_localized(self):
        tz = ZoneInfo('US/Eastern')
        current_time = datetime(year=2023, month=1, day=2, hour=23, tzinfo=tz)
        with freeze_time(current_time):
            form = HQApiKeyForm(max_allowed_expiration_days=30, timezone=tz)
            # 11 PM Eastern time will wrap over to the next day in UTC
            # So if we aren't localizing the date, this would be '2023-02-02'
            self.assertEqual(form.fields['expiration_date'].initial, '2023-02-01')

    def _form_data(self, expiration_date='2023-01-01'):
        data = {
            'name': 'TestKey',
        }

        if expiration_date:
            data['expiration_date'] = expiration_date

        return data
