"""
DomainES
--------
"""
from .es_query import HQESQuery
from . import filters


class DomainES(HQESQuery):
    index = 'domains'

    @property
    def builtin_filters(self):
        return [
            non_test_domains,
            incomplete_domains,
            real_domains,
            commcare_domains,
            commconnect_domains,
            commtrack_domains,
            created,
            in_domains,
            is_active,
            is_snapshot,
        ] + super(DomainES, self).builtin_filters


def non_test_domains():
    return filters.term("is_test", [False, "none"])


def incomplete_domains():
    return filters.OR(filters.missing("countries"),
                      filters.missing("internal.area"),
                      filters.missing("internal.notes"),
                      filters.missing("internal.organization_name"),
                      filters.missing("internal.sub_area"),
                      )


def real_domains():
    return filters.term("is_test", False)


def commcare_domains():
    return filters.AND(filters.term("commconnect_enabled", False),
                       filters.term("commtrack_enabled", False))


def commconnect_domains():
    return filters.term("commconnect_enabled", True)


def commtrack_domains():
    return filters.term("commtrack_enabled", True)


def created(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('date_created', gt, gte, lt, lte)


def in_domains(domains):
    return filters.term('name', list(domains))


def is_active(is_active=True):
    return filters.term('is_active', is_active)


def is_snapshot(is_snapshot=True):
    return filters.term('is_snapshot', is_snapshot)
