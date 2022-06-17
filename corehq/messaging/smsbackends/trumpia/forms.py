from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from crispy_forms import layout as crispy

from dimagi.utils.django.fields import TrimmedCharField

from corehq.apps.sms.forms import BackendForm


class TrumpiaBackendForm(BackendForm):
    username = TrimmedCharField(label=gettext_lazy("Username"), required=True)
    api_key = TrimmedCharField(label=gettext_lazy("API Key"), required=True)

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Trumpia Settings"),
            'username',
            'api_key',
        )
