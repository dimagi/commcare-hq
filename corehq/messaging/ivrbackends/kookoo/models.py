from corehq.apps.ivr.api import log_error, GatewayConnectionError
from corehq.apps.ivr.models import IVRBackend, SQLIVRBackend
from corehq.apps.sms.models import MessagingEvent
from corehq.apps.sms.util import strip_plus
from dimagi.ext.couchdbkit import StringProperty
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import get_url_base
from django.conf import settings
from django.core.urlresolvers import reverse
from urllib import urlencode
from urllib2 import urlopen
from xml.etree.ElementTree import XML
from xml.sax.saxutils import escape


class KooKooBackend(IVRBackend):
    api_key = StringProperty()

    @classmethod
    def get_api_id(cls):
        return 'KOOKOO'

    @classmethod
    def get_generic_name(cls):
        return "KooKoo"

    def cache_first_ivr_response(self):
        return True

    def initiate_outbound_call(self, call, logged_subevent, ivr_data=None):
        """
        Same expected return value as corehq.apps.ivr.api.initiate_outbound_call
        """
        phone_number = strip_plus(call.phone_number)

        if phone_number.startswith('91'):
            phone_number = '0%s' % phone_number[2:]
        else:
            log_error(MessagingEvent.ERROR_UNSUPPORTED_COUNTRY,
                call, logged_subevent)
            return True

        response = self.invoke_kookoo_outbound_api(phone_number)
        status, message = self.get_status_and_message(response)

        do_not_retry = False
        if status == 'queued':
            call.error = False
            call.gateway_session_id = 'KOOKOO-%s' % message
        elif status == 'error':
            call.error = True
            call.error_message = message
            if (message.strip().upper() in [
                'CALLS WILL NOT BE MADE BETWEEN 9PM TO 9AM.',
                'PHONE NUMBER IN DND LIST',
            ]):
                # These are error messages that come from KooKoo and
                # are indicative of non-recoverable errors, so we
                # wouldn't benefit from retrying the call.
                do_not_retry = True
            logged_subevent.error(MessagingEvent.ERROR_GATEWAY_ERROR)
        else:
            log_error(MessagingEvent.ERROR_GATEWAY_ERROR, call, logged_subevent)

        return not call.error or do_not_retry

    def get_response(self, gateway_session_id, ivr_responses, collect_input=False,
            hang_up=True, input_length=None):

        xml_string = ""
        for response in ivr_responses:
            text_to_say = response["text_to_say"]
            audio_file_url = response["audio_file_url"]

            if audio_file_url is not None:
                xml_string += "<playaudio>%s</playaudio>" % escape(audio_file_url)
            elif text_to_say is not None:
                xml_string += "<playtext>%s</playtext>" % escape(text_to_say)

        input_length_str = ""
        if input_length is not None:
            input_length_str = 'l="%s"' % input_length

        if input_length == 1:
            timeout = "3000"
        else:
            timeout = "5000"

        if collect_input:
            xml_string = '<collectdtmf %s o="%s">%s</collectdtmf>' % (input_length_str, timeout, xml_string)

        if hang_up:
            xml_string += "<hangup/>"

        return '<response sid="%s">%s</response>' % (gateway_session_id[7:], xml_string)

    def get_status_and_message(self, xml_response):
        """
        Gets the status and message from a KooKoo initiate
        outbound call XML response.
        """
        status = ''
        message = ''
        root = XML(xml_response)
        for child in root:
            if child.tag.endswith("status"):
                status = child.text
            elif child.tag.endswith("message"):
                message = child.text
        return (status, message)

    def invoke_kookoo_outbound_api(self, phone_number):
        url_base = get_url_base()
        params = urlencode({
            'phone_no': phone_number,
            'api_key': self.api_key,
            'outbound_version': '2',
            'url': url_base + reverse('corehq.messaging.ivrbackends.kookoo.views.ivr'),
            'callback_url': url_base + reverse('corehq.messaging.ivrbackends.kookoo.views.ivr_finished'),
        })
        url = 'http://www.kookoo.in/outbound/outbound.php?%s' % params

        try:
            return urlopen(url, timeout=settings.IVR_GATEWAY_TIMEOUT).read()
        except Exception:
            notify_exception(None, message='[IVR] Error connecting to KooKoo')
            raise GatewayConnectionError('Error connecting to KooKoo')

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQLKooKooBackend


