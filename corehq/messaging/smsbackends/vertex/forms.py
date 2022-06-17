from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy
from django.utils.translation import gettext_lazy, gettext as _


class VertexBackendForm(BackendForm):
    username = TrimmedCharField(
        label=gettext_lazy("username"),
        required=True,
    )
    password = TrimmedCharField(
        label=gettext_lazy("password"),
        required=True,
    )
    senderid = TrimmedCharField(
        label=gettext_lazy("senderid"),
        required=True,
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Vertex Settings"),
            'username',
            'password',
            'senderid',
        )
