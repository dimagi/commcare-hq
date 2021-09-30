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
    description = ugettext_noop("TODO")
    ajax_pagination = True

    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.simple.SimpleUsername',
    ]

    @cached_property
    def _reports_only(self):
        return 'reports' in self.request.GET

    @property
    def headers(self):
        if self._reports_only:
            return DataTablesHeader(
                DataTablesColumn(_("Username")),
                DataTablesColumn(_("Date")),
                DataTablesColumn(_("Report")),
            )
        return DataTablesHeader(
            DataTablesColumn(_("Username")),
            DataTablesColumn(_("Date")),
            DataTablesColumn(_("Request Path")),
            DataTablesColumn(_("View Name")),
            DataTablesColumn(_("Params")),
            DataTablesColumn(_("View Kwargs")),
            DataTablesColumn(_("Status")),
        )

    @property
    def rows(self):
        events = self._get_queryset()[self.pagination.start:self.pagination.end]
        for event in events:
            if self._reports_only:
                yield [
                    event.user,
                    ServerTime(event.event_date).user_time(self.timezone).ui_string(),
                    self._get_report_name(event.view_kwargs.get('report_slug')),
                ]
            else:
                yield [
                    event.user,
                    event.event_date,
                    event.path,
                    event.view,
                    event.params,
                    str(event.view_kwargs),
                    event.status_code,
                ]

    @property
    def total_records(self):
        return self._get_queryset().count()

    def _get_queryset(self):
        username = self.request.GET.get('username')
        queryset = NavigationEventAudit.objects.filter(
            domain=self.domain,
            user=username,
            event_date__gt=self.datespan.startdate,
            event_date__lt=self.datespan.enddate_adjusted,
        )
        if self._reports_only:
            queryset = queryset.filter(
                view_fk__value= 'corehq.apps.reports.dispatcher.ProjectReportDispatcher')
        return queryset.select_related('view_fk')

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
