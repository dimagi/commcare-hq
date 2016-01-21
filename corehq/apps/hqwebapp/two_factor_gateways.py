from django.utils.translation import ugettext as _
from twilio.rest import TwilioRestClient

from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend

class Gateway(object):

    def __init__(self):
        backends = SQLTwilioBackend.objects.filter(hq_api_id='TWILIO', deleted=False, is_global=True)
        sid = backends[0].extra_fields['account_sid']
        token = backends[0].extra_fields['auth_token']
        self.from_number = backends[0].load_balancing_numbers[0]
        self.client = TwilioRestClient(sid, token)

    def send_sms(self, device, token):
        message = _('Your authentication token is %s') % token
        self.client.sms.messages.create(
            to=device.number,
            from_=self.from_number,
            body=message)