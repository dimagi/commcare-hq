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
    personalized_subdomain = TrimmedCharField(
        label=_("Personalized Subdomain"),
    )
    scenario_key = TrimmedCharField(
        label=_("Scenario Key"),
        help_text=_("Enables sendimg messages via whatsapp, viber, line and voice channel with or "
                    "without automatic failover to another channel according to the specific scenario."),
        required=False
    )

    def clean_scenario_key(self):
        value = self.cleaned_data.get("scenario_key") or ""
        return value.strip() or None

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Infobip Settings"),
            'account_sid',
            'auth_token',
            'personalized_subdomain',
            'scenario_key'
        )
