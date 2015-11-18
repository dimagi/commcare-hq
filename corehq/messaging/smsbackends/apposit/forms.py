from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy
from django.utils.translation import ugettext_lazy, ugettext as _


class AppositBackendForm(BackendForm):
    from_number = TrimmedCharField(
        label=ugettext_lazy("From Number"),
    )
    username = TrimmedCharField(
        label=ugettext_lazy("Username"),
    )
    password = TrimmedCharField(
        label=ugettext_lazy("Password"),
    )
    service_id = TrimmedCharField(
        label=ugettext_lazy("Service Id"),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Apposit Settings"),
            'from_number',
            'username',
            'password',
            'service_id',
        )
