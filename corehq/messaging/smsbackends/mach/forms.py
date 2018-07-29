from __future__ import absolute_import
from __future__ import unicode_literals
from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from django.core.exceptions import ValidationError
from crispy_forms import layout as crispy
from django.utils.translation import ugettext_lazy as _


class MachBackendForm(BackendForm):
    account_id = TrimmedCharField(
        label=_("Account ID"),
    )
    password = TrimmedCharField(
        label=_("Password"),
    )
    sender_id = TrimmedCharField(
        label=_("Sender ID"),
    )
    max_sms_per_second = IntegerField(
        label=_("Max Outgoing SMS Per Second (as per account contract)"),
    )

    def clean_max_sms_per_second(self):
        value = self.cleaned_data["max_sms_per_second"]
        try:
            value = int(value)
            assert value > 0
        except AssertionError:
            raise ValidationError(_("Please enter a positive number"))
        return value

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Syniverse Settings"),
            'account_id',
            'password',
            'sender_id',
            'max_sms_per_second',
        )
