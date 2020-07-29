from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from django.forms import ChoiceField
from crispy_forms import layout as crispy
from django.utils.translation import ugettext_lazy as _

from corehq.apps.sms.models import SQLMobileBackend


class InfobipBackendForm(BackendForm):
    account_sid = TrimmedCharField(
        label=_("Account SID"),
        required=True
    )
    auth_token = TrimmedCharField(
        label=_("Auth Token"),
        required=True
    )
    personalized_subdomain = TrimmedCharField(
        label=_("Personalized Subdomain"),
        required=True
    )
    scenario_key = TrimmedCharField(
        label=_("Scenario Key"),
        help_text=_("Enables sendimg messages via whatsapp, viber, line and voice channel with or "
                    "without automatic failover to another channel according to the specific scenario."),
        required=False
    )
    fallback_backend_id = ChoiceField(
        label=_("Fallback Backend"),
        required=False
    )

    def clean_scenario_key(self):
        value = self.cleaned_data.get("scenario_key") or ""
        return value.strip() or None

    @property
    def gateway_specific_fields(self):
        domain_backends = SQLMobileBackend.get_domain_backends(
            SQLMobileBackend.SMS,
            self.domain,
        )
        backend_choices = [('', _("No Fallback Backend"))]
        backend_choices.extend([
            (backend.couch_id, backend.name) for backend in domain_backends
            if backend.id != self.backend_id
        ])
        self.fields['fallback_backend_id'].choices = backend_choices
        return crispy.Fieldset(
            _("Infobip Settings"),
            'account_sid',
            'auth_token',
            'personalized_subdomain',
            'scenario_key',
            'fallback_backend_id'
        )
