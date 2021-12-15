import attr
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.forms import model_to_dict
from django.utils.translation import ugettext as _

from corehq.apps.case_search.exceptions import CaseSearchUserError
from corehq.util.quickcache import quickcache

CLAIM_CASE_TYPE = 'commcare-case-claim'
FUZZY_PROPERTIES = "fuzzy_properties"
CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY = 'commcare_blacklisted_owner_ids'
CASE_SEARCH_XPATH_QUERY_KEY = '_xpath_query'
CASE_SEARCH_CASE_TYPE_KEY = "case_type"

# These use the `x_commcare_` prefix to distinguish them from 'filter' keys
# This is a purely aesthetic distinction and not functional
CASE_SEARCH_REGISTRY_ID_KEY = 'x_commcare_data_registry'
CASE_SEARCH_EXPAND_ID_PROPERTY_KEY = 'x_commcare_expand_id_property'

CONFIG_KEYS_MAPPING = {
    CASE_SEARCH_CASE_TYPE_KEY: "case_types",
    CASE_SEARCH_REGISTRY_ID_KEY: "data_registry",
    CASE_SEARCH_EXPAND_ID_PROPERTY_KEY: "expand_id_property"
}
LEGACY_CONFIG_KEYS = {
    CASE_SEARCH_REGISTRY_ID_KEY: "commcare_registry"
}
UNSEARCHABLE_KEYS = (
    CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY,
    'owner_id',
    'include_closed',   # backwards compatibility for deprecated functionality to include closed cases
) + tuple(CONFIG_KEYS_MAPPING.values()) + tuple(LEGACY_CONFIG_KEYS.values())


def _flatten_singleton_list(value):
    return value[0] if value and len(value) == 1 else value


def _flatten_multi_value_dict_values(value):
    return {k: _flatten_singleton_list(v) for k, v in value.items()}


@attr.s(frozen=True)
class CaseSearchRequestConfig:
    criteria = attr.ib(kw_only=True, converter=_flatten_multi_value_dict_values)
    case_types = attr.ib(kw_only=True, default=None)
    data_registry = attr.ib(kw_only=True, default=None, converter=_flatten_singleton_list)
    expand_id_property = attr.ib(kw_only=True, default=None, converter=_flatten_singleton_list)

    @case_types.validator
    def _require_case_type(self, attribute, value):
        # custom validator to allow custom exception and message
        if not value:
            raise CaseSearchUserError(_('Search request must specify {param}').format(param=attribute.name))

    @data_registry.validator
    @expand_id_property.validator
    def _is_string(self, attribute, value):
        if value and not isinstance(value, str):
            raise CaseSearchUserError(_("{param} must be a string").format(param=attribute.name))


def extract_search_request_config(request_dict):
    params = dict(request_dict.lists())

    def _get_value(key):
        val = None
        try:
            val = params.pop(key)
        except KeyError:
            if key in LEGACY_CONFIG_KEYS:
                val = params.pop(LEGACY_CONFIG_KEYS[key], None)
        return val

    kwargs_from_params = {
        config_name: _get_value(param_name)
        for param_name, config_name in CONFIG_KEYS_MAPPING.items()
    }
    return CaseSearchRequestConfig(criteria=params, **kwargs_from_params)


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


def enable_case_search(domain):
    from corehq.apps.case_search.tasks import reindex_case_search_for_domain
    from corehq.pillows.case_search import domains_needing_search_index

    config, created = CaseSearchConfig.objects.get_or_create(pk=domain)
    if not config.enabled:
        config.enabled = True
        config.save()
        case_search_enabled_for_domain.clear(domain)
        domains_needing_search_index.clear()
        reindex_case_search_for_domain.delay(domain)
    return config


def disable_case_search(domain):
    from corehq.apps.case_search.tasks import (
        delete_case_search_cases_for_domain,
    )
    from corehq.pillows.case_search import domains_needing_search_index

    try:
        config = CaseSearchConfig.objects.get(pk=domain)
    except CaseSearchConfig.DoesNotExist:
        # CaseSearch was never enabled
        return None
    if config.enabled:
        config.enabled = False
        config.save()
        case_search_enabled_for_domain.clear(domain)
        domains_needing_search_index.clear()
        delete_case_search_cases_for_domain.delay(domain)
    return config


def case_search_enabled_domains():
    """Returns a list of all domains that have case search enabled
    """
    return CaseSearchConfig.objects.filter(enabled=True).values_list('domain', flat=True)
