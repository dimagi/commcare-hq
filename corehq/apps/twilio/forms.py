from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField

class TwilioBackendForm(BackendForm):
    account_sid = TrimmedCharField()
    auth_token = TrimmedCharField()
    phone_number = TrimmedCharField()

