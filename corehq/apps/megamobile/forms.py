from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy
from django.utils.translation import ugettext_lazy as _


class MegamobileBackendForm(BackendForm):
    api_account_name = TrimmedCharField(
        label=_("API Account Name"),
    )
    source_identifier = TrimmedCharField(
        label=_("Source Identifier"),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Megamobile Settings"),
            'api_account_name',
            'source_identifier',
        )
