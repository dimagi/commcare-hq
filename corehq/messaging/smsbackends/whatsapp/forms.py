from django.utils.translation import ugettext_lazy as _

from corehq.apps.sms.forms import BackendForm
from crispy_forms import layout as crispy
from dimagi.utils.django.fields import TrimmedCharField


class WhatsAppBackendForm(BackendForm):
    phone_number = TrimmedCharField(
        label=_("Phone Number"),
        help_text=_('Phone number with international dialling code, excluding leading "+" or zeros.')
    )
    password = TrimmedCharField(
        label=_("WhatsApp Password"),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("WhatsApp Settings"),
            'phone_number',
            'password',
        )
