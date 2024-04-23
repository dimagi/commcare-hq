import re

import attr
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.forms import model_to_dict
from django.utils.translation import gettext as _

from corehq.apps.case_search.exceptions import CaseSearchUserError
from corehq.apps.case_search.filter_dsl import CaseFilterError
from corehq.util.metrics.const import MODULE_NAME_TAG
from corehq.util.quickcache import quickcache

CLAIM_CASE_TYPE = 'commcare-case-claim'
FUZZY_PROPERTIES = "fuzzy_properties"
CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY = 'commcare_blacklisted_owner_ids'
CASE_SEARCH_XPATH_QUERY_KEY = '_xpath_query'
CASE_SEARCH_CASE_TYPE_KEY = "case_type"
CASE_SEARCH_INDEX_KEY_PREFIX = "indices."
CASE_SEARCH_SORT_KEY = "commcare_sort"

# These use the `x_commcare_` prefix to distinguish them from 'filter' keys
# This is a purely aesthetic distinction and not functional
CASE_SEARCH_REGISTRY_ID_KEY = 'x_commcare_data_registry'
CASE_SEARCH_CUSTOM_RELATED_CASE_PROPERTY_KEY = 'x_commcare_custom_related_case_property'
CASE_SEARCH_INCLUDE_ALL_RELATED_CASES_KEY = 'x_commcare_include_all_related_cases'
CASE_SEARCH_MODULE_NAME_TAG_KEY = "x_commcare_tag_module_name"

CONFIG_KEYS_MAPPING = {
    CASE_SEARCH_CASE_TYPE_KEY: "case_types",
    CASE_SEARCH_REGISTRY_ID_KEY: "data_registry",
    CASE_SEARCH_CUSTOM_RELATED_CASE_PROPERTY_KEY: "custom_related_case_property",
    CASE_SEARCH_INCLUDE_ALL_RELATED_CASES_KEY: "include_all_related_cases",
    CASE_SEARCH_SORT_KEY: "commcare_sort",
}

CASE_SEARCH_TAGS_MAPPING = {
    CASE_SEARCH_MODULE_NAME_TAG_KEY: MODULE_NAME_TAG,
}

UNSEARCHABLE_KEYS = (
    CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY,
    'owner_id',
    'include_closed',   # backwards compatibility for deprecated functionality to include closed cases
) + tuple(CONFIG_KEYS_MAPPING.values())


def _flatten_singleton_list(value):
    return value[0] if value and isinstance(value, list) and len(value) == 1 else value


@attr.s(frozen=True)
class SearchCriteria:
    key = attr.ib()
    value = attr.ib(converter=_flatten_singleton_list)

    @property
    def is_empty(self):
        return not bool(self.value)

    @property
    def has_missing_filter(self):
        if self.has_multiple_terms:
            return bool([v for v in self.value if v == ''])
        return self.value == ''

    @property
    def value_as_list(self):
        assert not self.has_multiple_terms
        return self.value.split(' ')

    @property
    def has_multiple_terms(self):
        return isinstance(self.value, list)

    @property
    def is_daterange(self):
        if self.has_multiple_terms:
            return any([v.startswith('__range__') for v in self.value])
        return self.value.startswith('__range__')

    @property
    def is_ancestor_query(self):
        return '/' in self.key

    @property
    def is_index_query(self):
        return self.key.startswith(CASE_SEARCH_INDEX_KEY_PREFIX)

    @property
    def index_query_identifier(self):
        return self.key.removeprefix(CASE_SEARCH_INDEX_KEY_PREFIX)

    def get_date_range(self):
        """The format is __range__YYYY-MM-DD__YYYY-MM-DD"""
        start, end = self.value.split('__')[2:]
        return start, end

    def clone_without_blanks(self):
        return SearchCriteria(self.key, self._value_without_empty())

    def _value_without_empty(self):
        return _flatten_singleton_list([v for v in self.value if v != ''])

    def validate(self):
        self._validate_multiple_terms()
        self._validate_daterange()

    def _validate_multiple_terms(self):
        if not self.has_multiple_terms:
            return

        disallowed_parameters = [
            CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY,
            'owner_id',
        ]

        if self.is_daterange and len(self.value) > 2:
            raise CaseFilterError(
                _("Only one blank value plus one date range value are supprted"),
                self.key
            )

        if self.key in disallowed_parameters:
            raise CaseFilterError(
                _("Multiple values are only supported for simple text and range searches"),
                self.key
            )

    def _validate_daterange(self):
        if not self.is_daterange:
            return
        pattern = re.compile(r'__range__\d{4}-\d{2}-\d{2}__\d{4}-\d{2}-\d{2}')
        if self.has_multiple_terms:
            # don't validate empty values
            values = [val for val in self.value if val != '']
        else:
            values = [self.value]
        for v in values:
            match = pattern.match(v)
            if not match:
                raise CaseFilterError(_('Invalid date range format, {}').format(v), self.key)


