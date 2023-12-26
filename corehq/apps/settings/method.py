from two_factor.plugins.phonenumber.method import PhoneCallMethod, SMSMethod
from two_factor.plugins.registry import GeneratorMethod

from corehq.apps.settings.forms import HQPhoneNumberForm, HQTOTPDeviceForm


class HQGeneratorMethod(GeneratorMethod):

    form_path = 'corehq.apps.settings.forms.HQTOTPDeviceForm'

    def get_setup_forms(self, *args):
        return {self.code: HQTOTPDeviceForm}


class HQPhoneCallMethod(PhoneCallMethod):

    form_path = 'corehq.apps.settings.forms.HQPhoneNumberForm'

    def get_setup_forms(self, *args):
        return {self.code: HQPhoneNumberForm}


class HQSMSMethod(SMSMethod):

    form_path = 'corehq.apps.settings.forms.HQPhoneNumberForm'

    def get_setup_forms(self, *args):
        return {self.code: HQPhoneNumberForm}
