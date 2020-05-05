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

    def validate_phone_number(self, phone_number: str) -> None:
        from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend
        if not SQLTwilioBackend.phone_number_is_messaging_service_sid(phone_number):
            super().validate_phone_number(phone_number)
