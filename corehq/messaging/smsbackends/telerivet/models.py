from __future__ import absolute_import
from __future__ import unicode_literals
import requests
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.sms.models import SQLSMSBackend, SMS
from corehq.messaging.smsbackends.telerivet.exceptions import TelerivetException
from corehq.messaging.smsbackends.telerivet.forms import TelerivetBackendForm
from django.conf import settings
from django.db import models
from requests.exceptions import RequestException

MESSAGE_TYPE_SMS = "sms"


class SQLTelerivetBackend(SQLSMSBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            # The api key of the account to send from.
            'api_key',
            # The Telerivet project id.
            'project_id',
            # The id of the phone to send from, as shown on Telerivet's API page.
            'phone_id',
            # The Webhook Secret that gets posted to hq on every request
            'webhook_secret',
            # If None, ignored. Otherwise, the country code to append to numbers
            # in inbound requests if not already there.
            'country_code',
        ]

    @classmethod
    def get_api_id(cls):
        return 'TELERIVET'

    @classmethod
    def get_generic_name(cls):
        return "Telerivet (Android)"

    @classmethod
    def get_form_class(cls):
        return TelerivetBackendForm

    def get_phone_info(self):
        config = self.config
        url = ('https://api.telerivet.com/v1/projects/{}/phones/{}'
               .format(config.project_id, config.phone_id))

        response = requests.post(
            url,
            auth=(config.api_key, ''),
            verify=True,
            timeout=settings.SMS_GATEWAY_TIMEOUT,
        )

        return response.json()

    def get_phone_number_or_none(self):
        try:
            info = self.get_phone_info()
        except RequestException:
            return None

        return info.get('phone_number')

    def send(self, msg, *args, **kwargs):
        config = self.config
        payload = {
            'route_id': config.phone_id,
            'to_number': msg.phone_number,
            'content': msg.text,
            'message_type': MESSAGE_TYPE_SMS,
        }
        url = 'https://api.telerivet.com/v1/projects/%s/messages/send' % config.project_id

        # Sending with the json param automatically sets the Content-Type header to application/json
        response = requests.post(
            url,
            auth=(config.api_key, ''),
            json=payload,
            verify=True,
            timeout=settings.SMS_GATEWAY_TIMEOUT,
        )

        if response.status_code == 200:
            result = response.json()
            if 'error' in result:
                raise TelerivetException("Error with backend %s: %s" % (self.pk, result['error']['code']))

            msg.backend_message_id = result.get('id')
        elif response.status_code in (401, 402):
            # These are account-related errors, retrying won't help
            msg.set_system_error(SMS.ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS)
        else:
            raise TelerivetException(
                "Received HTTP response status code %s from backend %s" % (response.status_code, self.pk)
            )

    @classmethod
    def by_webhook_secret(cls, webhook_secret):
        # This isn't ideal right now, but this table has so few records
        # that it shouldn't be a performance problem. Longer term, we'll
        # move the webhook_secret to be the api_key and then we can query
        # for this directly.
        result = cls.active_objects.filter(
            hq_api_id=cls.get_api_id()
        )
        result_by_webhook = {
            backend.config.webhook_secret: backend
            for backend in result
        }
        return result_by_webhook.get(webhook_secret)


class IncomingRequest(models.Model):
    """
    A log of all requests that Telerivet makes to CommCareHQ,
    to be used for debugging.
    """
    event = models.CharField(max_length=255, null=True)
    message_id = models.CharField(max_length=255, null=True)
    message_type = models.CharField(max_length=255, null=True)
    content = models.TextField(null=True)
    from_number = models.CharField(max_length=255, null=True)
    from_number_e164 = models.CharField(max_length=255, null=True)
    to_number = models.CharField(max_length=255, null=True)
    time_created = models.CharField(max_length=255, null=True)
    time_sent = models.CharField(max_length=255, null=True)
    contact_id = models.CharField(max_length=255, null=True)
    phone_id = models.CharField(max_length=255, null=True)
    service_id = models.CharField(max_length=255, null=True)
    project_id = models.CharField(max_length=255, null=True)
    secret = models.CharField(max_length=255, null=True, db_index=True)

    @classmethod
    def get_last_sms_by_webhook_secret(cls, webhook_secret):
        from corehq.messaging.smsbackends.telerivet.tasks import MESSAGE_TYPE_SMS
        result = cls.objects.filter(
            secret=webhook_secret,
            message_type=MESSAGE_TYPE_SMS
        ).order_by('-time_created')[:1]

        if len(result) == 1:
            return result[0]

        return None
