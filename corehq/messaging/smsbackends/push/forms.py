from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy
from django.utils.translation import ugettext_lazy, ugettext as _


class PushBackendForm(BackendForm):
    channel = TrimmedCharField(
        label=ugettext_lazy("Channel"),
    )
    service = TrimmedCharField(
        label=ugettext_lazy("Service"),
    )
    password = TrimmedCharField(
        label=ugettext_lazy("Password"),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Push Settings"),
            'channel',
            'service',
            'password',
        )
