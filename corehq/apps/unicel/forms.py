from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField

class UnicelBackendForm(BackendForm):
    username = TrimmedCharField()
    password = TrimmedCharField()
    sender = TrimmedCharField()

