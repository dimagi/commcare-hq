"""
DomainES
--------

Here's an example generating a histogram of domain creations (that's a type of
faceted query), filtered by a provided list of domains and a report date range.

.. code-block:: python

    from corehq.apps.es import DomainES

    domains_after_date = (DomainES()
                          .in_domains(domains)
                          .created(gte=datespan.startdate, lte=datespan.enddate)
                          .date_histogram('date', 'date_created', interval)
                          .size(0))
    histo_data = domains_after_date.run().aggregations.date.buckets_list
"""
from .es_query import HQESQuery
from . import filters


class DomainES(HQESQuery):
    index = 'domains'
    default_filters = {
        'not_snapshot': filters.NOT(filters.term('is_snapshot', True)),
    }

    def only_snapshots(self):
        """Normally snapshots are excluded, instead, return only snapshots"""
        return (self.remove_default_filter('not_snapshot')
                .filter(filters.term('is_snapshot', True)))

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
            last_modified,
            in_domains,
            is_active,
            is_active_project,
            created_by_user,
            self_started,
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


def last_modified(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('last_modified', gt, gte, lt, lte)


def in_domains(domains):
    return filters.term('name', domains)


def is_active(is_active=True):
    return filters.term('is_active', is_active)


def is_active_project(is_active=True):
    # Project is active - has submitted a form in the last 30 days
    return filters.term('cp_is_active', is_active)


def created_by_user(creating_user):
    return filters.term('creating_user', creating_user)


def self_started():
    return filters.term("internal.self_started", "true")
