from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from django.forms import PasswordInput
from crispy_forms import layout as crispy
from django.utils.translation import ugettext_lazy as _


class TurnBackendForm(BackendForm):
    username = TrimmedCharField(
        label=_("Account Username"),
    )
    password = TrimmedCharField(
        label=_("Password"),
        widget=PasswordInput,
    )
    auth_token = TrimmedCharField(
        label=_("Auth Token"),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Turn Settings"),
            'username',
            'password',
            'auth_token',
        )
