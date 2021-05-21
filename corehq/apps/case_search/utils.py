import re
from django.utils.translation import ugettext as _

from casexml.apps.case.models import CommCareCase
from corehq.apps.app_manager.dbaccessors import get_app_cached
from corehq.apps.app_manager.util import module_offers_search
from corehq.apps.case_search.models import (
    CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY,
    CASE_SEARCH_XPATH_QUERY_KEY,
    SEARCH_QUERY_CUSTOM_VALUE,
    UNSEARCHABLE_KEYS,
    CaseSearchConfig,
    FuzzyProperties,
)
from corehq.apps.es.case_search import CaseSearchES, flatten_result
from corehq.apps.case_search.const import CASE_SEARCH_MAX_RESULTS
from corehq.apps.case_search.filter_dsl import CaseFilterError


class CaseSearchCriteria(object):
    """Compiles the case search object for the view
    """

    def __init__(self, domain, case_type, criteria):
        self.domain = domain
        self.case_type = case_type
        self.criteria = criteria

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
                     .is_closed(False)
                     .size(CASE_SEARCH_MAX_RESULTS)
                     .set_sorting_block(['_score', '_doc']))
        return search_es

    def _assemble_optional_search_params(self):
        self._add_xpath_query()
        self._add_owner_id()
        self._add_blacklisted_owner_ids()
        self._add_daterange_queries()
        self._add_case_property_queries()

    def _validate_param_value(self, key, value):
        if isinstance(value, list):
            raise CaseFilterError(
                _("Multiple xpath queries for a query param is not supported"),
                key
            )

    def _add_xpath_query(self):
        query = self.criteria.pop(CASE_SEARCH_XPATH_QUERY_KEY, None)
        self._validate_param_value(CASE_SEARCH_XPATH_QUERY_KEY, query)
        if query:
            self.search_es = self.search_es.xpath_query(self.domain, query)

    def _add_owner_id(self):
        owner_id = self.criteria.pop('owner_id', False)
        self._validate_param_value('owner_id', owner_id)
        if owner_id:
            self.search_es = self.search_es.owner(owner_id)

    def _add_blacklisted_owner_ids(self):
        blacklisted_owner_ids = self.criteria.pop(CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY, None)
        if blacklisted_owner_ids is not None:
            for blacklisted_owner_id in blacklisted_owner_ids.split(' '):
                self.search_es = self.search_es.blacklist_owner_id(blacklisted_owner_id)

    def _add_daterange_queries(self):
        # Add query for specially formatted daterange param
        #   The format is __range__YYYY-MM-DD__YYYY-MM-DD, which is
        #   used by App manager case-search feature
        pattern = re.compile(r'__range__\d{4}-\d{2}-\d{2}__\d{4}-\d{2}-\d{2}')
        drop_keys = []
        for key, val in self.criteria.items():
            # multiple daterange query param values are not supported
            if not isinstance(val, list) and val.startswith('__range__'):
                match = pattern.match(val)
                if match:
                    [_, _, startdate, enddate] = val.split('__')
                    drop_keys.append(key)
                    self.search_es = self.search_es.date_range_case_property_query(
                        key, gte=startdate, lte=enddate)
        for key in drop_keys:
            self.criteria.pop(key)

    def _add_case_property_queries(self):
        try:
            fuzzies = self.config.fuzzy_properties.get(
                domain=self.domain, case_type=self.case_type).properties
        except FuzzyProperties.DoesNotExist:
            fuzzies = []

        for key, value in self.criteria.items():
            if (key in UNSEARCHABLE_KEYS or key.startswith(SEARCH_QUERY_CUSTOM_VALUE)
                    or key.startswith('__range__')):
                continue
            remove_char_regexs = self.config.ignore_patterns.filter(
                domain=self.domain,
                case_type=self.case_type,
                case_property=key,
            )
            for removal_regex in remove_char_regexs:
                to_remove = re.escape(removal_regex.regex)
                if isinstance(value, list):
                    new_value = []
                    for val in value:
                        new_value.append(re.sub(to_remove, '', value))
                else:
                    value = re.sub(to_remove, '', value)

            if '/' in key:
                self._validate_param_value(key, value)
                query = '{} = "{}"'.format(key, value)
                self.search_es = self.search_es.xpath_query(self.domain, query, fuzzy=(key in fuzzies))
            else:
                self.search_es = self.search_es.case_property_query(key, value, fuzzy=(key in fuzzies))


def get_related_cases(domain, app_id, case_type, cases):
    """
    Fetch related cases that are necessary to display any related-case
    properties in the app requesting this case search.

    Returns list of CommCareCase objects for adding to CaseDBFixture.
    """
    if not cases:
        return []

    app = get_app_cached(domain, app_id)
    paths = get_related_case_relationships(app, case_type)
    if not paths:
        return []
    return get_related_case_results(domain, cases, paths)


def get_related_case_relationships(app, case_type):
    """
    Get unique case relationships used by search details in any modules that
    match the given case type and are configured for case search.

    Returns a set of paths, e.g. {"parent", "host", "parent/parent"}
    """
    paths = set()
    for module in app.get_modules():
        if module.case_type == case_type and module_offers_search(module):
            for column in module.search_detail("short").columns + module.search_detail("long").columns:
                if not column.useXpathExpression:
                    parts = column.field.split("/")
                    if len(parts) > 1:
                        parts.pop()     # keep only the relationship: "parent", "parent/parent", etc.
                        paths.add("/".join(parts))
    return paths


def get_related_case_results(domain, cases, paths):
    """
    Given a set of cases and a set of case property paths,
    fetches ES documents for all cases referenced by those paths.
    """
    if not cases:
        return []

    results_cache = {}
    for path in paths:
        current_cases = cases
        parts = path.split("/")
        for index, identifier in enumerate(parts):
            fragment = "/".join(parts[:index + 1])
            if fragment in results_cache:
                current_cases = results_cache[fragment]
            else:
                indices = [case.get_index(identifier) for case in current_cases]
                related_case_ids = {i.referenced_id for i in indices if i}
                results = CaseSearchES().domain(domain).case_ids(related_case_ids).run().hits
                current_cases = [CommCareCase.wrap(flatten_result(result)) for result in results]
                results_cache[fragment] = current_cases

    results = []
    for path in paths:
        results.extend(results_cache[path])

    return results
