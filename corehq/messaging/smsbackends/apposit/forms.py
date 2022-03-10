from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from crispy_forms import layout as crispy

from dimagi.utils.django.fields import TrimmedCharField

from corehq.apps.sms.forms import BackendForm

from ..http.form_handling import form_clean_url


class AppositBackendForm(BackendForm):
    application_id = TrimmedCharField(
        label=ugettext_lazy("Application Id"),
    )
    application_token = TrimmedCharField(
        label=ugettext_lazy("Application Token"),
    )
    from_number = TrimmedCharField(
        label=ugettext_lazy("From Number"),
    )
    host = TrimmedCharField(
        label=ugettext_lazy("Host"),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Apposit Settings"),
            'application_id',
            'application_token',
            'from_number',
            'host',
        )

    def clean_host(self):
        host = self.cleaned_data.get("host")
        return form_clean_url(host)
