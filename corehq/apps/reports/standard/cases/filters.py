from __future__ import absolute_import
from __future__ import unicode_literals

import json

from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy
import six

from corehq.apps.app_manager.app_schemas.case_properties import (
    all_case_properties_by_domain,
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
            'all_case_properties': json.dumps(get_flattened_case_properties(self.domain)),
        })

        return context


class CaseListExplorerColumns(BaseSimpleFilter):
    slug = 'explorer_columns'
    label = ugettext_lazy("Columns")
    template = "reports/filters/case_properties.html"
    PERSISTENT_COLUMNS = [
        {'name': '_link', 'label': 'Link', 'hidden': True},
    ]

    DEFAULT_COLUMNS = [
        {'name': 'type', 'label': 'Case Type', 'hidden': False},
        {'name': 'name', 'label': 'Case Name', 'hidden': False},
        {'name': 'owner_id', 'label': 'Owner ID', 'hidden': False},
        {'name': 'modified_on', 'label': 'Last Modified Date', 'hidden': False},

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
            'all_case_properties': json.dumps(get_flattened_case_properties(self.domain)),
        })
        return context

    @classmethod
    def get_value(cls, request, domain):
        value = super(CaseListExplorerColumns, cls).get_value(request, domain)
        return json.loads(value or "[]")


def get_flattened_case_properties(domain):
    all_properties_by_type = all_case_properties_by_domain(domain, include_parent_properties=False)
    all_properties = [
        {'name': value, 'caseType': case_type}
        for case_type, values in six.iteritems(all_properties_by_type)
        for value in values
    ]
    return all_properties
