from .es_query import HQESQuery
from . import filters


class DomainES(HQESQuery):
    index = 'domains'

    @property
    def builtin_filters(self):
        return [
            real_domains,
            commconnect_domains,
            created,
            in_domains,
        ] + super(DomainES, self).builtin_filters


def real_domains():
    return filters.term("is_test", False)


def commconnect_domains():
    return filters.term("commconnect_enabled", True)


def created(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('date_created', gt, gte, lt, lte)


def in_domains(domains):
    return filters.term('name', list(domains))
