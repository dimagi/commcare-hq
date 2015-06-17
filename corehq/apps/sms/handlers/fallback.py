from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import (
    send_sms_to_verified_number,
    MessageMetadata,
    add_msg_tags,
)
from corehq.apps.sms.models import WORKFLOW_DEFAULT, MessagingEvent


def fallback_handler(v, text, msg):
    domain_obj = Domain.get_by_name(v.domain, strict=True)

    logged_event = MessagingEvent.create_event_for_adhoc_sms(
        v.domain, recipient=v.owner, content_type=MessagingEvent.CONTENT_SMS,
        source=MessagingEvent.SOURCE_UNRECOGNIZED)

    inbound_subevent = logged_event.create_subevent_for_single_sms(
        v.owner_doc_type, v.owner_id)
    inbound_meta = MessageMetadata(workflow=WORKFLOW_DEFAULT,
        messaging_subevent_id=inbound_subevent.pk)
    add_msg_tags(msg, inbound_meta)

    if domain_obj.use_default_sms_response and domain_obj.default_sms_response:
        outbound_subevent = logged_event.create_subevent_for_single_sms(
            v.owner_doc_type, v.owner_id)
        outbound_meta = MessageMetadata(workflow=WORKFLOW_DEFAULT,
            location_id=msg.location_id,
            messaging_subevent_id=outbound_subevent.pk)
        send_sms_to_verified_number(v, domain_obj.default_sms_response,
            metadata=outbound_meta)
        outbound_subevent.completed()

    inbound_subevent.completed()
    logged_event.completed()
    return True
