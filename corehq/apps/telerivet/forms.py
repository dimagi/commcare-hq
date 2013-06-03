from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm

class TelerivetBackendForm(BackendForm):
    api_key = CharField()
    project_id = CharField()
    phone_id = CharField()

