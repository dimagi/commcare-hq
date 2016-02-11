from collections import namedtuple
import datetime
from django.db.models import F
from django.utils.translation import ugettext_noop
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.style.decorators import use_nvd3, use_bootstrap3
from corehq.apps.users.util import user_id_to_username, raw_username
from corehq.toggles import PROJECT_HEALTH_DASHBOARD
from dimagi.ext import jsonobject
from dimagi.utils.dates import add_months
from dimagi.utils.decorators.memoized import memoized


UserActivityStub = namedtuple('UserStub', ['user_id', 'username', 'num_forms_submitted'])


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
    def get_active_user_ids(self):
        return self._base_queryset.values_list('user_id', flat=True).distinct()

    @memoized
    def get_performing_user_ids(self):
        return self._performing_queryset.values_list('user_id', flat=True).distinct()

    def get_unhealthy_users(self):
        """
        Get a list of unhealthy users - defined as those who were "performing" last month
        but are not this month (though are still active).
        """
        if self._previous_summary:
            previously_performing = set(self._previous_summary.get_performing_user_ids())
            currently_performing = set(self.get_performing_user_ids())
            return [
                UserActivityStub(
                    user_id=row.user_id,
                    username=raw_username(row.username),
                    num_forms_submitted=row.num_of_forms,
                ) for row in self._base_queryset.filter(
                    user_id__in=previously_performing - currently_performing
                ).order_by('-num_of_forms')
            ]

    def get_dropouts(self):
        """
        Get a list of dropout users - defined as those who were active last month
        but are not active this month
        """
        if self._previous_summary:
            previously_active = set(self._previous_summary.get_active_user_ids())
            currently_active = set(self.get_active_user_ids())
            dropout_ids = previously_active - currently_active
            dropouts = [
                UserActivityStub(
                    user_id=user_id,
                    username=user_id_to_username(user_id),
                    num_forms_submitted=0,
                )
                for user_id in dropout_ids
            ]
            return sorted(dropouts, key=lambda userstub: userstub.username)

    def get_newly_performing(self):
        """
        Get a list of "newly performing" users - defined as those who are "performing" this month
        after not performing last month.
        """
        if self._previous_summary:
            previously_performing = set(self._previous_summary.get_performing_user_ids())
            currently_performing = set(self.get_performing_user_ids())
            return [
                UserActivityStub(
                    user_id=row.user_id,
                    username=raw_username(row.username),
                    num_forms_submitted=row.num_of_forms,
                ) for row in self._base_queryset.filter(
                    user_id__in=currently_performing - previously_performing
                ).order_by('-num_of_forms')
            ]


class ProjectHealthDashboard(ProjectReport):
    slug = 'project_health'
    name = ugettext_noop("Project Health")
    is_bootstrap3 = True
    base_template = "reports/project_health/project_health_dashboard.html"

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return PROJECT_HEALTH_DASHBOARD.enabled(domain)

    @use_bootstrap3
    @use_nvd3
    def set_bootstrap3_status(self, request, *args, **kwargs):
        pass

    @property
    def template_context(self):
        now = datetime.datetime.utcnow()
        rows = []
        last_month_summary = None
        for i in range(-3, 0):
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
