from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from memoized import memoized

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import UserManagementReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin, ProjectReport
from corehq.apps.reports.util import datespan_from_beginning
from corehq.apps.users.models import UserHistory


class UserHistoryReport(DatespanMixin, GenericTabularReport, ProjectReport):
    slug = 'user_history'
    name = ugettext_lazy("User History")
    section_name = ugettext_lazy("User Management")

    dispatcher = UserManagementReportDispatcher

    # ToDo: Add pending filters
    fields = [
        'corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter',
    ]

    description = ugettext_lazy("History of user updates")
    ajax_pagination = True

    sortable = False

    @property
    def default_datespan(self):
        return datespan_from_beginning(self.domain_object, self.timezone)

    @property
    def headers(self):
        # ToDo: Add headers
        h = [
            DataTablesColumn(_("User")),
        ]

        return DataTablesHeader(*h)

    @property
    def total_records(self):
        return self._get_queryset().count()

    @memoized
    def _get_queryset(self):
        # ToDo: add query based on params
        return UserHistory.objects.none()

    @property
    def rows(self):
        records = self._get_queryset().order_by('-changed_at')[
            self.pagination.start:self.pagination.start + self.pagination.count
        ]
        for record in records:
            yield _user_history_row(record)


def _user_history_row(record):
    # ToDo: add render for each row
    return []
