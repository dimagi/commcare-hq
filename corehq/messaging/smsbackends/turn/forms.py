from django.utils.translation import ugettext_lazy as _

from crispy_forms import layout as crispy
from django.forms import ChoiceField

from dimagi.utils.django.fields import TrimmedCharField

from corehq.apps.sms.forms import BackendForm
from corehq.apps.sms.models import SQLMobileBackend


class TurnBackendForm(BackendForm):
    client_auth_token = TrimmedCharField(label=_("Client Auth Token"))
    business_id = TrimmedCharField(label=_("Business ID"))
    template_namespace = TrimmedCharField(label=_("Template Namespace"))
    business_auth_token = TrimmedCharField(label=_("Business Auth Token"))
    fallback_backend_id = ChoiceField(label=_("Fallback Backend"), required=False)

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
            _("Turn Settings"),
            "client_auth_token",
            "business_id",
            "template_namespace",
            "business_auth_token",
            "fallback_backend_id",
        )
