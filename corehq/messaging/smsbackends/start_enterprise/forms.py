from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy
from django.utils.translation import gettext_lazy, gettext as _


class StartEnterpriseBackendForm(BackendForm):
    username = TrimmedCharField(
        label=gettext_lazy("Username"),
        required=True,
    )
    password = TrimmedCharField(
        label=gettext_lazy("Password"),
        required=True,
    )
    sender_id = TrimmedCharField(
        label=gettext_lazy("Sender Id"),
        required=True,
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Start Enterprise Settings"),
            'username',
            'password',
            'sender_id',
        )
