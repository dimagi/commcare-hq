from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.sms.forms import BackendForm
from corehq.util.validation import is_url_or_host_banned
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy, ugettext as _


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
        value = self.cleaned_data.get("host")
        if is_url_or_host_banned(value):
            raise ValidationError(_("Invalid Host"))
        return value
