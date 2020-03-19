from corehq.apps.sms.api import (
    MessageMetadata,
    add_msg_tags,
    send_sms_with_backend,
)
from corehq.apps.sms.models import (
    WORKFLOW_FORWARD,
    MessagingEvent,
)


def forward_sms(msg, domain, verified_number, text, backend_id):
    logged_event = MessagingEvent.create_event_for_adhoc_sms(
        domain, recipient=verified_number.owner,
        content_type=MessagingEvent.CONTENT_SMS,
        source=MessagingEvent.SOURCE_FORWARDED)

    inbound_subevent = logged_event.create_subevent_for_single_sms(
        verified_number.owner_doc_type, verified_number.owner_id)
    inbound_meta = MessageMetadata(workflow=WORKFLOW_FORWARD,
        messaging_subevent_id=inbound_subevent.pk)
    add_msg_tags(msg, inbound_meta)

    outbound_subevent = logged_event.create_subevent_for_single_sms(
        verified_number.owner_doc_type, verified_number.owner_id)
    outbound_meta = MessageMetadata(workflow=WORKFLOW_FORWARD,
        messaging_subevent_id=outbound_subevent.pk)

    send_sms_with_backend(domain, verified_number.phone_number, text,
        backend_id, metadata=outbound_meta)

    outbound_subevent.completed()
    inbound_subevent.completed()
    logged_event.completed()
