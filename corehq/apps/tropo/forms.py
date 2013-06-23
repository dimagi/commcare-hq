from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField

class TropoBackendForm(BackendForm):
    messaging_token = TrimmedCharField()

