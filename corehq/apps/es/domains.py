from .es_query import HQESQuery
from . import filters


class DomainES(HQESQuery):
    index = 'domains'

    @property
    def builtin_filters(self):
        return [
            real_domains,
            commconnect_domains,
        ] + super(DomainES, self).builtin_filters


def real_domains():
    return filters.term("is_test", False)


def commconnect_domains():
    return filters.term("commconnect_enabled", True)
