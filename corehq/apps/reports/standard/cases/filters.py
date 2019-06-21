from __future__ import absolute_import, unicode_literals

import json
from collections import Counter

import six
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy

from corehq.apps.app_manager.app_schemas.case_properties import (
    all_case_properties_by_domain,
)
from corehq.apps.case_search.const import (
    CASE_COMPUTED_METADATA,
    SPECIAL_CASE_PROPERTIES,
)
from corehq.apps.reports.filters.base import BaseSimpleFilter


class CaseSearchFilter(BaseSimpleFilter):
    slug = 'search_query'
    label = ugettext_lazy("Search")
    help_inline = mark_safe(ugettext_lazy(
        'Search any text, or use a targeted query. For more info see the '
        '<a href="https://wiki.commcarehq.org/display/commcarepublic/'
        'Advanced+Case+Search" target="_blank">Case Search</a> help page'
    ))


class XpathCaseSearchFilter(BaseSimpleFilter):
    slug = 'search_xpath'
    label = ugettext_lazy("Search")
    template = "reports/filters/xpath_textarea.html"

    @property
    def filter_context(self):
        context = super(XpathCaseSearchFilter, self).filter_context
        context.update({
            'placeholder': "e.g. name = 'foo' and dob <= '2017-02-12'",
            'text': self.get_value(self.request, self.domain) or '',
            'suggestions': json.dumps(self.get_suggestions()),
        })

        return context

    def get_suggestions(self):
        case_properties = get_flattened_case_properties(self.domain, include_parent_properties=True)
        special_case_properties = [
            {'name': prop, 'case_type': None, 'meta_type': 'info'}
            for prop in SPECIAL_CASE_PROPERTIES
        ]
        operators = [
            {'name': prop, 'case_type': None, 'meta_type': 'operator'}
            for prop in ['=', '!=', '>=', '<=', '>', '<', 'and', 'or']
        ]
        return case_properties + special_case_properties + operators


class CaseListExplorerColumns(BaseSimpleFilter):
    slug = 'explorer_columns'
    label = ugettext_lazy("Columns")
    template = "reports/filters/explorer_columns.html"
    DEFAULT_COLUMNS = ['@case_type', 'case_name', 'last_modified']

    @property
    def filter_context(self):
        context = super(CaseListExplorerColumns, self).filter_context

        initial_values = self.get_value(self.request, self.domain)
        if not initial_values:
            initial_values = self.DEFAULT_COLUMNS

        context.update({
            'initial_value': json.dumps(initial_values),
            'column_suggestions': json.dumps(self.get_column_suggestions()),
        })
        return context

    def get_column_suggestions(self):
        case_properties = get_flattened_case_properties(self.domain, include_parent_properties=False)
        special_properties = [
            {'name': prop, 'case_type': None, 'meta_type': 'info'}
            for prop in SPECIAL_CASE_PROPERTIES + CASE_COMPUTED_METADATA
        ]
        return case_properties + special_properties

    @classmethod
    def get_value(cls, request, domain):
        value = super(CaseListExplorerColumns, cls).get_value(request, domain)
        return json.loads(value or "[]")


def get_flattened_case_properties(domain, include_parent_properties=False):
    all_properties_by_type = all_case_properties_by_domain(
        domain,
        include_parent_properties=include_parent_properties
    )
    property_counts = Counter(item for sublist in all_properties_by_type.values() for item in sublist)
    all_properties = [
        {'name': value, 'case_type': case_type, 'count': property_counts[value]}
        for case_type, values in six.iteritems(all_properties_by_type)
        for value in values
    ]
    return all_properties
