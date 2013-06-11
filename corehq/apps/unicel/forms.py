from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm

class UnicelBackendForm(BackendForm):
    username = CharField()
    password = CharField()
    sender = CharField()

