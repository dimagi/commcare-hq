import hashlib
from datetime import datetime
from dimagi.utils.logging import notify_exception
from django.http import HttpResponse
from django.conf import settings
from urllib import urlencode
from urllib2 import urlopen
from xml.etree.ElementTree import XML
from dimagi.utils.web import get_url_base
from django.core.urlresolvers import reverse
from xml.sax.saxutils import escape
from corehq.apps.sms.models import MessagingEvent
from corehq.apps.sms.util import strip_plus
from corehq.apps.smsforms.app import start_session
from corehq.apps.smsforms.models import XFORMS_SESSION_IVR
from corehq.apps.smsforms.util import form_requires_input
from corehq.apps.ivr.api import (log_error, GatewayConnectionError,
    set_first_ivr_response)
from corehq.apps.app_manager.models import Form


API_ID = "KOOKOO"


def get_http_response_string(gateway_session_id, ivr_responses, collect_input=False, hang_up=True, input_length=None):
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


def get_status_and_message(xml_response):
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


def invoke_kookoo_outbound_api(phone_number, api_key, is_test=False):
    if is_test:
        session_id = hashlib.sha224(datetime.utcnow().isoformat()).hexdigest()
        return "<request><status>queued</status><message>%s</message></request>" % session_id

    url_base = get_url_base()
    params = urlencode({
        'phone_no': phone_number,
        'api_key': api_key,
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


def initiate_outbound_call(call_log_entry, logged_subevent, ivr_data=None, *args, **kwargs):
    """
    Expected kwargs:
        api_key

    Same expected return value as corehq.apps.ivr.api.initiate_outbound_call
    """
    phone_number = strip_plus(call_log_entry.phone_number)

    if phone_number.startswith('91'):
        phone_number = '0%s' % phone_number[2:]
    else:
        log_error(MessagingEvent.ERROR_UNSUPPORTED_COUNTRY,
            call_log_entry, logged_subevent)
        return True

    response = invoke_kookoo_outbound_api(phone_number, kwargs['api_key'], kwargs.get('is_test', False))
    status, message = get_status_and_message(response)

    do_not_retry = False
    if status == 'queued':
        call_log_entry.error = False
        call_log_entry.gateway_session_id = 'KOOKOO-%s' % message

        if ivr_data:
            set_first_ivr_response(call_log_entry, call_log_entry.gateway_session_id,
                ivr_data, get_http_response_string)
    elif status == 'error':
        call_log_entry.error = True
        call_log_entry.error_message = message
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
        log_error(MessagingEvent.ERROR_GATEWAY_ERROR,
            call_log_entry, logged_subevent)

    call_log_entry.save()
    return not call_log_entry.error or do_not_retry