def criteria_dict_to_criteria_list(criteria_dict):
    criteria = [SearchCriteria(k, v) for k, v in criteria_dict.items()]
    for search_criteria in criteria:
        search_criteria.validate()
    return criteria


@attr.dataclass
class CommcareSortProperty:
    property_name: str = ''
    sort_type: str = ''
    is_descending: bool = False


def _parse_commcare_sort_properties(values):
    if values is None:
        return

    parsed_sort_properties = []
    flattened_values = [sort_property for value in values for sort_property in value.split(',')]
    for sort_property in flattened_values:
        parts = sort_property.lstrip('+-').split(':')
        parsed_sort_properties.append(
            CommcareSortProperty(
                property_name=parts[0],
                sort_type=parts[1] if len(parts) > 1 else 'exact',
                is_descending=sort_property.startswith('-')
            ))
    return parsed_sort_properties


@attr.s(frozen=True)
class CaseSearchRequestConfig:
    criteria = attr.ib(kw_only=True)
    case_types = attr.ib(kw_only=True, default=None)
    data_registry = attr.ib(kw_only=True, default=None, converter=_flatten_singleton_list)
    custom_related_case_property = attr.ib(kw_only=True, default=None, converter=_flatten_singleton_list)
    include_all_related_cases = attr.ib(kw_only=True, default=None, converter=_flatten_singleton_list)
    commcare_sort = attr.ib(kw_only=True, default=None, converter=_parse_commcare_sort_properties)

    @case_types.validator
    def _require_case_type(self, attribute, value):
        # custom validator to allow custom exception and message
        if not value:
            raise CaseSearchUserError(_('Search request must specify {param}').format(param=attribute.name))

    @data_registry.validator
    @custom_related_case_property.validator
    def _is_string(self, attribute, value):
        if value and not isinstance(value, str):
            raise CaseSearchUserError(_("{param} must be a string").format(param=attribute.name))


def extract_search_request_config(request_dict):
    params = request_dict.copy()
    for param_name in CASE_SEARCH_TAGS_MAPPING:
        params.pop(param_name, None)
    kwargs_from_params = {
        config_name: params.pop(param_name, None)
        for param_name, config_name in CONFIG_KEYS_MAPPING.items()
    }
    criteria = criteria_dict_to_criteria_list(params)
    return CaseSearchRequestConfig(criteria=criteria, **kwargs_from_params)


class GetOrNoneManager(models.Manager):
    """
    Adds get_or_none method to objects
    """

    def get_or_none(self, **kwargs):
        try:
            return self.get(**kwargs)
        except self.model.DoesNotExist:
            return None


class FuzzyProperties(models.Model):
    domain = models.CharField(
        max_length=256,
        null=False,
        blank=False,
        db_index=True,
    )
    case_type = models.CharField(
        max_length=256,
        null=False,
        blank=False,
        db_index=True,
    )
    properties = ArrayField(
        models.TextField(null=True, blank=True),
        null=True,
    )

    class Meta(object):
        unique_together = ('domain', 'case_type')


class IgnorePatterns(models.Model):
    domain = models.CharField(
        max_length=256,
        null=False,
        blank=False,
        db_index=True,
    )
    case_type = models.CharField(
        max_length=256,
        null=False,
        blank=False,
        db_index=True,
    )
    case_property = models.CharField(
        max_length=256,
        null=False,
        blank=False,
        db_index=True,
    )
    regex = models.CharField(
        max_length=256,
        null=False,
        blank=False,
        db_index=False,
    )


