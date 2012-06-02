import logging
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.sms.models import SMSLog, OUTGOING, INCOMING
from corehq.apps.sms.mixin import MobileBackend, VerifiedNumber
from datetime import datetime
from corehq.apps.unicel import api as unicel_api
from corehq.apps.sms import mach_api
from corehq.apps.sms.util import format_message_list
from corehq.apps.smsforms.models import XFormsSession
from corehq.apps.smsforms.app import get_responses

ALTERNATIVE_BACKENDS = [("+91", unicel_api)] # TODO: move to setting?
DEFAULT_BACKEND = mach_api

def get_backend_api(msg):
    """
    Given a message, find which version of the api to return.
    """
    # this is currently a very dumb method that checks for 
    # india and routes to unicel, otherwise returning mach
    
    # The caller assumes the returned module has a send() method 
    # that takes in a message object.
    phone = clean_phone_number(msg.phone_number)
    for code, be_module in ALTERNATIVE_BACKENDS:
        if phone.startswith(code):
            return be_module
    return DEFAULT_BACKEND

def send_sms(domain, id, phone_number, text):
    """
    Sends an outbound SMS. Returns false if it fails.
    """
    if phone_number is None:
        return False
    if isinstance(phone_number, int) or isinstance(phone_number, long):
        phone_number = str(phone_number)
    logging.debug('Sending message: %s' % text)
    phone_number = clean_phone_number(phone_number)
    msg = SMSLog(domain=domain,
                     couch_recipient=id, 
                     couch_recipient_doc_type="CouchUser",
                     phone_number=phone_number,
                     direction=OUTGOING,
                     date = datetime.utcnow(),
                     text = text)
    try:
        get_backend_api(msg).send(msg)
        msg.save()
        return True
    except Exception:
        logging.exception("Problem sending SMS to %s" % phone_number)
        return False

def send_sms_to_verified_number(verified_number, text):
    """
    Sends an sms using the given verified phone number entry.
    
    verified_number The VerifiedNumber entry to use when sending.
    text            The text of the message to send.
    
    return  True on success, False on failure
    """
    try:
        backend = verified_number.backend
        module = __import__(backend.outbound_module, fromlist=["send"])
        kwargs = backend.outbound_params
        msg = SMSLog(
            couch_recipient_doc_type    = verified_number.owner_doc_type,
            couch_recipient             = verified_number.owner_id,
            phone_number                = verified_number.phone_number,
            direction                   = OUTGOING,
            date                        = datetime.utcnow(),
            domain                      = verified_number.domain,
            text                        = text
        )
        module.send(msg, **kwargs)
        msg.save()
        return True
    except Exception as e:
        logging.exception("Exception while sending SMS to VerifiedNumber id " + verified_number._id)
        logging.exception(e)
        return False

def incoming(phone_number, text):
    v = VerifiedNumber.view("sms/verified_number_by_number",
        key=phone_number,
        include_docs=True
    ).one()
    
    # Log message in message log
    msg = SMSLog(
        phone_number    = phone_number,
        direction       = INCOMING,
        date            = datetime.utcnow(),
        text            = text
    )
    if v is not None:
        msg.couch_recipient_doc_type    = v.owner_doc_type
        msg.couch_recipient             = v.owner_id
        msg.domain                      = v.domain
    msg.save()
    
    # Pass message to the appropriate form
    if v is not None:
        session = XFormsSession.view("smsforms/open_sessions_by_connection",
                                     key=[v.domain, v.owner_id],
                                     include_docs=True).one()
        if session is not None:
            responses = get_responses(msg)
            if len(responses) > 0:
                response_text = format_message_list(responses)
                send_sms_to_verified_number(v, response_text)
        else:
            #TODO: Try to match the text against a keyword to start a survey
            pass
    else:
        #TODO: Registration via SMS
        pass



