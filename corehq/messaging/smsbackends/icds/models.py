from urllib import urlencode
from urllib2 import urlopen

from crispy_forms import layout as crispy
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from corehq.apps.sms.models import SQLSMSBackend
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField


class ICDSBackendForm(BackendForm):
    username = TrimmedCharField(
        label=_('Username'),
    )
    pin = TrimmedCharField(
        label=_('PIN'),
    )
    sender_id = TrimmedCharField(
        label=_('Sender ID'),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("ICDS Settings"),
            'username',
            'pin',
            'sender_id',
        )


class SQLICDSBackend(SQLSMSBackend):

    class Meta:
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'username',
            'pin',
            'sender_id',
        ]

    @classmethod
    def get_api_id(cls):
        return 'ICDS'

    @classmethod
    def get_generic_name(cls):
        return "ICDS"

    @classmethod
    def get_form_class(cls):
        return ICDSBackendForm

    def send(self, msg, orig_phone_number=None, *args, **kwargs):
        config = self.config
        phone_number = msg.phone_number
        try:
            text = msg.text.encode("iso-8859-1")
            msg_type = "PM"
        except UnicodeEncodeError:
            text = msg.text.encode("utf-8")
            msg_type = "UC"
        params = {
            "username": config.username,
            "pin": config.pin,
            "mnumber": phone_number,
            "message": text,
            "signature": config.sender_id,
            "msgType": msg_type
        }
        url_params = urlencode(params)
        url = 'https://smsgw.sms.gov.in/failsafe/HttpLink?%s' % url_params
        response = urlopen("%s?%s" % (url, url_params),
                           timeout=settings.SMS_GATEWAY_TIMEOUT).read()
