from kafka.protocol.offset import OffsetResetStrategy
from kafka.structs import OffsetRequestPayload

from corehq.apps.change_feed.connection import get_kafka_client
from .document_types import CASE, FORM, DOMAIN, META, APP

# this is redundant but helps avoid import warnings until nothing references these
CASE = CASE
FORM = FORM
DOMAIN = DOMAIN
META = META
APP = APP

# new models
CASE_SQL = 'case-sql'
FORM_SQL = 'form-sql'
SMS = 'sms'
LEDGER = 'ledger'
COMMCARE_USER = 'commcare-user'
GROUP = 'group'
WEB_USER = 'web-user'


ALL = (
    CASE,
    CASE_SQL,
    COMMCARE_USER,
    DOMAIN,
    FORM,
    FORM_SQL,
    GROUP,
    LEDGER,
    META,
    SMS,
    WEB_USER,
    APP,
)


def get_topic(document_type_object):
    return document_type_object.primary_type


def get_topic_offset(topic):
    assert topic in ALL
    return get_all_offsets()[topic]


def get_multi_topic_offset(topics):
    offsets = get_all_offsets()
    return {topic: offsets[topic] for topic in topics}


def get_all_offsets():
    client = get_kafka_client()
    offset_requests = [OffsetRequestPayload(topic, 0, OffsetResetStrategy.LATEST, 1) for topic in ALL]
    responses = client.send_offset_request(offset_requests)
    return {
        r.topic: r.offsets[0] for r in responses
    }
