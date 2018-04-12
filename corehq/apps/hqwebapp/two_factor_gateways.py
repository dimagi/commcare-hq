from __future__ import absolute_import
from __future__ import unicode_literals
from six.moves.urllib.parse import urlencode

from django.utils import translation
from django.utils.translation import ugettext as _
from django.utils.translation import pgettext
from twilio.rest import Client
from django.contrib.sites.models import Site
from django.urls import reverse

from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend


VOICE_LANGUAGES = ('en', 'en-gb', 'es', 'fr', 'it', 'de', 'da-DK', 'de-DE',
                   'en-AU', 'en-CA', 'en-GB', 'en-IN', 'en-US', 'ca-ES',
                   'es-ES', 'es-MX', 'fi-FI', 'fr-CA', 'fr-FR', 'it-IT',
                   'ja-JP', 'ko-KR', 'nb-NO', 'nl-NL', 'pl-PL', 'pt-BR',
                   'pt-PT', 'ru-RU', 'sv-SE', 'zh-CN', 'zh-HK', 'zh-TW')


class Gateway(object):

    def __init__(self):
        backends = SQLTwilioBackend.objects.filter(hq_api_id='TWILIO', deleted=False, is_global=True)
        sid = backends[0].extra_fields['account_sid']
        token = backends[0].extra_fields['auth_token']
        self.from_number = backends[0].load_balancing_numbers[0]
        self.client = Client(sid, token)

    def send_sms(self, device, token):
        message = _('Your authentication token is %s') % token
        self.client.api.account.messages.create(
            to=device.number.as_e164,
            from_=self.from_number,
            body=message)

    def make_call(self, device, token):
        locale = translation.get_language()
        validate_voice_locale(locale)

        url = reverse('two_factor:twilio_call_app', kwargs={'token': token})
        url = '%s?%s' % (url, urlencode({'locale': locale}))
        uri = 'https://%s%s' % (Site.objects.get_current().domain, url)
        self.client.api.account.calls.create(to=device.number.as_e164, from_=self.from_number,
                                 url=uri, method='GET', if_machine='Hangup', timeout=15)


def validate_voice_locale(locale):
    with translation.override(locale):
        voice_locale = pgettext('twilio_locale', 'en')
        if voice_locale not in VOICE_LANGUAGES:
            raise NotImplementedError('The language "%s" is not '
                                      'supported by Twilio' % voice_locale)
