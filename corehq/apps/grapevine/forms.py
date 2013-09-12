from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField


class GrapevineBackendForm(BackendForm):
    affiliate_code = TrimmedCharField()
    authentication_code = TrimmedCharField()

