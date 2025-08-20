from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import (
    MessageMetadata,
    add_msg_tags,
    send_message_to_verified_number,
)
from corehq.apps.sms.models import WORKFLOW_DEFAULT, ConnectMessagingNumber, MessagingEvent


def fallback_handler(verified_number, text, msg):
    domain_obj = Domain.get_by_name(verified_number.domain, strict=True)
    if isinstance(verified_number, ConnectMessagingNumber):
        content_type = MessagingEvent.CONTENT_CONNECT
    else:
        content_type = MessagingEvent.CONTENT_SMS

    logged_event = MessagingEvent.create_event_for_adhoc_sms(
        verified_number.domain, recipient=verified_number.owner, content_type=content_type,
        source=MessagingEvent.SOURCE_UNRECOGNIZED)

    inbound_subevent = logged_event.create_subevent_for_single_sms(
        verified_number.owner_doc_type, verified_number.owner_id)
    inbound_meta = MessageMetadata(workflow=WORKFLOW_DEFAULT,
        messaging_subevent_id=inbound_subevent.pk)
    add_msg_tags(msg, inbound_meta)

    if domain_obj.use_default_sms_response and domain_obj.default_sms_response:
        outbound_subevent = logged_event.create_subevent_for_single_sms(
            verified_number.owner_doc_type, verified_number.owner_id)
        outbound_meta = MessageMetadata(workflow=WORKFLOW_DEFAULT,
            location_id=msg.location_id,
            messaging_subevent_id=outbound_subevent.pk)
        send_message_to_verified_number(verified_number, domain_obj.default_sms_response,
                                    metadata=outbound_meta)
        outbound_subevent.completed()

    inbound_subevent.completed()
    logged_event.completed()
    return True
