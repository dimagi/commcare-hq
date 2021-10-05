from django.utils.functional import cached_property
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from corehq.apps.auditcare.models import NavigationEventAudit
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin, ProjectReport
from corehq.util.timezones.conversions import ServerTime


class WebUserActivityReport(GetParamsMixin, DatespanMixin, GenericTabularReport, ProjectReport):
    slug = 'web_user_activity'
    name = ugettext_noop("Web User Activity")
    ajax_pagination = True

    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.simple.SimpleUsername',
    ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Username")),
            DataTablesColumn(_("Date")),
            DataTablesColumn(_("Report")),
        )

    @property
    def rows(self):
        events = self._get_queryset()[self.pagination.start:self.pagination.end]
        for event in events:
            yield [
                event.user,
                ServerTime(event.event_date).user_time(self.timezone).ui_string(),
                self._get_report_name(event.view_kwargs.get('report_slug')),
            ]

    @property
    def total_records(self):
        return self._get_queryset().count()

    def _get_queryset(self):
        username = self.request.GET.get('username')
        return NavigationEventAudit.objects.filter(
            domain=self.domain,
            user=username,
            event_date__gt=self.datespan.startdate,
            event_date__lt=self.datespan.enddate_adjusted,
            view_fk__value= 'corehq.apps.reports.dispatcher.ProjectReportDispatcher',
        ).select_related('view_fk')

    def _get_report_name(self, slug):
        if slug and slug in self._report_names_by_slug:
            return self._report_names_by_slug[slug]
        return "Unknown"

    @cached_property
    def _report_names_by_slug(self):
        from corehq.reports import REPORTS
        return {
            report.slug: report.name
            for tab in REPORTS(self.request.project) for report in tab[1]
        }
