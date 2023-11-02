from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from two_factor.plugins.registry import registry

from corehq.apps.hqwebapp.two_factor_methods import (
    HQGeneratorMethod,
    HQPhoneCallMethod,
    HQSMSMethod,
)

from ..forms import HQTwoFactorMethodForm


@override_settings(TWO_FACTOR_CALL_GATEWAY=True, TWO_FACTOR_SMS_GATEWAY=True)
class TestHQTwoFactorMethodForm(SimpleTestCase):

    def test_when_phone_support_is_enabled_all_options_are_shown(self):
        self.mock_get_methods.return_value = [HQGeneratorMethod(), HQPhoneCallMethod(), HQSMSMethod()]
        form = HQTwoFactorMethodForm()
        choices = self._get_choice_values(form.fields['method'].choices)
        self.assertSetEqual(choices, {'generator', 'call', 'sms'})

    def test_when_phone_support_is_disabled_phone_and_sms_are_not_listed(self):
        self.mock_get_methods.return_value = [HQGeneratorMethod()]
        form = HQTwoFactorMethodForm()
        choices = self._get_choice_values(form.fields['method'].choices)
        self.assertNotIn('call', choices)
        self.assertNotIn('sms', choices)

    def test_when_fields_are_valid_form_is_valid(self):
        self.mock_get_methods.return_value = [HQGeneratorMethod(), HQPhoneCallMethod(), HQSMSMethod()]
        form = HQTwoFactorMethodForm(data={'method': 'call'})
        self.assertTrue(form.is_valid())

    def test_when_phone_support_is_disabled_phone_is_invalid(self):
        self.mock_get_methods.return_value = [HQGeneratorMethod()]
        form = HQTwoFactorMethodForm(data={'method': 'call'})
        self.assertFalse(form.is_valid())

    def test_when_phone_support_is_disabled_sms_is_invalid(self):
        self.mock_get_methods.return_value = [HQGeneratorMethod()]
        form = HQTwoFactorMethodForm(data={'method': 'sms'})
        self.assertFalse(form.is_valid())

    def setUp(self):
        patcher = patch.object(registry, 'get_methods')
        self.mock_get_methods = patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def _get_choice_values(choices):
        return {choice[0] for choice in choices}
