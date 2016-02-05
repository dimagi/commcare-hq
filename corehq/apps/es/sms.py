"""
SMSES
--------
"""
from .es_query import HQESQuery
from . import filters


class SMSES(HQESQuery):
    index = 'sms'

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
        ] + super(SMSES, self).builtin_filters

    def user_aggregation(self):
        return self.terms_aggregation('couch_recipient', 'user')


def incoming_messages():
    return direction("i")


def outgoing_messages():
    return direction("o")


def direction(direction_):
    return filters.term("direction", direction_)


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
