from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm

class TropoBackendForm(BackendForm):
    messaging_token = CharField()