class SQLKooKooBackend(SQLIVRBackend):
    class Meta:
        app_label = 'sms'
        proxy = True

    @classmethod
    def _migration_get_couch_model_class(cls):
        return KooKooBackend

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'api_key',
        ]

    @classmethod
    def get_api_id(cls):
        return 'KOOKOO'

    @classmethod
    def get_generic_name(cls):
        return "KooKoo"

    def cache_first_ivr_response(self):
        return True

    def initiate_outbound_call(self, call, logged_subevent, ivr_data=None):
        """
        Same expected return value as corehq.apps.ivr.api.initiate_outbound_call
        """
        phone_number = strip_plus(call.phone_number)

        if phone_number.startswith('91'):
            phone_number = '0%s' % phone_number[2:]
        else:
            log_error(MessagingEvent.ERROR_UNSUPPORTED_COUNTRY,
                call, logged_subevent)
            return True

        response = self.invoke_kookoo_outbound_api(phone_number)
        status, message = self.get_status_and_message(response)

        do_not_retry = False
        if status == 'queued':
            call.error = False
            call.gateway_session_id = 'KOOKOO-%s' % message
        elif status == 'error':
            call.error = True
            call.error_message = message
            if (message.strip().upper() in [
                'CALLS WILL NOT BE MADE BETWEEN 9PM TO 9AM.',
                'PHONE NUMBER IN DND LIST',
            ]):
                # These are error messages that come from KooKoo and
                # are indicative of non-recoverable errors, so we
                # wouldn't benefit from retrying the call.
                do_not_retry = True
            logged_subevent.error(MessagingEvent.ERROR_GATEWAY_ERROR)
        else:
            log_error(MessagingEvent.ERROR_GATEWAY_ERROR, call, logged_subevent)

        return not call.error or do_not_retry

    def get_response(self, gateway_session_id, ivr_responses, collect_input=False,
            hang_up=True, input_length=None):

        xml_string = ""
        for response in ivr_responses:
            text_to_say = response["text_to_say"]
            audio_file_url = response["audio_file_url"]

            if audio_file_url is not None:
                xml_string += "<playaudio>%s</playaudio>" % escape(audio_file_url)
            elif text_to_say is not None:
                xml_string += "<playtext>%s</playtext>" % escape(text_to_say)

        input_length_str = ""
        if input_length is not None:
            input_length_str = 'l="%s"' % input_length

        if input_length == 1:
            timeout = "3000"
        else:
            timeout = "5000"

        if collect_input:
            xml_string = '<collectdtmf %s o="%s">%s</collectdtmf>' % (input_length_str, timeout, xml_string)

        if hang_up:
            xml_string += "<hangup/>"

        return '<response sid="%s">%s</response>' % (gateway_session_id[7:], xml_string)

    def get_status_and_message(self, xml_response):
        """
        Gets the status and message from a KooKoo initiate
        outbound call XML response.
        """
        status = ''
        message = ''
        root = XML(xml_response)
        for child in root:
            if child.tag.endswith("status"):
                status = child.text
            elif child.tag.endswith("message"):
                message = child.text
        return (status, message)

    def invoke_kookoo_outbound_api(self, phone_number):
        url_base = get_url_base()
        params = urlencode({
            'phone_no': phone_number,
            'api_key': self.config.api_key,
            'outbound_version': '2',
            'url': url_base + reverse('corehq.messaging.ivrbackends.kookoo.views.ivr'),
            'callback_url': url_base + reverse('corehq.messaging.ivrbackends.kookoo.views.ivr_finished'),
        })
        url = 'http://www.kookoo.in/outbound/outbound.php?%s' % params

        try:
            return urlopen(url, timeout=settings.IVR_GATEWAY_TIMEOUT).read()
        except Exception:
            notify_exception(None, message='[IVR] Error connecting to KooKoo')
            raise GatewayConnectionError('Error connecting to KooKoo')
