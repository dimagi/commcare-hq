"""
SMSES
--------
"""
from . import filters
from .client import ElasticDocumentAdapter, create_document_adapter
from .const import (
    HQ_SMS_INDEX_CANONICAL_NAME,
    HQ_SMS_INDEX_NAME,
    HQ_SMS_SECONDARY_INDEX_NAME,
)
from .es_query import HQESQuery
from .index.settings import IndexSettingsKey


class SMSES(HQESQuery):
    index = HQ_SMS_INDEX_CANONICAL_NAME

    @property
    def builtin_filters(self):
        return [
            incoming_messages,
            outgoing_messages,
            to_commcare_user,
            to_commcare_case,
            to_web_user,
            to_couch_user,
            to_commcare_user_or_case,
            received,
            direction,
            processed,
            processed_or_incoming_messages,
        ] + super(SMSES, self).builtin_filters

    def user_aggregation(self):
        return self.terms_aggregation('couch_recipient', 'user')


class ElasticSMS(ElasticDocumentAdapter):

    settings_key = IndexSettingsKey.SMS
    canonical_name = HQ_SMS_INDEX_CANONICAL_NAME

    @property
    def mapping(self):
        from .mappings.sms_mapping import SMS_MAPPING
        return SMS_MAPPING

    @property
    def model_cls(self):
        from corehq.apps.sms.models import SMS
        return SMS


sms_adapter = create_document_adapter(
    ElasticSMS,
    HQ_SMS_INDEX_NAME,
    "sms",
    secondary=HQ_SMS_SECONDARY_INDEX_NAME,
)


def incoming_messages():
    return direction("i")


def outgoing_messages():
    return direction("o")


def direction(direction_):
    return filters.term("direction", direction_)


def processed_or_incoming_messages():
    return filters.NOT(filters.AND(outgoing_messages(), processed(False)))


def processed(processed=True):
    return filters.term('processed', processed)


def to_commcare_user():
    return filters.term("couch_recipient_doc_type", "commcareuser")


def to_commcare_case():
    return filters.term("couch_recipient_doc_type", "commcarecase")


def to_web_user():
    return filters.term("couch_recipient_doc_type", "webuser")


def to_couch_user():
    return filters.term("couch_recipient_doc_type", "couchuser")


def to_commcare_user_or_case():
    return filters.OR(to_commcare_user(), to_commcare_case())


def received(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('date', gt, gte, lt, lte)
