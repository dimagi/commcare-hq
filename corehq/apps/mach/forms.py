from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm

class MachBackendForm(BackendForm):
    account_id = CharField()
    password = CharField()
    sender_id = CharField()

