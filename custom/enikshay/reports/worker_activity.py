from corehq.apps.es import UserES
from corehq.apps.es.users import mobile_users
from corehq.apps.reports.analytics.esaccessors import get_submission_counts_by_user
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.standard.monitoring import WorkerActivityReport
from corehq.apps.reports.util import get_simplified_users, numcell
from custom.enikshay.reports.filters import EnikshayLocationFilter

from django.utils.translation import ugettext as _


class EnikshayWorkerActivityReport(WorkerActivityReport, CustomProjectReport):
    slug = 'enikshay_worker_activity_report'
    num_avg_intervals = 4

    @property
    def fields(self):
        return DatespanFilter, EnikshayLocationFilter

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("User")),
            DataTablesColumn(_("# Forms Submitted"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Avg # Forms Submitted"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Last Form Submission"))
        )

    @property
    def users(self):
        location_ids = EnikshayLocationFilter.get_value(self.request, self.domain)
        user_query = UserES().domain(self.domain).filter(mobile_users())
        if location_ids:
            user_query = user_query.location(location_ids)
        return get_simplified_users(user_query)

    @property
    def rows(self):
        rows = []
        submissions_by_user = get_submission_counts_by_user(self.domain, self.datespan)
        avg_submissions_by_user = get_submission_counts_by_user(self.domain, self.avg_datespan)
        last_form_by_user = self.es_last_submissions()

        for user in self.users:
            rows.append([
                user['username_in_report'],
                submissions_by_user.get(user['user_id'], 0),
                numcell(
                    int(avg_submissions_by_user.get(user["user_id"], 0)) / float(self.num_avg_intervals)
                ),
                last_form_by_user.get(user["user_id"]) or _(self.NO_FORMS_TEXT),
            ])
        return rows
