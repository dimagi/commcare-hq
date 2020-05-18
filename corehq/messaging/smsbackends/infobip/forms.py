from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy
from django.utils.translation import ugettext_lazy as _


class InfobipBackendForm(BackendForm):
    account_sid = TrimmedCharField(
        label=_("Account SID"),
    )
    auth_token = TrimmedCharField(
        label=_("Auth Token"),
    )

    scenario_key = TrimmedCharField(
        label=_("Scenario Key"),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Infobip Settings"),
            'account_sid',
            'auth_token',
            'scenario_key'
        )
