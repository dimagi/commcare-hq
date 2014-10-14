from dateutil import parser
import datetime
import logging
import simplejson
from corehq.apps.reports.filters.base import BaseReportFilter

# For translations
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from dimagi.utils.dates import DateSpan
from corehq.elastic import es_query, ES_URLS


class DatespanFilter(BaseReportFilter):
    """
        A filter that returns a startdate and an enddate.
        This is the standard datespan filter that gets pulled into request with the decorator
        @datespan_in_request
    """
    template = "reports/filters/datespan.html"
    label = ugettext_lazy("Date Range")
    slug = "datespan"
    inclusive = True
    default_days = 30

    @property
    def datespan(self):
        datespan = DateSpan.since(self.default_days, format="%Y-%m-%d", timezone=self.timezone, inclusive=self.inclusive)
        if self.request.datespan.is_valid() and self.slug == 'datespan':
            datespan.startdate = self.request.datespan.startdate
            datespan.enddate = self.request.datespan.enddate
        return datespan

    @property
    def filter_context(self):
        return {
            'datespan': self.datespan,
            'report_labels': self.report_labels,
            'separator': _(' to '),
            'timezone': self.timezone.zone,
        }

    @property
    def report_labels(self):
        return simplejson.dumps({
            'last_7_days': _('Last 7 Days'),
            'last_month': _('Last Month'),
            'last_30_days': _('Last 30 Days')
        })


class SubmitHistoryDatespanFilter(DatespanFilter):

    @property
    def default_days(self):
        days = 30
        # This query will obtain earliest submission form date in current domain,
        # otherwiste it will return default datespan(30days)
        q = { "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "and": [
                            {"term": { "domain.exact": self.domain }},
                        ]
                    }
                }
            },
            'sort': [{'received_on': {"order": "asc"}}],
            'size': 1
        }
        logging.info("ESlog: [%s.%s] ESquery: %s" % (self.__class__.__name__, self.domain, simplejson.dumps(q)))
        es_results = es_query(q=q, es_url=ES_URLS['forms'], dict_only=False)['hits'].get('hits', [])

        if len(es_results) > 0:
            start_date = parser.parse(es_results[0]['_source']['received_on']).replace(tzinfo=self.timezone)
            end_date = datetime.datetime.now(self.timezone)
            days = (end_date - start_date).days
        return days
