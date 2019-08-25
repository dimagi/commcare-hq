from corehq.apps.ivr.models import Call
from corehq.apps.sms.util import strip_plus
from corehq.apps.sms.models import INCOMING, PhoneNumber
from datetime import datetime


def log_call(phone_number, gateway_session_id, backend=None):
    cleaned_number = strip_plus(phone_number)
    v = PhoneNumber.by_extensive_search(cleaned_number)

    call = Call(
        phone_number=cleaned_number,
        direction=INCOMING,
        date=datetime.utcnow(),
        backend_api=backend.get_api_id() if backend else None,
        backend_id=backend.couch_id if backend else None,
        gateway_session_id=gateway_session_id,
    )
    if v:
        call.domain = v.domain
        call.couch_recipient_doc_type = v.owner_doc_type
        call.couch_recipient = v.owner_id
    call.save()
