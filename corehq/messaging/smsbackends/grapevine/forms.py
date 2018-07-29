from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy
from django.utils.translation import ugettext_lazy as _


class GrapevineBackendForm(BackendForm):
    affiliate_code = TrimmedCharField(
        label=_("Affiliate Code"),
    )
    authentication_code = TrimmedCharField(
        label=_("Authentication Code"),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Grapevine Settings"),
            'affiliate_code',
            'authentication_code',
        )




