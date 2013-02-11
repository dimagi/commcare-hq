from django.http import HttpResponse
from django.conf import settings
from urllib import urlencode
from urllib2 import urlopen
from xml.etree.ElementTree import XML
from dimagi.utils.web import get_url_base
from django.core.urlresolvers import reverse
from xml.sax.saxutils import escape

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
    
    if collect_input:
        xml_string = '<collectdtmf %s o="5000">%s</collectdtmf>' % (input_length_str, xml_string)
    
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
        raise InvalidPhoneNumberException("Kookoo can only send to Indian phone numbers.")
    
    url_base = get_url_base()
    
    params = urlencode({
        "phone_no" : phone_number,
        "api_key" : kwargs["api_key"],
        "outbound_version" : "2",
        "url" : url_base + reverse("corehq.apps.kookoo.views.ivr"),
        "callback_url" : url_base + reverse("corehq.apps.kookoo.views.ivr_finished"),
    })
    url = "http://www.kookoo.in/outbound/outbound.php?%s" % params
    response = urlopen(url).read()
    
    root = XML(response)
    for child in root:
        if child.tag.endswith("status"):
            status = child.text
        elif child.tag.endswith("message"):
            message = child.text
    
    if status == "queued":
        call_log_entry.error = False
        call_log_entry.gateway_session_id = "KOOKOO-" + message
    elif status == "error":
        call_log_entry.error = True
        call_log_entry.error_message = message
    else:
        call_log_entry.error = True
        call_log_entry.error_message = "Unknown status received from Kookoo."
    
    call_log_entry.save()
    return not call_log_entry.error

