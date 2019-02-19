from __future__ import absolute_import
from __future__ import unicode_literals
import codecs
import jsonfield
import re
import requests
from dimagi.utils.logging import notify_exception
from django.conf import settings
from django.db import models
from django.db import IntegrityError
from corehq.apps.sms.models import SQLSMSBackend
from corehq.messaging.smsbackends.start_enterprise.const import (
    SINGLE_SMS_URL,
    LONG_TEXT_MSG_TYPE,
    LONG_UNICODE_MSG_TYPE,
    SUCCESS_RESPONSE_REGEX,
    UNRETRYABLE_ERROR_MESSAGES,
)
from corehq.messaging.smsbackends.start_enterprise.exceptions import StartEnterpriseBackendException
from corehq.messaging.smsbackends.start_enterprise.forms import StartEnterpriseBackendForm
from corehq.apps.sms.models import SMS
from corehq.apps.sms.util import strip_plus


class StartEnterpriseDeliveryReceipt(models.Model):
    """
    Holds delivery receipt information pertaining to the Start Enterprise backend.
    """

    # Points to SMS.couch_id
    sms_id = models.CharField(max_length=126, db_index=True)

    # The message id received in the gateway response
    message_id = models.CharField(max_length=126, db_index=True, unique=True)

    # The timestamp that the delivery receipt was received by the gateway.
    # If None, then no delivery receipt has been received yet.
    received_on = models.DateTimeField(null=True, db_index=True)

    # The information sent by the gateway
    info = jsonfield.JSONField(null=True, default=dict)


class StartEnterpriseBackend(SQLSMSBackend):
    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_api_id(cls):
        return 'START_ENT'

    @classmethod
    def get_generic_name(cls):
        return "Start Enterprise"

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'username',
            'password',
            'sender_id',
        ]

    @classmethod
    def get_form_class(cls):
        return StartEnterpriseBackendForm

    def get_params(self, msg_obj):
        config = self.config
        try:
            message = msg_obj.text
            message.encode('ascii')
            message_type = LONG_TEXT_MSG_TYPE
        except UnicodeEncodeError:
            message = codecs.encode(codecs.encode(msg_obj.text, 'utf_16_be'), 'hex').decode('utf-8').upper()
            message_type = LONG_UNICODE_MSG_TYPE

        return {
            'usr': config.username,
            'pass': config.password,
            'msisdn': strip_plus(msg_obj.phone_number),
            'sid': config.sender_id,
            'mt': message_type,
            'msg': message,
        }

    @classmethod
    def phone_number_is_valid(cls, phone_number):
        phone_number = strip_plus(phone_number)
        # Phone number must be an Indian phone number
        # Also avoid processing numbers that are obviously too short
        return phone_number.startswith('91') and len(phone_number) > 3

    def send(self, msg_obj, *args, **kwargs):
        if not self.phone_number_is_valid(msg_obj.phone_number):
            msg_obj.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            return

        response = requests.get(
            SINGLE_SMS_URL,
            params=self.get_params(msg_obj),
            timeout=settings.SMS_GATEWAY_TIMEOUT,
        )
        self.handle_response(msg_obj, response.status_code, response.text)

    def record_message_ids(self, msg_obj, response_text):
        for message_id in response_text.split(','):
            try:
                StartEnterpriseDeliveryReceipt.objects.create(
                    sms_id=msg_obj.couch_id,
                    message_id=message_id
                )
            except IntegrityError:
                # The API is sometimes returning duplicate message IDs for different messages.
                # There's not much we can do when this happens, but we shouldn't fail hard.
                pass

    def handle_response(self, msg_obj, response_status_code, response_text):
        if response_status_code == 200 and re.match(SUCCESS_RESPONSE_REGEX, response_text):
            self.record_message_ids(msg_obj, response_text)
        else:
            self.handle_failure(msg_obj, response_status_code, response_text)

    def handle_failure(self, msg_obj, response_status_code, response_text):
        if response_status_code != 200:
            raise StartEnterpriseBackendException("Received unexpected status code: %s" % response_status_code)

        if response_text in UNRETRYABLE_ERROR_MESSAGES:
            msg_obj.set_system_error(SMS.ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS)
            notify_exception(None, "Error with the Start Enterprise Backend: %s" % response_text)
        else:
            raise StartEnterpriseBackendException(
                "Unrecognized response from Start Enterprise gateway: %s" % response_text
            )
