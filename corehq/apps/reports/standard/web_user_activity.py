from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from corehq.apps.auditcare.models import NavigationEventAudit
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin, ProjectReport


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
            yield [
                event.user,
                event.event_date,
                event.path,
                event.view,
                event.params,
                event.view_kwargs,
                event.status_code,
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
        ).select_related('view_fk')
