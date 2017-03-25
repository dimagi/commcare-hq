import random
from datetime import timedelta, date

from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.graph_models import PieChart, MultiBarChart, Axis
from corehq.apps.reports_core.filters import Choice
from corehq.apps.style.decorators import use_nvd3
from corehq.apps.userreports.models import StaticReportConfiguration
from corehq.apps.userreports.reports.factory import ReportFactory
from custom.enikshay.reports.filters import EnikshayLocationFilter, EnikshayMigrationFilter
from custom.enikshay.reports.generic import EnikshayReport
from custom.enikshay.reports.sqldata.case_finding_sql_data import CaseFindingSqlData
from custom.enikshay.reports.sqldata.charts_sql_data import ChartsSqlData
from custom.enikshay.reports.sqldata.treatment_outcome_sql_data import TreatmentOutcomeSqlData
from dimagi.utils.decorators.memoized import memoized

from django.utils.translation import ugettext_lazy, ugettext as _


@location_safe
class HistoricalAdherenceReport(EnikshayReport):

    name = ugettext_lazy('Historical Adherence')
    report_title = ugettext_lazy('Historical Adherence')
    slug = 'historical_adherence'
    use_datatables = False
    report_template_path = 'enikshay/historical_adherence.html'
    fields = (DatespanFilter,)

    emailable = False

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        return super(HistoricalAdherenceReport, self).decorator_dispatcher(request, *args, **kwargs)

    @property
    def headers(self):
        return DataTablesHeader()

    @property
    def rows(self):
        return []

    @property
    def report_context(self):
        report_context = super(HistoricalAdherenceReport, self).report_context
        calendar = []  # An array of weeks
        for week_index in range(6*4):
            sunday = date(2016, 1, 3) +timedelta(days=7*week_index)
            week = Week(sunday)
            calendar.append(week)

        calendar[0].days[0].display = False
        calendar[0].days[1].display = False

        report_context['weeks'] = calendar

        return report_context


class Week(object):
    def __init__(self, sunday):
        self.days = [
            Day(sunday + timedelta(days=x))
            for x in range(7)
        ]


class Day(object):

    def __init__(self, date):
        self.date = date
        self.month_string = self.date.strftime("%b") if self.date.day == 1 else 0
        self.day_string = self.date.day
        self.display = True
        self.adherence = random.random() > .1
