from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm, LoadBalancingBackendFormMixin
from dimagi.utils.django.fields import TrimmedCharField

class TwilioBackendForm(BackendForm, LoadBalancingBackendFormMixin):
    account_sid = TrimmedCharField()
    auth_token = TrimmedCharField()

