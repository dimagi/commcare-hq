from __future__ import absolute_import
from __future__ import unicode_literals
import copy
import re
import json

from corehq.util.quickcache import quickcache
from django.db import models
from jsonfield.fields import JSONField
from django.contrib.postgres.fields import ArrayField
import six


CLAIM_CASE_TYPE = 'commcare-case-claim'
FUZZY_PROPERTIES = "fuzzy_properties"
SEARCH_QUERY_ADDITION_KEY = 'commcare_custom_search_query'
SEARCH_QUERY_CUSTOM_VALUE = 'commcare_custom_value'
CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY = 'commcare_blacklisted_owner_ids'
UNSEARCHABLE_KEYS = (
    SEARCH_QUERY_ADDITION_KEY,
    CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY,
    'owner_id',
)


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


class CaseSearchQueryAddition(models.Model):
    domain = models.CharField(
        max_length=256,
        null=False,
        blank=False,
        db_index=True,
    )
    name = models.CharField(max_length=256, null=False, blank=False)
    query_addition = JSONField(
        default=dict,
        help_text="More information about how this field is used can be found <a href='https://docs.google.com/doc"
                  "ument/d/1MKllkHZ6JlxhfqZLZKWAnfmlA3oUqCLOc7iKzxFTzdY/edit#heading=h.k5pky76mwwon'>here</a>. Thi"
                  "s ES <a href='https://www.elastic.co/guide/en/elasticsearch/guide/1.x/bool-query.html'>document"
                  "ation</a> may also be useful. This JSON will be merged at the `query.filtered.query` path of th"
                  "e query JSON."
    )


class QueryMergeException(Exception):
    pass


def replace_custom_query_variables(query_addition, criteria, ignore_patterns):
    """Replaces values in custom queries with user input

    - In the custom query add '__{case_property_name}' as the value for the
      case property you are searching
    - In the case search options, add
      commcare_custom_value__{case_property_name} as the name of the property
      you are searching for.

    https://docs.google.com/document/d/1MKllkHZ6JlxhfqZLZKWAnfmlA3oUqCLOc7iKzxFTzdY/edit#heading=h.suj6zzehvecp
    """
    replaceable_criteria = {
        re.sub(SEARCH_QUERY_CUSTOM_VALUE, '', k): v
        for k, v in six.iteritems(criteria) if k.startswith(SEARCH_QUERY_CUSTOM_VALUE)
    }

    # Only include this custom query if the replaceable parts are present
    # TODO: do this only for specific parts of the custom query
    conditional_include = query_addition.get('include_if')
    if conditional_include and not replaceable_criteria.get(conditional_include):
        return {}
    elif conditional_include:
        del query_addition['include_if']

    query_addition = json.dumps(query_addition)
    for key, value in six.iteritems(replaceable_criteria):
        if ignore_patterns:
            remove_char_regexs = ignore_patterns.filter(
                case_property=re.sub('^__', '', key)
            )
            for removal_regex in remove_char_regexs:
                to_remove = re.escape(removal_regex.regex)
                value = re.sub(to_remove, '', value)
        to_add = re.escape(value)
        query_addition = re.sub(key, to_add, query_addition)

    query_addition = query_addition.replace('\\', '')
    return json.loads(query_addition)


def merge_queries(base_query, query_addition):
    """
    Merge query_addition into a copy of base_query.
    :param base_query: An elasticsearch query (dictionary)
    :param query_addition: A dictionary
    :return: The new merged query
    """

    def merge(a, b, path=None):
        """Merge b into a"""

        if path is None:
            path = []
        for key in b:
            if key in a:
                if isinstance(a[key], dict) and isinstance(b[key], dict):
                    merge(a[key], b[key], path + [str(key)])
                elif a[key] == b[key]:
                    pass  # same leaf value
                elif type(a[key]) == list and type(b[key]) == list:
                    a[key] += b[key]
                else:
                    raise QueryMergeException('Conflict at %s' % '.'.join(path + [str(key)]))
            else:
                a[key] = b[key]
        return a

    new_query = copy.deepcopy(base_query)
    try:
        merge(new_query, query_addition)
    except QueryMergeException as e:
        e.original_query = base_query
        e.query_addition = query_addition
        raise e
    return new_query


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
    config, created = CaseSearchConfig.objects.get_or_create(pk=domain)
    if not config.enabled:
        config.enabled = True
        config.save()
        case_search_enabled_for_domain.clear(domain)
        reindex_case_search_for_domain.delay(domain)


def disable_case_search(domain):
    from corehq.apps.case_search.tasks import delete_case_search_cases_for_domain
    try:
        config = CaseSearchConfig.objects.get(pk=domain)
    except CaseSearchConfig.DoesNotExist:
        # CaseSearch was never enabled
        return
    if config.enabled:
        config.enabled = False
        config.save()
        case_search_enabled_for_domain.clear(domain)
        delete_case_search_cases_for_domain.delay(domain)


def case_search_enabled_domains():
    """Returns a list of all domains that have case search enabled
    """
    return CaseSearchConfig.objects.filter(enabled=True).values_list('domain', flat=True)
