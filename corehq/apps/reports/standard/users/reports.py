import json

from django.db.models import Q
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from memoized import memoized

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import UserManagementReportDispatcher
from corehq.apps.reports.filters.users import (
    ChangeActionFilter,
    ChangedByUserFilter,
)
from corehq.apps.reports.filters.users import \
    ExpandedMobileWorkerFilter as EMWF
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin, ProjectReport
from corehq.apps.users.models import UserHistory
from corehq.apps.users.util import cached_user_id_to_username
from corehq.const import USER_DATETIME_FORMAT
from corehq.util.timezones.conversions import ServerTime


class UserHistoryReport(GetParamsMixin, DatespanMixin, GenericTabularReport, ProjectReport):
    slug = 'user_history'
    name = ugettext_lazy("User History")
    section_name = ugettext_lazy("User Management")

    dispatcher = UserManagementReportDispatcher

    fields = [
        'corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
        'corehq.apps.reports.filters.users.ChangedByUserFilter',
        'corehq.apps.reports.filters.users.ChangeActionFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter',
    ]

    description = ugettext_lazy("History of user updates")
    ajax_pagination = True

    sortable = False

    @property
    def headers(self):
        h = [
            DataTablesColumn(_("User")),
            DataTablesColumn(_("By User")),
            DataTablesColumn(_("Action")),
            DataTablesColumn(_("Via")),
            DataTablesColumn(_("Change Message")),
            DataTablesColumn(_("Changes")),
            DataTablesColumn(_("Timestamp")),
        ]

        return DataTablesHeader(*h)

    @property
    def total_records(self):
        return self._get_queryset().count()

    @memoized
    def _get_queryset(self):
        user_ids = self._get_user_ids()
        changed_by_user_ids = self._get_changed_by_user_ids()
        actions = self.request.GET.getlist('action')
        query = self._build_query(user_ids, changed_by_user_ids, actions)
        return query

    def _get_user_ids(self):
        es_query = self._get_users_es_query(self.request.GET.getlist(EMWF.slug))
        return es_query.values_list('_id', flat=True)

    def _get_changed_by_user_ids(self):
        es_query = self._get_users_es_query(self.request.GET.getlist(ChangedByUserFilter.slug))
        return es_query.values_list('_id', flat=True)

    def _get_users_es_query(self, slugs):
        return EMWF.user_es_query(
            self.domain,
            slugs,
            self.request.couch_user,
        )

    def _build_query(self, user_ids, changed_by_user_ids, actions):
        filters = Q(domain=self.domain)

        if user_ids:
            filters = filters & Q(user_id__in=user_ids)

        if changed_by_user_ids:
            filters = filters & Q(changed_by__in=changed_by_user_ids)

        if actions and ChangeActionFilter.ALL not in actions:
            filters = filters & Q(action__in=actions)

        if self.datespan:
            filters = filters & Q(changed_at__lt=self.datespan.enddate_adjusted,
                                  changed_at__gte=self.datespan.startdate)
        return UserHistory.objects.filter(filters)

    @property
    def rows(self):
        records = self._get_queryset().order_by('-changed_at')[
            self.pagination.start:self.pagination.start + self.pagination.count
        ]
        for record in records:
            yield _user_history_row(record, self.timezone)


def _user_history_row(record, timezone):
    return [
        cached_user_id_to_username(record.user_id),
        cached_user_id_to_username(record.changed_by),
        _get_action_display(record.action),
        record.details['changed_via'],
        record.message,
        json.dumps(record.details['changes']),
        ServerTime(record.changed_at).user_time(timezone).ui_string(USER_DATETIME_FORMAT),
    ]


def _get_action_display(logged_action):
    action = ugettext_lazy("Updated")
    if logged_action == UserHistory.CREATE:
        action = ugettext_lazy("Added")
    elif logged_action == UserHistory.DELETE:
        action = ugettext_lazy("Deleted")
    return action
