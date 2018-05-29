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


def get_flattened_case_properties(domain):
    all_properties_by_type = all_case_properties_by_domain(domain, include_parent_properties=False)
    all_properties = [
        {'name': value, 'case_type': case_type}
        for case_type, values in six.iteritems(all_properties_by_type)
        for value in values
    ]
    return all_properties
