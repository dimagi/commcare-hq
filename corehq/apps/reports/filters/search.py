from corehq.apps.reports.filters.base import BaseReportFilter


class SearchFilter(BaseReportFilter):
    slug = "search_query"
    template = "reports/filters/search.html"
    label = "Search"
    search_help_title = None
    search_help_content = None


    @property
    def filter_context(self):
        return {
            'search_query': self.request.GET.get('search_query', ""),
            'search_help_title': self.search_help_title,
            'search_help_content': self.search_help_content
        }
