from datetime import datetime
from corehq.apps.sms.models import CallLog, INCOMING
from corehq.apps.sms.mixin import VerifiedNumber

def incoming(phone_number):
    cleaned_number = phone_number
    if len(cleaned_number) > 0 and cleaned_number[0] == "+":
        cleaned_number = cleaned_number[1:]
    v = VerifiedNumber.view("sms/verified_number_by_number",
        startkey=[cleaned_number],
        endkey=[cleaned_number],
        include_docs=True
    ).one()
    msg = CallLog(
        phone_number    = cleaned_number,
        direction       = INCOMING,
        date            = datetime.utcnow(),
    )
    if v is not None:
        msg.domain = v.domain
        msg.couch_recipient_doc_type = v.owner_doc_type
        msg.couch_recipient = v.owner_id
    msg.save()


