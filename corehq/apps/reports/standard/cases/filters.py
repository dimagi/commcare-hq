from __future__ import absolute_import
from __future__ import unicode_literals

import json

from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy

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
    template = "reports/filters/textarea.html"

    @property
    def filter_context(self):
        context = super(XpathCaseSearchFilter, self).filter_context
        context.update({
            'placeholder': "e.g. name = 'foo' and dob <= '2017-02-12'",
            'text': self.get_value(self.request, self.domain) or '',
        })

        return context


class CaseListExplorerColumns(BaseSimpleFilter):
    slug = 'explorer_columns'
    label = ugettext_lazy("Columns")
    template = "reports/filters/case_properties.html"

    DEFAULT_COLUMNS = [
        {'name': 'name', 'label': 'Name', 'is_default': True},
    ]

    @property
    def filter_context(self):
        context = super(CaseListExplorerColumns, self).filter_context
        initial_values = self.get_value(self.request, self.domain) or []

        user_value_names = [v['name'] for v in initial_values]
        for default_column in reversed(self.DEFAULT_COLUMNS):
            if default_column['name'] not in user_value_names:
                initial_values = [default_column] + initial_values

        context.update({
            'initial_value': json.dumps(initial_values),
        })
        return context

    @classmethod
    def get_value(cls, request, domain):
        value = super(CaseListExplorerColumns, cls).get_value(request, domain)
        return json.loads(value or "[]")
