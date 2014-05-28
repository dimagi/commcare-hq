from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

class MachBackendForm(BackendForm):
    account_id = TrimmedCharField()
    password = TrimmedCharField()
    sender_id = TrimmedCharField()
    max_sms_per_second = IntegerField()

    def clean_max_sms_per_second(self):
        value = self.cleaned_data["max_sms_per_second"]
        try:
            value = int(value)
            assert value > 0
        except AssertionError:
            raise ValidationError(_("Please enter a positive number"))
        return value

