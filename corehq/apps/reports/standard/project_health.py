from collections import namedtuple
import datetime
from django.db.models import F
from django.utils.translation import ugettext_noop
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.style.decorators import use_nvd3
from corehq.apps.users.util import raw_username
from corehq.toggles import PROJECT_HEALTH_DASHBOARD
from dimagi.ext import jsonobject
from dimagi.utils.dates import add_months
from dimagi.utils.decorators.memoized import memoized


class UserActivityStub(namedtuple('UserStub', ['user_id', 'username', 'num_forms_submitted',
                                               'is_performing', 'previous_stub'])):

    @property
    def is_active(self):
        return self.num_forms_submitted > 0

    @property
    def is_newly_performing(self):
        return self.is_performing and (self.previous_stub is None or not self.previous_stub.is_performing)

    @property
    def delta_forms(self):
        previous_forms = 0 if self.previous_stub is None else self.previous_stub.num_forms_submitted
        return self.num_forms_submitted - previous_forms


class MonthlyPerformanceSummary(jsonobject.JsonObject):
    month = jsonobject.DateProperty()
    domain = jsonobject.StringProperty()
    active = jsonobject.IntegerProperty()
    performing = jsonobject.IntegerProperty()

    def __init__(self, domain, month, previous_summary=None):
        self._previous_summary = previous_summary
        self._base_queryset = MALTRow.objects.filter(
            domain_name=domain,
            month=month,
        )
        self._performing_queryset = self._base_queryset.filter(
            num_of_forms__gte=F('threshold')
        )
        super(MonthlyPerformanceSummary, self).__init__(
            month=month,
            domain=domain,
            active=self._base_queryset.distinct('user_id').count(),
            performing=self._performing_queryset.distinct('user_id').count(),
        )

    @property
    def delta_performing(self):
        return self.performing - self._previous_summary.performing if self._previous_summary else self.performing

    @property
    def delta_performing_pct(self):
        if self.delta_performing and self._previous_summary and self._previous_summary.performing:
            return float(self.delta_performing / float(self._previous_summary.performing)) * 100.

    @property
    def delta_active(self):
        return self.active - self._previous_summary.active if self._previous_summary else self.active

    @property
    def delta_active_pct(self):
        if self.delta_active and self._previous_summary and self._previous_summary.active:
            return float(self.delta_active / float(self._previous_summary.active)) * 100.

    @memoized
    def get_all_user_stubs(self):
        return {
            row.user_id: UserActivityStub(
                user_id=row.user_id,
                username=raw_username(row.username),
                num_forms_submitted=row.num_of_forms,
                is_performing=row.num_of_forms > row.threshold,
                previous_stub=None,
            ) for row in self._base_queryset.distinct('user_id')
        }

    @memoized
    def get_all_user_stubs_with_previous_data(self):
        if self._previous_summary:
            previous_stubs = self._previous_summary.get_all_user_stubs()
            user_stubs = self.get_all_user_stubs()
            ret = []
            for user_stub in user_stubs.values():
                ret.append(UserActivityStub(
                    user_id=user_stub.user_id,
                    username=user_stub.username,
                    num_forms_submitted=user_stub.num_forms_submitted,
                    is_performing=user_stub.is_performing,
                    previous_stub=previous_stubs.get(user_stub.user_id)
                ))
            for missing_user_id in set(previous_stubs.keys()) - set(user_stubs.keys()):
                previous_stub = previous_stubs[missing_user_id]
                ret.append(UserActivityStub(
                    user_id=previous_stub.user_id,
                    username=previous_stub.username,
                    num_forms_submitted=0,
                    is_performing=False,
                    previous_stub=previous_stub
                ))
            return ret

    def get_unhealthy_users(self):
        """
        Get a list of unhealthy users - defined as those who were "performing" last month
        but are not this month (though are still active).
        """
        if self._previous_summary:
            unhealthy_users = filter(
                lambda stub: stub.is_active and not stub.is_performing,
                self.get_all_user_stubs_with_previous_data()
            )
            return sorted(unhealthy_users, key=lambda stub: stub.delta_forms)

    def get_dropouts(self):
        """
        Get a list of dropout users - defined as those who were active last month
        but are not active this month
        """
        if self._previous_summary:
            dropouts = filter(
                lambda stub: not stub.is_active,
                self.get_all_user_stubs_with_previous_data()
            )
            return sorted(dropouts, key=lambda stub: stub.delta_forms)

    def get_newly_performing(self):
        """
        Get a list of "newly performing" users - defined as those who are "performing" this month
        after not performing last month.
        """
        if self._previous_summary:
            dropouts = filter(
                lambda stub: stub.is_newly_performing,
                self.get_all_user_stubs_with_previous_data()
            )
            return sorted(dropouts, key=lambda stub: -stub.delta_forms)


class ProjectHealthDashboard(ProjectReport):
    slug = 'project_health'
    name = ugettext_noop("Project Health")
    is_bootstrap3 = True
    base_template = "reports/project_health/project_health_dashboard.html"

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return PROJECT_HEALTH_DASHBOARD.enabled(domain)

    @use_nvd3
    def bootstrap3_dispatcher(self, request, *args, **kwargs):
        super(ProjectHealthDashboard, self).bootstrap3_dispatcher(request, *args, **kwargs)

    @property
    def template_context(self):
        now = datetime.datetime.utcnow()
        rows = []
        last_month_summary = None
        for i in range(-6, 0):
            year, month = add_months(now.year, now.month, i)
            month_as_date = datetime.date(year, month, 1)
            this_month_summary = MonthlyPerformanceSummary(
                domain=self.domain,
                month=month_as_date,
                previous_summary=last_month_summary,
            )
            rows.append(this_month_summary)
            last_month_summary = this_month_summary

        return {
            'rows': rows,
            'last_month': rows[-1]
        }
