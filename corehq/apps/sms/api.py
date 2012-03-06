import logging
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.sms.models import MessageLog, OUTGOING
from corehq.apps.sms.mixin import MobileBackend
from datetime import datetime
from corehq.apps.unicel import api as unicel_api
from corehq.apps.sms import mach_api

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
    logging.debug('Sending message: %s' % text)
    phone_number = clean_phone_number(phone_number)
    msg = MessageLog(domain=domain,
                     couch_recipient=id, 
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
        msg = MessageLog(
            phone_number = verified_number.phone_number,
            direction    = OUTGOING,
            date         = datetime.utcnow(),
            text         = text
        )
        module.send(msg, **kwargs)
        return True
    except Exception as e:
        logging.exception(e)
        return False


