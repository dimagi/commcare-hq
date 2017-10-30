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
