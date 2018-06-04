from __future__ import absolute_import
from __future__ import unicode_literals

import json

from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy, ugettext as _
import six

from corehq.apps.app_manager.app_schemas.case_properties import (
    all_case_properties_by_domain,
)
from corehq.apps.case_search.const import SPECIAL_CASE_PROPERTIES, CASE_COMPUTED_METADATA
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
            'all_case_properties': json.dumps(get_flattened_case_properties(self.domain)),
        })

        return context


class CaseListExplorerColumns(BaseSimpleFilter):
    slug = 'explorer_columns'
    label = ugettext_lazy("Columns")
    template = "reports/filters/explorer_columns.html"
    PERSISTENT_COLUMNS = [
        # hidden from view, but used for sorting when no sort column is provided
        {'name': 'last_modified', 'label': 'Last Modified Date', 'hidden': True, 'editable': False},
        # shown, but unremovable so there is always at least one column
        {'name': '_link', 'label': _('Link'), 'editable': False},
    ]

    DEFAULT_COLUMNS = [
        {'name': '@case_type', 'label': _('Case Type')},
        {'name': 'case_name', 'label': _('Case Name')},
        {'name': 'owner_name', 'label': _('Owner Name')},
        {'name': 'date_opened', 'label': _('Date Opened')},
        {'name': 'opened_by_username', 'label': _('Opened By Username')},
        {'name': 'last_modified', 'label': _('Last Modified')},
        {'name': '@status', 'label': _('Status')},
    ]

    @property
    def filter_context(self):
        context = super(CaseListExplorerColumns, self).filter_context
        initial_values = self.get_value(self.request, self.domain) or []

        user_value_names = [v['name'] for v in initial_values]
        if not user_value_names:
            initial_values = self.DEFAULT_COLUMNS

        for persistent_column in reversed(self.PERSISTENT_COLUMNS):
            if persistent_column['name'] not in user_value_names:
                initial_values = [persistent_column] + initial_values

        context.update({
            'initial_value': json.dumps(initial_values),
            'column_suggestions': json.dumps(self.get_column_suggestions()),
        })
        return context

    def get_column_suggestions(self):
        case_properties = get_flattened_case_properties(self.domain)
        special_properties = [
            {'name': prop, 'case_type': None, 'meta_type': 'info'}
            for prop in SPECIAL_CASE_PROPERTIES + CASE_COMPUTED_METADATA
        ]
        return case_properties + special_properties

    @classmethod
    def get_value(cls, request, domain):
        value = super(CaseListExplorerColumns, cls).get_value(request, domain)
        return json.loads(value or "[]")


def get_flattened_case_properties(domain):
    all_properties_by_type = all_case_properties_by_domain(domain, include_parent_properties=False)
    all_properties = [
        {'name': value, 'case_type': case_type}
        for case_type, values in six.iteritems(all_properties_by_type)
        for value in values
    ]
    return all_properties
