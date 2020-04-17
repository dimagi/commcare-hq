from django.utils.translation import ugettext_lazy as _

from crispy_forms import layout as crispy

from dimagi.utils.django.fields import TrimmedCharField

from corehq.apps.sms.forms import BackendForm


class TurnBackendForm(BackendForm):
    client_auth_token = TrimmedCharField(label=_("Client Auth Token"))
    business_id = TrimmedCharField(label=_("Business ID"))
    template_namespace = TrimmedCharField(label=_("Template Namespace"))
    business_auth_token = TrimmedCharField(label=_("Business Auth Token"))

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Turn Settings"),
            "client_auth_token",
            "business_id",
            "template_namespace",
            "business_auth_token",
        )
