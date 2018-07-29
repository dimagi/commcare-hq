from __future__ import absolute_import
from __future__ import unicode_literals
import re

from corehq.apps.es.case_search import CaseSearchES
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_MAX_RESULTS

from corehq.apps.case_search.models import (
    CaseSearchConfig,
    merge_queries,
    replace_custom_query_variables,
    CaseSearchQueryAddition,
    SEARCH_QUERY_ADDITION_KEY,
    SEARCH_QUERY_CUSTOM_VALUE,
    FuzzyProperties,
    CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY,
    UNSEARCHABLE_KEYS,
)


class CaseSearchCriteria(object):
    """Compiles the case search object for the view
    """

    def __init__(self, domain, case_type, criteria):
        self.domain = domain
        self.case_type = case_type
        self.criteria = criteria
        self.query_addition_debug_details = {}

        self.config = self._get_config()
        self.search_es = self._get_initial_search_es()

        self._assemble_optional_search_params()

    def _get_config(self):
        try:
            config = (CaseSearchConfig.objects
                      .prefetch_related('fuzzy_properties')
                      .prefetch_related('ignore_patterns')
                      .get(domain=self.domain))
        except CaseSearchConfig.DoesNotExist as e:
            from corehq.util.soft_assert import soft_assert
            _soft_assert = soft_assert(
                to="{}@{}.com".format('frener', 'dimagi'),
                notify_admins=False, send_to_ops=False
            )
            _soft_assert(
                False,
                "Someone in domain: {} tried accessing case search without a config".format(self.domain),
                e
            )
            config = CaseSearchConfig(domain=self.domain)
        return config

    def _get_initial_search_es(self):
        search_es = (CaseSearchES()
                     .domain(self.domain)
                     .case_type(self.case_type)
                     .size(CASE_SEARCH_MAX_RESULTS))
        return search_es

    def _assemble_optional_search_params(self):
        self._add_include_closed()
        self._add_owner_id()
        self._add_blacklisted_owner_ids()
        self._add_case_property_queries()
        self._add_case_search_additions()

    def _add_include_closed(self):
        try:
            include_closed = self.criteria.pop('include_closed')
        except KeyError:
            include_closed = False
        if include_closed != 'True':
            self.search_es = self.search_es.is_closed(False)

    def _add_owner_id(self):
        owner_id = self.criteria.pop('owner_id', False)
        if owner_id:
            self.search_es = self.search_es.owner(owner_id)

    def _add_blacklisted_owner_ids(self):
        blacklisted_owner_ids = self.criteria.pop(CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY, None)
        if blacklisted_owner_ids is not None:
            for blacklisted_owner_id in blacklisted_owner_ids.split(' '):
                self.search_es = self.search_es.blacklist_owner_id(blacklisted_owner_id)

    def _add_case_property_queries(self):
        try:
            fuzzies = self.config.fuzzy_properties.get(
                domain=self.domain, case_type=self.case_type).properties
        except FuzzyProperties.DoesNotExist:
            fuzzies = []

        for key, value in self.criteria.items():
            if key in UNSEARCHABLE_KEYS or key.startswith(SEARCH_QUERY_CUSTOM_VALUE):
                continue
            remove_char_regexs = self.config.ignore_patterns.filter(
                domain=self.domain,
                case_type=self.case_type,
                case_property=key,
            )
            for removal_regex in remove_char_regexs:
                to_remove = re.escape(removal_regex.regex)
                value = re.sub(to_remove, '', value)
            self.search_es = self.search_es.case_property_query(key, value, fuzzy=(key in fuzzies))

    def _add_case_search_additions(self):
        query_addition_id = self.criteria.pop(SEARCH_QUERY_ADDITION_KEY, None)
        if query_addition_id:
            ignore_patterns = self.config.ignore_patterns.filter(domain=self.domain, case_type=self.case_type)
            query_addition = CaseSearchQueryAddition.objects.get(
                id=query_addition_id, domain=self.domain).query_addition
            query_addition = replace_custom_query_variables(query_addition, self.criteria, ignore_patterns)
            self.query_addition_debug_details['original_query'] = self.search_es.get_query()
            self.query_addition_debug_details['query_addition'] = query_addition
            new_query = merge_queries(self.search_es.get_query(), query_addition)
            self.query_addition_debug_details['new_query'] = new_query
            self.search_es = self.search_es.set_query(new_query)
