from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from django.forms import PasswordInput
from crispy_forms import layout as crispy
from django.utils.translation import ugettext_lazy as _


class TurnBackendForm(BackendForm):
    client_auth_token = TrimmedCharField(
        label=_("Client Auth Token"),
    )
    business_id = TrimmedCharField(
        label=_("Business ID"),
    )
    business_auth_token = TrimmedCharField(
        label=_("Business Auth Token"),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Turn Settings"),
            'client_auth_token',
            'business_id',
            'business_auth_token',
        )
