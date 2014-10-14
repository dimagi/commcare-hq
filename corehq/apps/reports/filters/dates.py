import datetime
import logging
import simplejson

from django.utils.translation import ugettext_lazy, ugettext as _

from dimagi.utils.dates import DateSpan
from dimagi.utils.parsing import string_to_datetime

from corehq.apps.reports.filters.base import BaseReportFilter
from corehq.apps.sofabed.models import FormData
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
        """
        Return the earliest date of form submission for the domain
        falling back to 30 days.
        """
        days = 30
        forms = (FormData.objects
                 .filter(domain=self.domain)
                 .order_by('received_on'))
        if forms.count():
            start_date = forms[0].received_on.replace(tzinfo=self.timezone)
            end_date = datetime.datetime.now(self.timezone)
            days = (end_date - start_date).days
        return days
