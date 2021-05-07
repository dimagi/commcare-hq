from django.contrib.admin.models import LogEntry
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from memoized import memoized

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import UserManagementReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin, ProjectReport
from corehq.apps.reports.util import datespan_from_beginning


class UserHistoryReport(DatespanMixin, GenericTabularReport, ProjectReport):
    slug = 'user_history'
    name = ugettext_lazy("User History")
    section_name = ugettext_lazy("User Management")

    dispatcher = UserManagementReportDispatcher

    fields = [
        'corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter',
    ]

    description = ugettext_lazy("History of user updates")
    ajax_pagination = True

    sortable = False  # keep it simple for now

    @property
    def default_datespan(self):
        return datespan_from_beginning(self.domain_object, self.timezone)

    @property
    def headers(self):
        # ToDo: Add headers
        h = [
            DataTablesColumn(_("By User")),
            DataTablesColumn(_("For User")),
        ]

        return DataTablesHeader(*h)

    @property
    def total_records(self):
        return self._get_queryset().count()

    @memoized
    def _get_queryset(self):
        # ToDo: filter based on params
        query = LogEntry.objects
        return query.order_by('-action_time')

    @property
    def rows(self):
        records = self._get_queryset()[self.pagination.start:self.pagination.start + self.pagination.count]
        for log_entry in records:
            yield _log_entry_display(log_entry)


def _log_entry_display(log_entry):
    # ToDo: add other columns
    return [
        log_entry.user.username,
        log_entry.object_repr,
    ]
