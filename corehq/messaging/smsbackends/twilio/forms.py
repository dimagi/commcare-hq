from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.sms.forms import BackendForm, LoadBalancingBackendFormMixin
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy
from django.utils.translation import ugettext_lazy as _


class TwilioBackendForm(BackendForm, LoadBalancingBackendFormMixin):
    account_sid = TrimmedCharField(
        label=_("Account SID"),
    )
    auth_token = TrimmedCharField(
        label=_("Auth Token"),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Twilio Settings"),
            'account_sid',
            'auth_token',
        )
