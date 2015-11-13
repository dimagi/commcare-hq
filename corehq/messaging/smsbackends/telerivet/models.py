import os
import requests
from dimagi.ext.couchdbkit import *
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.sms.mixin import SMSBackend
from corehq.apps.sms.models import SQLSMSBackend
from corehq.messaging.smsbackends.telerivet.forms import TelerivetBackendForm
from django.conf import settings
from django.db import models

MESSAGE_TYPE_SMS = "sms"


class TelerivetBackend(SMSBackend):
    # The api key of the account to send from.
    api_key = StringProperty()
    # The Telerivet project id.
    project_id = StringProperty()
    # The id of the phone to send from, as shown on Telerivet's API page.
    phone_id = StringProperty()
    # The Webhook Secret that gets posted to hq on every request
    webhook_secret = StringProperty()
    # If None, ignored. Otherwise, the country code to append to numbers
    # in inbound requests if not already there.
    country_code = StringProperty()

    class Meta:
        app_label = "telerivet"

    @classmethod
    def get_api_id(cls):
        return "TELERIVET"

    @classmethod
    def get_generic_name(cls):
        return "Telerivet (Android)"

    @classmethod
    def get_template(cls):
        return "telerivet/backend.html"

    @classmethod
    def get_form_class(cls):
        return TelerivetBackendForm

    def send(self, msg, *args, **kwargs):
        text = msg.text.encode("utf-8")
        params = {
            "phone_id": str(self.phone_id),
            "to_number": clean_phone_number(msg.phone_number),
            "content": text,
            "message_type": MESSAGE_TYPE_SMS,
        }
        url = "https://api.telerivet.com/v1/projects/%s/messages/outgoing" % str(self.project_id)

        result = requests.post(
            url,
            auth=(str(self.api_key), ''),
            data=params,
            verify=True,
            timeout=settings.SMS_GATEWAY_TIMEOUT,
        )

        result = result.json()

    @classmethod
    def by_webhook_secret(cls, webhook_secret):
        return cls.view("telerivet/backend_by_secret", key=[webhook_secret],
                        include_docs=True).one()

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQLTelerivetBackend


class SQLTelerivetBackend(SQLSMSBackend):
    class Meta:
        app_label = 'sms'
        proxy = True

    @classmethod
    def _migration_get_couch_model_class(cls):
        return TelerivetBackend

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
    secret = models.CharField(max_length=255, null=True)
