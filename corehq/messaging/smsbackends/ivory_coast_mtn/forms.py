from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy
from django.utils.translation import ugettext_lazy, ugettext as _


class IvoryCoastMTNBackendForm(BackendForm):
    customer_id = TrimmedCharField(
        label=ugettext_lazy("Customer ID"),
        required=True,
    )
    username = TrimmedCharField(
        label=ugettext_lazy("Username"),
        required=True,
    )
    password = TrimmedCharField(
        label=ugettext_lazy("Password"),
        required=True,
    )
    sender_id = TrimmedCharField(
        label=ugettext_lazy("Sender ID"),
        required=True,
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Ivory Coast MTN Settings"),
            'customer_id',
            'username',
            'password',
            'sender_id',
        )
