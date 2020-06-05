from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy
from django.utils.translation import ugettext_lazy as _


class PinpointBackendForm(BackendForm):
    project_id = TrimmedCharField(
        label=_("Project ID"),
        required=True
    )
    region = TrimmedCharField(
        label=_("Region"),
        required=True
    )
    access_key = TrimmedCharField(
        label=_("Access Key"),
        required=True
    )
    secret_access_key = TrimmedCharField(
        label=_("Secret Access Key"),
        required=True
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Pinpoint Settings"),
            'project_id',
            'region',
            'access_key',
            'secret_access_key'
        )
