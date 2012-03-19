from datetime import datetime
from corehq.apps.sms.models import CallLog, INCOMING, INBOUND_CALL
from corehq.apps.sms.mixin import VerifiedNumber


def incoming(domain, phone_number):
    v = VerifiedNumber.view("sms/verified_number_by_number",
        startkey=[phone_number],
        endkey=[phone_number],
        include_docs=True
    ).one()
    msg = CallLog(
        domain          = domain,
        phone_number    = phone_number,
        direction       = INCOMING,
        date            = datetime.utcnow(),
        call_type       = INBOUND_CALL
    )
    if v is not None:
        msg.couch_recipient_doc_type = v.owner_doc_type
        msg.couch_recipient = v.owner_id
    msg.save()
    # Next: Dispatch to inbound handler