class CaseSearchConfig(models.Model):
    """
    Contains config for case search
    """
    class Meta(object):
        app_label = 'case_search'

    domain = models.CharField(
        max_length=256,
        null=False,
        blank=False,
        db_index=True,
        primary_key=True
    )
    enabled = models.BooleanField(blank=False, null=False, default=False)
    synchronous_web_apps = models.BooleanField(blank=False, null=False, default=False)
    sync_cases_on_form_entry = models.BooleanField(blank=False, null=False, default=False)
    fuzzy_properties = models.ManyToManyField(FuzzyProperties)
    ignore_patterns = models.ManyToManyField(IgnorePatterns)

    objects = GetOrNoneManager()

    @classmethod
    def enabled_domains(cls):
        return cls.objects.filter(enabled=True).values_list('domain', flat=True)

    def to_json(self):
        config = model_to_dict(self)
        config['fuzzy_properties'] = [
            model_to_dict(fuzzy_property, exclude=['id']) for fuzzy_property in config['fuzzy_properties']
        ]
        config['ignore_patterns'] = [
            model_to_dict(ignore_pattern, exclude=['id']) for ignore_pattern in config['ignore_patterns']
        ]
        return config

    @classmethod
    def create_model_and_index_from_json(cls, domain, json_def):
        if json_def['enabled']:
            config = enable_case_search(domain)
        else:
            config = disable_case_search(domain)

        if not config:
            return None

        config.synchronous_web_apps = json_def['synchronous_web_apps']
        config.sync_cases_on_form_entry = json_def['sync_cases_on_form_entry']
        config.ignore_patterns.all().delete()
        config.fuzzy_properties.all().delete()
        config.save()

        ignore_patterns = []
        for ignore_pattern in json_def['ignore_patterns']:
            ip = IgnorePatterns(**ignore_pattern)
            ip.domain = domain
            ip.save()
            ignore_patterns.append(ip)
        config.ignore_patterns.set(ignore_patterns)

        fuzzy_properties = []
        for fuzzy_property in json_def['fuzzy_properties']:
            fp = FuzzyProperties(**fuzzy_property)
            fp.domain = domain
            fp.save()
            fuzzy_properties.append(fp)
        config.fuzzy_properties.set(fuzzy_properties)

        return config


@quickcache(['domain'], timeout=24 * 60 * 60, memoize_timeout=60)
def case_search_enabled_for_domain(domain):
    try:
        CaseSearchConfig.objects.get(pk=domain, enabled=True)
    except CaseSearchConfig.DoesNotExist:
        return False
    else:
        return True


@quickcache(['domain'], timeout=24 * 60 * 60, memoize_timeout=60)
def case_search_synchronous_web_apps_for_domain(domain):
    if not case_search_enabled_for_domain(domain):
        return False

    config = CaseSearchConfig.objects.get_or_none(pk=domain)
    if config:
        return config.synchronous_web_apps
    return False


@quickcache(['domain'], timeout=24 * 60 * 60, memoize_timeout=60)
def case_search_sync_cases_on_form_entry_enabled_for_domain(domain):
    if settings.UNIT_TESTING:
        return False  # override with .tests.util.commtrack_enabled
    config = CaseSearchConfig.objects.get_or_none(pk=domain, enabled=True)
    return config.sync_cases_on_form_entry if config else False


def enable_case_search(domain):
    from corehq.apps.case_search.tasks import reindex_case_search_for_domain

    config, created = CaseSearchConfig.objects.get_or_create(pk=domain)
    if not config.enabled:
        config.enabled = True
        config.save()
        case_search_enabled_for_domain.clear(domain)
        reindex_case_search_for_domain.delay(domain)
        case_search_sync_cases_on_form_entry_enabled_for_domain.clear(domain)
    return config


def disable_case_search(domain):
    from corehq.apps.case_search.tasks import (
        delete_case_search_cases_for_domain,
    )

    try:
        config = CaseSearchConfig.objects.get(pk=domain)
    except CaseSearchConfig.DoesNotExist:
        # CaseSearch was never enabled
        return None
    if config.enabled:
        config.enabled = False
        config.save()
        case_search_enabled_for_domain.clear(domain)
        delete_case_search_cases_for_domain.delay(domain)
        case_search_sync_cases_on_form_entry_enabled_for_domain.clear(domain)
    return config


def case_search_enabled_domains():
    """Returns a list of all domains that have case search enabled
    """
    return CaseSearchConfig.objects.filter(enabled=True).values_list('domain', flat=True)


class DomainsNotInCaseSearchIndex(models.Model):
    """
    NOTE: This is a temporary "migration" model.
    This model is to be confused with the Case Search feature itself.
    This is a temporary object used to track domains that have not yet
    had their case data moved over to the Case Search Elasticsearch Index.

    Moving forward, the case data from all domains will be indexed by the
    CaseSearchIndex as well as the CaseIndex in elasticsearch.
    This is due to the efforts from SaaS to GA the Case List Explorer.
    This model exists to ensure that data from older domains is migrated in
    small controllable chunks so as not to overload pillows.
    Eventually, this model will be removed once the indexing of older
    data is complete.
    """
    domain = models.CharField(
        max_length=256,
        null=False,
        blank=False,
        db_index=True,
    )
    estimated_size = models.IntegerField()
