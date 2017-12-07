from __future__ import absolute_import
from django.core.exceptions import PermissionDenied
from corehq.apps.es import UserES
from corehq.apps.es.users import mobile_users
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.analytics.esaccessors import get_submission_counts_by_user
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.standard.monitoring import WorkerActivityReport
from corehq.apps.reports.util import get_simplified_users
from custom.enikshay.reports.filters import EnikshayLocationFilter

from django.utils.translation import ugettext as _, ugettext_lazy

from dimagi.utils.decorators.memoized import memoized


@location_safe
class EnikshayWorkerActivityReport(WorkerActivityReport, CustomProjectReport):
    name = ugettext_lazy('Worker Form Activity')
    slug = 'enikshay_worker_activity_report'
    num_avg_intervals = 4
    ajax_pagination = True
    is_cacheable = False
    fix_left_col = False

    @property
    def fields(self):
        return DatespanFilter, EnikshayLocationFilter

    @property
    def view_by_groups(self):
        return False

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("User")),
            DataTablesColumn(_("# Forms Submitted"), sortable=False),
            DataTablesColumn(_("Avg # Forms Submitted"), sortable=False),
            DataTablesColumn(_("Last Form Submission"), sortable=False)
        )

    @property
    def locations_id(self):
        return EnikshayLocationFilter.get_value(self.request, self.domain)

    @property
    def user_query(self):
        user_query = UserES().domain(self.domain).filter(mobile_users())
        locations_id = self.locations_id
        if locations_id:
            user_query = user_query.location(locations_id)
        elif not self.request.couch_user.has_permission(self.domain, 'access_all_locations'):
            # EnikshayLocationFilter.get_value should always return a
            # location_id for restricted users
            raise PermissionDenied()
        return user_query

    @property
    @memoized
    def users(self):
        return get_simplified_users(
            self.user_query
                .start(self.pagination.start)
                .size(self.pagination.count)
                .sort('username', desc=self.pagination.desc)
        )

    @property
    def user_ids(self):
        return [u['user_id'] for u in self.users]

    @property
    def rows(self):
        rows = []
        submissions_by_user = get_submission_counts_by_user(self.domain, self.datespan, self.user_ids)
        avg_submissions_by_user = get_submission_counts_by_user(self.domain, self.avg_datespan, self.user_ids)
        last_form_by_user = self.es_last_submissions()

        for user in self.users:
            rows.append([
                user['username_in_report'],
                submissions_by_user.get(user['user_id'], 0),
                int(avg_submissions_by_user.get(user["user_id"], 0)) / float(self.num_avg_intervals),
                last_form_by_user.get(user["user_id"]) or _(self.NO_FORMS_TEXT),
            ])
        return rows

    @property
    def shared_pagination_GET_params(self):
        return [
            dict(name='startdate', value=self.datespan.startdate_display),
            dict(name='enddate', value=self.datespan.enddate_display),
            dict(name='locations_id', value=self.request.GET.getlist('locations_id')),
        ]

    @property
    def total_records(self):
        return self.user_query.count()
