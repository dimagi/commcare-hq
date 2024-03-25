from django.test import SimpleTestCase, override_settings

from two_factor.plugins.registry import registry

from corehq.apps.hqwebapp.apps import register_two_factor_methods
from corehq.apps.hqwebapp.two_factor_methods import (
    HQGeneratorMethod,
    HQPhoneCallMethod,
    HQSMSMethod,
)


@override_settings(
    ALLOW_PHONE_AS_DEFAULT_TWO_FACTOR_DEVICE=True,
    TWO_FACTOR_SMS_GATEWAY='corehq.apps.hqwebapp.two_factor_gateways.Gateway',
    TWO_FACTOR_CALL_GATEWAY='corehq.apps.hqwebapp.two_factor_gateways.Gateway',
)
class RegisterCustom2FAMethodsTests(SimpleTestCase):

    @override_settings(
        ALLOW_PHONE_AS_DEFAULT_TWO_FACTOR_DEVICE=False,
        TWO_FACTOR_SMS_GATEWAY=None,
        TWO_FACTOR_CALL_GATEWAY=None,
    )
    def test_custom_generator_method_is_registered(self):
        register_two_factor_methods()
        method = registry.get_method('generator')
        self.assertIsInstance(method, HQGeneratorMethod)

    @override_settings(TWO_FACTOR_SMS_GATEWAY=None)
    def test_custom_call_method_is_registered_if_relevant_settings_are_true(self):
        register_two_factor_methods()
        method = registry.get_method('call')
        self.assertIsInstance(method, HQPhoneCallMethod)

    @override_settings(TWO_FACTOR_CALL_GATEWAY=None)
    def test_custom_sms_method_is_registered_if_relevant_settings_are_true(self):
        register_two_factor_methods()
        method = registry.get_method('sms')
        self.assertIsInstance(method, HQSMSMethod)

    @override_settings(ALLOW_PHONE_AS_DEFAULT_TWO_FACTOR_DEVICE=False)
    def test_neither_phone_method_is_registered_if_allow_phone_setting_is_false(self):
        register_two_factor_methods()
        self.assertIsNone(registry.get_method('call'))
        self.assertIsNone(registry.get_method('sms'))
