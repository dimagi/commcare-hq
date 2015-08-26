from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy
from corehq.apps.reports.filters.search import SearchFilter


class CaseSearchFilter(SearchFilter):
    search_help_inline = mark_safe(ugettext_lazy(
        'Search any text, or use a targeted query. For more info see the '
        '<a href="https://wiki.commcarehq.org/display/commcarepublic/'
        'Advanced+Case+Search" target="_blank">Case Search</a> help page'
    ))
