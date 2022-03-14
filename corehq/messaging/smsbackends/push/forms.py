from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy
from django.utils.translation import gettext_lazy, gettext as _


class PushBackendForm(BackendForm):
    channel = TrimmedCharField(
        label=gettext_lazy("Channel"),
    )
    service = TrimmedCharField(
        label=gettext_lazy("Service"),
    )
    password = TrimmedCharField(
        label=gettext_lazy("Password"),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Push Settings"),
            'channel',
            'service',
            'password',
        )
