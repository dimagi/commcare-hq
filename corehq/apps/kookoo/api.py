import hashlib
from datetime import datetime
from django.http import HttpResponse
from django.conf import settings
from urllib import urlencode
from urllib2 import urlopen
from xml.etree.ElementTree import XML
from dimagi.utils.web import get_url_base
from django.core.urlresolvers import reverse
from xml.sax.saxutils import escape
from corehq.apps.smsforms.app import start_session
from corehq.apps.smsforms.models import XFORMS_SESSION_IVR
from corehq.apps.smsforms.util import form_requires_input
from corehq.apps.ivr.api import format_ivr_response, get_input_length
from corehq.apps.app_manager.models import Form

class InvalidPhoneNumberException(Exception):
    pass

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

"""
Expected kwargs:
    api_key

Returns True if the call was queued successfully, or False if an error occurred.
"""
def initiate_outbound_call(call_log_entry, *args, **kwargs):
    phone_number = call_log_entry.phone_number
    if phone_number.startswith("+"):
        phone_number = phone_number[1:]

    if phone_number.startswith("91"):
        phone_number = "0" + phone_number[2:]
    else:
        call_log_entry.error = True
        call_log_entry.error_message = "Kookoo can only send to Indian phone numbers."
        call_log_entry.save()
        return False

    form = Form.get_form(call_log_entry.form_unique_id)
    app = form.get_app()
    module = form.get_module()

    # Only precache the first response if it's not an only-label form, otherwise we could end up
    # submitting the form regardless of whether the person actually answers the call.
    if form_requires_input(form):
        recipient = call_log_entry.recipient
        case_id = call_log_entry.case_id
        case_for_case_submission = call_log_entry.case_for_case_submission
        session, responses = start_session(recipient.domain, recipient, app,
            module, form, case_id, yield_responses=True,
            session_type=XFORMS_SESSION_IVR,
            case_for_case_submission=case_for_case_submission)

        ivr_responses = []
        if len(responses) == 0:
            call_log_entry.error = True
            call_log_entry.error_message = "No prompts seen in form. Please check that the form does not have errors."
            call_log_entry.save()
            return False

        for response in responses:
            ivr_responses.append(format_ivr_response(response.event.caption, app))

        input_length = get_input_length(responses[-1])

        call_log_entry.use_precached_first_response = True
        call_log_entry.xforms_session_id = session.session_id

    url_base = get_url_base()

    params = urlencode({
        "phone_no" : phone_number,
        "api_key" : kwargs["api_key"],
        "outbound_version" : "2",
        "url" : url_base + reverse("corehq.apps.kookoo.views.ivr"),
        "callback_url" : url_base + reverse("corehq.apps.kookoo.views.ivr_finished"),
    })
    url = "http://www.kookoo.in/outbound/outbound.php?%s" % params
    if kwargs.get("is_test", False):
        session_id = hashlib.sha224(datetime.utcnow().isoformat()).hexdigest()
        response = "<request><status>queued</status><message>%s</message></request>" % session_id
    else:
        response = urlopen(url, timeout=settings.IVR_GATEWAY_TIMEOUT).read()

    root = XML(response)
    for child in root:
        if child.tag.endswith("status"):
            status = child.text
        elif child.tag.endswith("message"):
            message = child.text

    do_not_retry = False
    if status == "queued":
        call_log_entry.error = False
        call_log_entry.gateway_session_id = "KOOKOO-" + message
    elif status == "error":
        call_log_entry.error = True
        call_log_entry.error_message = message
        if (message.strip().upper() in [
            'CALLS WILL NOT BE MADE BETWEEN 9PM TO 9AM',
            'PHONE NUMBER IN DND LIST',
        ]):
            do_not_retry = True
    else:
        call_log_entry.error = True
        call_log_entry.error_message = "Unknown status received from Kookoo."

    if call_log_entry.error:
        call_log_entry.use_precached_first_response = False

    if call_log_entry.use_precached_first_response:
        call_log_entry.first_response = get_http_response_string(call_log_entry.gateway_session_id, ivr_responses, collect_input=True, hang_up=False, input_length=input_length)

    call_log_entry.save()
    return not call_log_entry.error or do_not_retry

