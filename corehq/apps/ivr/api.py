from datetime import datetime
from corehq.apps.sms.models import CallLog, INCOMING
from corehq.apps.sms.mixin import VerifiedNumber

def incoming(phone_number, backend_api):
    cleaned_number = phone_number
    if len(cleaned_number) > 0 and cleaned_number[0] == "+":
        cleaned_number = cleaned_number[1:]
    
    # Try to look up the verified number entry
    v = VerifiedNumber.view("sms/verified_number_by_number",
        key=cleaned_number,
        include_docs=True
    ).one()
    
    # If none was found, try to match only the last digits of numbers in the database
    if v is None:
        v = VerifiedNumber.view("sms/verified_number_by_suffix",
            key=cleaned_number,
            include_docs=True
        ).one()
    
    # Save the call entry
    msg = CallLog(
        phone_number    = cleaned_number,
        direction       = INCOMING,
        date            = datetime.utcnow(),
        backend_api     = backend_api
    )
    if v is not None:
        msg.domain = v.domain
        msg.couch_recipient_doc_type = v.owner_doc_type
        msg.couch_recipient = v.owner_id
    msg.save()


