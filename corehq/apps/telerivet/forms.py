from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField

class TelerivetBackendForm(BackendForm):
    api_key = TrimmedCharField()
    project_id = TrimmedCharField()
    phone_id = TrimmedCharField()

