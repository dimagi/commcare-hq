import os
import requests
from dimagi.ext.couchdbkit import *
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.sms.models import SQLSMSBackend
from corehq.messaging.smsbackends.telerivet.forms import TelerivetBackendForm
from django.conf import settings
from django.db import models

MESSAGE_TYPE_SMS = "sms"


class SQLTelerivetBackend(SQLSMSBackend):
    class Meta:
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

    def send(self, msg, *args, **kwargs):
        text = msg.text.encode('utf-8')
        config = self.config
        params = {
            'phone_id': str(config.phone_id),
            'to_number': clean_phone_number(msg.phone_number),
            'content': text,
            'message_type': MESSAGE_TYPE_SMS,
        }
        url = 'https://api.telerivet.com/v1/projects/%s/messages/outgoing' % str(config.project_id)

        result = requests.post(
            url,
            auth=(str(config.api_key), ''),
            data=params,
            verify=True,
            timeout=settings.SMS_GATEWAY_TIMEOUT,
        )

        result = result.json()

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
