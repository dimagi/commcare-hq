from __future__ import absolute_import
from __future__ import unicode_literals

import codecs

from corehq.apps.sms.util import clean_phone_number
from corehq.apps.sms.api import incoming
from corehq.apps.sms.models import SQLSMSBackend
from six.moves.urllib.request import urlopen
from six.moves.urllib.parse import urlencode
from corehq.messaging.smsbackends.unicel.forms import UnicelBackendForm
from django.conf import settings

OUTBOUND_URLBASE = "http://www.unicel.in/SendSMS/sendmsg.php"


class InboundParams(object):
    """
    A constant-defining class for incoming sms params
    """
    SENDER = "send"
    MESSAGE = "msg"

    # 1 if message is multipart message, 0 otherwise
    UDHI = "UDHI"

    # gateway message id
    MID = "MID"

    # 8 if message is a unicode hex string, 0 if ascii
    DCS = "DCS"


class OutboundParams(object):
    """
    A constant-defining class for outbound sms params
    """
    SENDER = "send"
    MESSAGE = "msg"
    USERNAME = "uname"
    PASSWORD = "pass"
    DESTINATION = "dest"

# constant additional parameters when sending a unicode message
UNICODE_PARAMS = [("udhi", 0),
                  ("dcs", 8)]


class SQLUnicelBackend(SQLSMSBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'username',
            'password',
            'sender',
        ]

    @classmethod
    def get_api_id(cls):
        return 'UNICEL'

    @classmethod
    def get_generic_name(cls):
        return "Unicel"

    @classmethod
    def get_form_class(cls):
        return UnicelBackendForm

    def send(self, message, *args, **kwargs):
        config = self.config
        phone_number = clean_phone_number(message.phone_number).replace('+', '')
        params = [(OutboundParams.DESTINATION, phone_number),
                  (OutboundParams.USERNAME, config.username),
                  (OutboundParams.PASSWORD, config.password),
                  (OutboundParams.SENDER, config.sender)]
        try:
            text_as_ascii = message.text.encode('ascii')
            params.append((OutboundParams.MESSAGE, text_as_ascii))
        except UnicodeEncodeError:
            params.extend(UNICODE_PARAMS)
            encoded = message.text.encode('utf_16_be').encode('hex').upper()
            params.append((OutboundParams.MESSAGE, encoded))

        data = urlopen('%s?%s' % (OUTBOUND_URLBASE, urlencode(params)),
            timeout=settings.SMS_GATEWAY_TIMEOUT).read()

        return data


def create_from_request(request, backend_id=None):
    """
    From an inbound request (representing an incoming message),
    create a message (log) object with the right fields populated.
    """
    sender = request.GET[InboundParams.SENDER]
    message = request.GET[InboundParams.MESSAGE]

    if len(sender) == 10:
        # add india country code
        sender = '91' + sender

    is_unicode = request.GET.get(InboundParams.DCS, "") == "8"
    if is_unicode:
        message = codecs.decode(codecs.decode(message, 'hex'), 'utf_16_be')

    backend_message_id = request.GET.get(InboundParams.MID, None)

    log = incoming(sender, message, SQLUnicelBackend.get_api_id(), backend_message_id=backend_message_id,
        backend_id=backend_id)

    return log
