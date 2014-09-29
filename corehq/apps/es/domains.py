from .es_query import HQESQuery
from . import filters


class DomainES(HQESQuery):
    index = 'domains'

    @property
    def builtin_filters(self):
        return [
            non_test_domains,
            incomplete_domains,
        ] + super(DomainES, self).builtin_filters


def non_test_domains():
    return filters.term("is_test", [False, "none"])


def incomplete_domains():
    return filters.OR(filters.missing("country"),
                      filters.missing("internal.area"),
                      filters.missing("internal.initiative"),
                      filters.missing("internal.notes"),
                      filters.missing("internal.organization_name"),
                      filters.missing("internal.platform"),
                      filters.missing("internal.phone_model"),
                      filters.missing("internal.project_manager"),
                      filters.missing("internal.project_state"),
                      filters.missing("internal.sub_area"),
                      )
