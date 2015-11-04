from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy
from django.utils.translation import ugettext_lazy as _


class UnicelBackendForm(BackendForm):
    username = TrimmedCharField(
        label=_("Username"),
    )
    password = TrimmedCharField(
        label=_("Password"),
    )
    sender = TrimmedCharField(
        label=_("Sender ID"),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Unicel Settings"),
            'username',
            'password',
            'sender',
        )
