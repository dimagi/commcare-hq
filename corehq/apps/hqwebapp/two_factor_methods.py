from django_otp.plugins.otp_totp.models import TOTPDevice

from two_factor.plugins.phonenumber.method import PhoneCallMethod, SMSMethod
from two_factor.plugins.registry import GeneratorMethod

from corehq.apps.hqwebapp.forms import HQAuthenticationTokenForm
from corehq.apps.settings.forms import HQPhoneNumberForm, HQTOTPDeviceForm


class HQGeneratorMethod(GeneratorMethod):

    # only overriding this because it is set in GeneratorMethod
    form_path = 'corehq.apps.settings.forms.HQTOTPDeviceForm'

    def get_setup_forms(self, *args):
        return {self.code: HQTOTPDeviceForm}

    def get_token_form_class(self):
        return HQAuthenticationTokenForm

    def recognize_device(self, device):
        return isinstance(device, TOTPDevice)


class HQPhoneCallMethod(PhoneCallMethod):

    def get_setup_forms(self, *args):
        return {self.code: HQPhoneNumberForm}

    def get_token_form_class(self):
        return HQAuthenticationTokenForm


class HQSMSMethod(SMSMethod):

    def get_setup_forms(self, *args):
        return {self.code: HQPhoneNumberForm}

    def get_token_form_class(self):
        return HQAuthenticationTokenForm
