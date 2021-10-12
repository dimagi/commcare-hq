from django.test import SimpleTestCase, override_settings
from ..forms import HQTwoFactorMethodForm


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
