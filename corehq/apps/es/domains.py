"""
DomainES
--------

.. code-block:: python

    from corehq.apps.es import DomainES

    query = (DomainES()
             .in_domains(domains)
             .created(gte=datespan.startdate, lte=datespan.enddate)
             .size(0))
"""
from . import filters
from .client import ElasticDocumentAdapter, create_document_adapter
from .es_query import HQESQuery
from .transient_util import get_adapter_mapping, from_dict_with_possible_id


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
            created,
            last_modified,
            in_domains,
            is_active,
            is_active_project,
            created_by_user,
            self_started,
        ] + super(DomainES, self).builtin_filters


class ElasticDomain(ElasticDocumentAdapter):

    _index_name = "hqdomains_2021-03-08"
    type = "hqdomain"

    @property
    def mapping(self):
        return get_adapter_mapping(self)

    @classmethod
    def from_python(cls, doc):
        return from_dict_with_possible_id(doc)


domain_adapter = create_document_adapter(ElasticDomain)


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
