from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy
from django.utils.translation import gettext_lazy, gettext as _


class SMSGHBackendForm(BackendForm):
    from_number = TrimmedCharField(
        label=gettext_lazy("From Number"),
    )
    client_id = TrimmedCharField(
        label=gettext_lazy("Client Id"),
    )
    client_secret = TrimmedCharField(
        label=gettext_lazy("Client Secret"),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("SMSGH Settings"),
            'from_number',
            'client_id',
            'client_secret',
        )
