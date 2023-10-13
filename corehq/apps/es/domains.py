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

from django_countries import countries

from . import filters
from .client import ElasticDocumentAdapter, create_document_adapter
from .const import (
    HQ_DOMAINS_INDEX_CANONICAL_NAME,
    HQ_DOMAINS_INDEX_NAME,
    HQ_DOMAINS_SECONDARY_INDEX_NAME,
)
from .es_query import HQESQuery
from .index.analysis import COMMA_ANALYSIS
from .index.settings import IndexSettingsKey


class DomainES(HQESQuery):
    index = HQ_DOMAINS_INDEX_CANONICAL_NAME
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
    canonical_name = HQ_DOMAINS_INDEX_CANONICAL_NAME

    @property
    def mapping(self):
        from .mappings.domain_mapping import DOMAIN_MAPPING
        return DOMAIN_MAPPING

    @property
    def model_cls(self):
        from corehq.apps.domain.models import Domain
        return Domain

    def _from_dict(self, domain_dict):
        """
        Takes a domain dict and applies required transformation to make it suitable for ES.
        :param domain: an instance of ``dict`` which is result of ``Domain.to_json()``
        """
        from corehq.apps.accounting.models import Subscription

        sub = Subscription.visible_objects.filter(subscriber__domain=domain_dict['name'], is_active=True)
        domain_dict['deployment'] = domain_dict.get('deployment') or {}
        domain_countries = domain_dict['deployment'].get('countries', [])
        domain_dict['deployment']['countries'] = []
        if sub:
            domain_dict['subscription'] = sub[0].plan_version.plan.edition
        countries_map = dict(countries)
        for country in domain_countries:
            domain_dict['deployment']['countries'].append(countries_map[country].upper())
        return super()._from_dict(domain_dict)


domain_adapter = create_document_adapter(
    ElasticDomain,
    HQ_DOMAINS_INDEX_NAME,
    "hqdomain",
    secondary=HQ_DOMAINS_SECONDARY_INDEX_NAME,
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
