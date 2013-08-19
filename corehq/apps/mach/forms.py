from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField

class MachBackendForm(BackendForm):
    account_id = TrimmedCharField()
    password = TrimmedCharField()
    sender_id = TrimmedCharField()

