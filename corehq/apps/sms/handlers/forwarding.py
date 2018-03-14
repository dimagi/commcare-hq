from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.sms.dbaccessors import get_forwarding_rules_for_domain
from corehq.apps.sms.models import (
    FORWARD_ALL, FORWARD_BY_KEYWORD, MessagingEvent,
    WORKFLOW_FORWARD,
)
from corehq.apps.sms.api import (send_sms_with_backend, add_msg_tags,
    MessageMetadata)


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


def forwarding_handler(v, text, msg):
    rules = get_forwarding_rules_for_domain(v.domain)
    text_words = text.upper().split()
    keyword_to_match = text_words[0] if len(text_words) > 0 else ""
    for rule in rules:
        matches_rule = False
        if rule.forward_type == FORWARD_ALL:
            matches_rule = True
        elif rule.forward_type == FORWARD_BY_KEYWORD:
            matches_rule = (keyword_to_match == rule.keyword.upper())

        if matches_rule:
            forward_sms(msg, v.domain, v, text, rule.backend_id)
            return True
    return False
