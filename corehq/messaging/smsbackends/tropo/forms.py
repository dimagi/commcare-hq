from django.forms.fields import *
from django.utils.translation import ugettext_lazy as _
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy


class TropoBackendForm(BackendForm):
    messaging_token = TrimmedCharField(
        label=_("Messaging Token")
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Tropo Settings"),
            'messaging_token',
        )
