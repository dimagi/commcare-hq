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

from copy import copy

from django_countries import Countries

from . import filters
from .client import ElasticDocumentAdapter, create_document_adapter
from .es_query import HQESQuery
from .index.analysis import COMMA_ANALYSIS
from .index.settings import IndexSettingsKey
from .transient_util import get_adapter_mapping


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

    analysis = COMMA_ANALYSIS
    settings_key = IndexSettingsKey.DOMAINS

    @property
    def mapping(self):
        return get_adapter_mapping(self)

    def from_python(self, domain):
        """
        :param user: an instance of ``CouchUser`` or a user dict
        :raises ``TypeError`` user is none of the above types
        """
        from corehq.apps.domain.models import Domain
        if isinstance(domain, Domain):
            domain_dict = domain.to_json()
        elif isinstance(domain, dict):
            domain_dict = domain
        else:
            raise TypeError(f"Unkown type {type(domain)}")
        return self.from_dict(domain_dict)

    def from_dict(self, domain):
        """
        Takes a domain dict and applies required transformation to make it suitable for ES.
        The function is replica of ``transform_domain_for_elasticsearch``.
        In future all references to  ``transform_domain_for_elasticsearch`` will be replaced by `from_python`
        :param domain: an instance of ``dict`` which is result of ``Domain.to_json()``
        """
        from corehq.apps.accounting.models import Subscription

        doc_ret = copy(domain)
        sub = Subscription.visible_objects.filter(subscriber__domain=doc_ret['name'], is_active=True)
        doc_ret['deployment'] = doc_ret.get('deployment') or {}
        countries = doc_ret['deployment'].get('countries', [])
        doc_ret['deployment']['countries'] = []
        if sub:
            doc_ret['subscription'] = sub[0].plan_version.plan.edition
        for country in countries:
            doc_ret['deployment']['countries'].append(Countries[country].upper())
        return doc_ret.pop('_id', None), doc_ret


domain_adapter = create_document_adapter(
    ElasticDomain,
    "hqdomains_2021-03-08",
    "hqdomain",
)


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
