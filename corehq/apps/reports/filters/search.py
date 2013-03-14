from corehq.apps.reports.filters.base import BaseReportFilter


class SearchFilter(BaseReportFilter):
    slug = "search_query"
    template = "reports/filters/search.html"
    label= "Search"


    @property
    def filter_context(self):
        print "in filter context"
        return {
            'search_query': self.request.GET.get('search_query', None)
        }
