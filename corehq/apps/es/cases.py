from .es_query import HQESQuery
from . import filters


class CaseES(HQESQuery):
    index = 'cases'

    @property
    def builtin_filters(self):
        return [
            opened_range,
            closed_range,
            is_closed,
            in_domains,
        ] + super(CaseES, self).builtin_filters


def opened_range(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('opened_on', gt, gte, lt, lte)


def closed_range(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('closed_on', gt, gte, lt, lte)


def is_closed(closed=True):
    return filters.term('closed', closed)


def in_domains(domains):
    return filters.term("domain", list(domains))
