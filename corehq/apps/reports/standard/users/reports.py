from django.contrib.admin.models import LogEntry
from django.contrib.admin.options import get_content_type_for_model
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from memoized import memoized

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import UserManagementReportDispatcher
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter as EMWF
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin, ProjectReport
from corehq.apps.reports.util import datespan_from_beginning
from corehq.const import USER_DATETIME_FORMAT
from corehq.util.timezones.conversions import ServerTime


class UserHistoryReport(GetParamsMixin, DatespanMixin, GenericTabularReport, ProjectReport):
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
        h = [
            DataTablesColumn(_("User")),
            DataTablesColumn(_("By User")),
            DataTablesColumn(_("Action")),
            DataTablesColumn(_("Change Message")),
            DataTablesColumn(_("Time")),
        ]

        return DataTablesHeader(*h)

    @property
    def total_records(self):
        return self._get_queryset().count()

    @memoized
    def _get_queryset(self):
        usernames = self._get_usernames()
        # users needed to filter on, without it we would expose all log entries in the system
        # so return empty if none available
        if not usernames:
            return LogEntry.objects.none()

        query = self._build_query(usernames)
        return query.order_by('-action_time')

    def _get_usernames(self):
        mobile_user_and_group_slugs = set(
            self.request.GET.getlist(EMWF.slug)
        )

        return EMWF.user_es_query(
            self.domain,
            mobile_user_and_group_slugs,
            self.request.couch_user,
        ).values_list('username', flat=True)

    def _build_query(self, usernames):
        query = LogEntry.objects.select_related('user')
        query = query.filter(content_type=_user_model_content_type())

        query = query.filter(object_repr__in=usernames)
        if self.datespan:
            query = query.filter(action_time__lt=self.datespan.enddate_adjusted,
                                 action_time__gte=self.datespan.startdate)
        return query.order_by('-action_time')

    @property
    def rows(self):
        records = self._get_queryset()[self.pagination.start:self.pagination.start + self.pagination.count]
        for log_entry in records:
            yield _log_entry_display(log_entry)


@memoized
def _user_model_content_type():
    return get_content_type_for_model(User)


def _log_entry_display(log_entry):
    return [
        log_entry.object_repr,
        log_entry.user.username,
        _get_action_display(log_entry),
        log_entry.change_message,
        ServerTime(log_entry.action_time).ui_string(USER_DATETIME_FORMAT),
    ]


def _get_action_display(log_entry):
    action = ugettext_lazy("Updated")
    if log_entry.is_addition():
        action = ugettext_lazy("Added")
    elif log_entry.is_deletion():
        action = ugettext_lazy("Deleted")
    return action
