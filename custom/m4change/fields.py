import datetime
from corehq.util.dates import iso_string_to_date
from dimagi.utils.dates import DateSpan
import json
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.reports.dont_use.fields import ReportField


class DateRangeField(ReportField):
    name = ugettext_noop("Date Range")
    slug = "datespan"
    template = "m4change/fields/daterange.html"
    inclusive = True
    default_days = 30

    def update_context(self):
        self.context["datespan_name"] = self.name

        range = self.request.GET.get('range', None)
        if range:
            dates = str(range).split(_(' to '))
            self.request.datespan.startdate = datetime.datetime.combine(
                iso_string_to_date(dates[0]), datetime.time())
            self.request.datespan.enddate = datetime.datetime.combine(
                iso_string_to_date(dates[1]), datetime.time())

        self.datespan = DateSpan.since(self.default_days, timezone=self.timezone, inclusive=self.inclusive)
        if self.request.datespan.is_valid():
            self.datespan.startdate = self.request.datespan.startdate
            self.datespan.enddate = self.request.datespan.enddate
        self.context['timezone'] = self.timezone.zone
        self.context['datespan'] = self.datespan

        report_labels = json.dumps({
            'year_to_date': _('Year to Date'), 'last_month': _('Last Month'),
            'last_quarter': _('Last Quarter'), 'last_two_quarters': _('Last Two Quarters'),
            'last_three_quarters': _('Last Three Quarters'), 'last_year': _('Last Year'),
            'last_two_years': _('Last Two Years'), 'last_three_years': _('Last Three Years'),
            'last_four_years': _('Last Four Years')
        })

        self.context['report_labels'] = report_labels
        self.context['separator'] = _(' to ')


class CaseSearchField(ReportField):
    name = ugettext_noop("Case Search")
    slug = "case_search"
    template = "reports/filters/search.html"

    def update_context(self):
        self.search_query = self.request.GET.get("case_search", "")
        self.context["search_query"] = self.search_query
        self.context["label"] = _("Case Search")
