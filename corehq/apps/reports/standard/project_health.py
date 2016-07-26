from collections import namedtuple
import datetime
from django.utils.translation import ugettext_lazy
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.domain.models import Domain
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.style.decorators import use_nvd3
from corehq.apps.users.util import raw_username
from corehq.toggles import PROJECT_HEALTH_DASHBOARD
from dimagi.ext import jsonobject
from dimagi.utils.dates import add_months
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.es.groups import GroupES
from corehq.apps.es.users import UserES
from itertools import chain
from corehq.apps.locations.models import SQLLocation


def get_performance_threshold(domain_name):
    return Domain.get_by_name(domain_name).internal.performance_threshold or 15


class UserActivityStub(namedtuple('UserStub', ['user_id', 'username', 'num_forms_submitted',
                                               'is_performing', 'previous_stub', 'next_stub'])):

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

    @property
    def num_forms_submitted_next_month(self):
        return self.next_stub.num_forms_submitted if self.next_stub else 0

    @property
    def delta_forms_next_month(self):
        return self.num_forms_submitted_next_month - self.num_forms_submitted


class MonthlyMALTRows(jsonobject.JsonObject):
    month = jsonobject.DateProperty()
    domain = jsonobject.StringProperty()

    def __init__(self, domain, month, performance_threshold, not_deleted_active_users, users, has_filter):
        self._rows = MALTRow.objects.filter(
            domain_name=domain,
            month=month,
            user_type__in=['CommCareUser', 'CommCareUser-Deleted'],
            user_id__in=not_deleted_active_users,
        ).distinct('user_id')

        if has_filter:
            self._rows = self._rows.filter(user_id__in=users).distinct('user_id')

        self._threshold = performance_threshold

        super(MonthlyMALTRows, self).__init__(
            domain=domain,
            month=month,
        )

    def get_num_high_performing_users(self):
        return self._rows.filter(num_of_forms__gte=self._threshold).count()

    def get_num_active_users(self):
        return self._rows.filter(num_of_forms__gt=0).count()

    def get_num_low_performing_users(self):
        return self.get_num_active_users() - self.get_num_high_performing_users()

    def generate_user_stubs(self):
        return {
            row.user_id: UserActivityStub(
                user_id=row.user_id,
                username=raw_username(row.username),
                num_forms_submitted=row.num_of_forms,
                is_performing=row.num_of_forms >= self._threshold,
                previous_stub=None,
                next_stub=None,
            ) for row in self._rows
        }


class MonthlyPerformanceSummary(jsonobject.JsonObject):
    month = jsonobject.DateProperty()
    domain = jsonobject.StringProperty()
    active = jsonobject.IntegerProperty()
    performing = jsonobject.IntegerProperty()

    def __init__(self, domain, month, monthly_malt_rows, previous_summary=None):
        self._previous_summary = previous_summary
        self._next_summary = None
        self._monthly_malt_rows = monthly_malt_rows

        num_high_performers = self._monthly_malt_rows.get_num_high_performing_users()
        num_low_performers = self._monthly_malt_rows.get_num_low_performing_users()
        num_active_users = self._monthly_malt_rows.get_num_active_users()
        if previous_summary:
            delta_high_performers = num_high_performers - previous_summary.performing
            delta_low_performers = num_low_performers - previous_summary.low_performing
        else:
            delta_high_performers = 0
            delta_low_performers = 0

        super(MonthlyPerformanceSummary, self).__init__(
            month=month,
            domain=domain,
            active=num_active_users,
            inactive=0,
            total_users_by_month=0,
            percent_active=0,
            performing=num_high_performers,
            low_performing=num_low_performers,
            delta_high_performers=delta_high_performers,
            delta_low_performers=delta_low_performers,
        )

    def set_next_month_summary(self, next_month_summary):
        self._next_summary = next_month_summary

    def set_num_inactive_users(self, num_inactive_users):
        self.inactive = num_inactive_users

    def set_percent_active(self):
        self.total_users_by_month = self.number_of_inactive_users + self.number_of_active_users
        if self.total_users_by_month:
            self.percent_active = float(self.number_of_active_users) / float(self.total_users_by_month)
        else:
            self.percent_active = 0

    @property
    def number_of_performing_users(self):
        return self.performing

    @property
    def number_of_low_performing_users(self):
        return self.active - self.performing

    @property
    def number_of_active_users(self):
        return self.active

    @property
    def number_of_inactive_users(self):
        return self.inactive

    @property
    def previous_month(self):
        prev_year, prev_month = add_months(self.month.year, self.month.month, -1)
        return datetime.datetime(prev_year, prev_month, 1)

    @property
    def delta_high_performing(self):
        if self._previous_summary:
            return self.number_of_performing_users - self._previous_summary.number_of_performing_users
        else:
            return self.number_of_performing_users

    @property
    def delta_high_performing_pct(self):
        if (self.delta_high_performing and self._previous_summary and
           self._previous_summary.number_of_performing_users):
            return float(self.delta_high_performing /
                         float(self._previous_summary.number_of_performing_users)) * 100.

    @property
    def delta_low_performing(self):
        if self._previous_summary:
            return self.number_of_low_performing_users - self._previous_summary.number_of_low_performing_users
        else:
            return self.number_of_low_performing_users

    @property
    def delta_low_performing_pct(self):
        if self.delta_low_performing and self._previous_summary \
                and self._previous_summary.number_of_low_performing_users:
            return float(self.delta_low_performing /
                         float(self._previous_summary.number_of_low_performing_users)) * 100.

    @property
    def delta_active(self):
        return self.active - self._previous_summary.active if self._previous_summary else self.active

    @property
    def delta_active_pct(self):
        if self.delta_active and self._previous_summary and self._previous_summary.active:
            return float(self.delta_active / float(self._previous_summary.active)) * 100.

    @property
    def delta_inactive(self):
        return self.inactive - self._previous_summary.inactive if self._previous_summary else self.inactive

    @property
    def delta_inactive_pct(self):
        if self.delta_inactive and self._previous_summary:
            if self._previous_summary.number_of_inactive_users == 0:
                return self.delta_inactive * 100.
            return float(self.delta_inactive / float(self._previous_summary.number_of_inactive_users)) * 100.

    def _get_all_user_stubs(self):
        return self._monthly_malt_rows.generate_user_stubs()

    @memoized
    def get_all_user_stubs_with_extra_data(self):
        if self._previous_summary:
            previous_stubs = self._previous_summary._get_all_user_stubs()
            next_stubs = self._next_summary._get_all_user_stubs() if self._next_summary else {}
            user_stubs = self._get_all_user_stubs()
            ret = []
            for user_stub in user_stubs.values():
                ret.append(UserActivityStub(
                    user_id=user_stub.user_id,
                    username=user_stub.username,
                    num_forms_submitted=user_stub.num_forms_submitted,
                    is_performing=user_stub.is_performing,
                    previous_stub=previous_stubs.get(user_stub.user_id),
                    next_stub=next_stubs.get(user_stub.user_id),
                ))
            for missing_user_id in set(previous_stubs.keys()) - set(user_stubs.keys()):
                previous_stub = previous_stubs[missing_user_id]
                ret.append(UserActivityStub(
                    user_id=previous_stub.user_id,
                    username=previous_stub.username,
                    num_forms_submitted=0,
                    is_performing=False,
                    previous_stub=previous_stub,
                    next_stub=next_stubs.get(missing_user_id),
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
                self.get_all_user_stubs_with_extra_data()
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
                self.get_all_user_stubs_with_extra_data()
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
                self.get_all_user_stubs_with_extra_data()
            )
            return sorted(dropouts, key=lambda stub: -stub.delta_forms)


def build_worksheet(title, headers, rows):
    worksheet = []
    worksheet.append(headers)
    worksheet.extend(rows)
    return [
        title,
        worksheet
    ]


class ProjectHealthDashboard(ProjectReport):
    slug = 'project_health'
    name = ugettext_lazy("Project Performance")
    report_template_path = "reports/project_health/project_health_dashboard.html"

    fields = [
        'corehq.apps.reports.filters.location.LocationGroupFilter',
        'corehq.apps.reports.filters.dates.HiddenLastMonthDateFilter',
    ]

    exportable = True
    emailable = True
    asynchronous = False

    @property
    @memoized
    def template_report(self):
        if self.is_rendered_as_email:
            self.report_template_path = "reports/project_health/project_health_email.html"
        return super(ProjectHealthDashboard, self).template_report

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return PROJECT_HEALTH_DASHBOARD.enabled(domain)

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(ProjectHealthDashboard, self).decorator_dispatcher(request, *args, **kwargs)

    def get_group_location_ids(self):
        params = filter(None, self.request.GET.getlist('grouplocationfilter'))
        return params

    def parse_params(self, param_ids):
        locationids_param = []
        groupids_param = []

        if param_ids:
            param_ids = param_ids[0].split(',')
            for id in param_ids:
                if id.startswith("g__"):
                    groupids_param.append(id[3:])
                elif id.startswith("l__"):
                    loc = SQLLocation.by_location_id(id[3:])
                    if loc.get_descendants():
                        locationids_param.extend(loc.get_descendants().location_ids())
                    locationids_param.append(id[3:])

        return locationids_param, groupids_param

    def get_users_by_location_filter(self, location_ids):
        return UserES().domain(self.domain).location(location_ids).values_list('_id', flat=True)

    def get_users_by_group_filter(self, group_ids):
        return GroupES().domain(self.domain).group_ids(group_ids).values_list("users", flat=True)

    def get_unique_users(self, users_loc, users_group):
        if users_loc and users_group:
            return set(chain(*users_group)).union(users_loc)
        elif users_loc:
            return set(users_loc)
        else:
            return set(chain(*users_group))

    def get_users_by_filter(self):
        locationids_param, groupids_param = self.parse_params(self.get_group_location_ids())

        users_list_by_location = self.get_users_by_location_filter(locationids_param)
        users_list_by_group = self.get_users_by_group_filter(groupids_param)

        users_set = self.get_unique_users(users_list_by_location, users_list_by_group)
        return users_set

    def create_monthly_summary(self, month_as_date, threshold, filtered_users, last_month_summary):
        monthly_malt_rows = MonthlyMALTRows(
            domain=self.domain,
            month=month_as_date,
            performance_threshold=threshold,
            users=filtered_users,
            has_filter=bool(self.get_group_location_ids()),
            not_deleted_active_users=UserES().domain(self.domain).values_list("_id", flat=True),
        )
        this_month_summary = MonthlyPerformanceSummary(
            domain=self.domain,
            month=month_as_date,
            previous_summary=last_month_summary,
            monthly_malt_rows=monthly_malt_rows,
        )
        if last_month_summary is not None:
            last_month_summary.set_next_month_summary(this_month_summary)
            this_month_summary.set_num_inactive_users(len(this_month_summary.get_dropouts()))
        this_month_summary.set_percent_active()
        return this_month_summary

    def previous_six_months(self):
        now = datetime.datetime.utcnow()
        six_month_summary = []
        last_month_summary = None
        performance_threshold = get_performance_threshold(self.domain)
        filtered_users = self.get_users_by_filter()

        for i in range(-6, 1):
            year, month = add_months(now.year, now.month, i)
            month_as_date = datetime.date(year, month, 1)
            this_month_summary = self.create_monthly_summary(month_as_date, performance_threshold,
                                                             filtered_users, last_month_summary)
            six_month_summary.append(this_month_summary)
            last_month_summary = this_month_summary
        return six_month_summary[1:]

    def export_summary(self, six_months):
        return build_worksheet(title="Six Month Performance Summary",
                               headers=['month', 'num_high_performing_users', 'num_low_performing_users',
                                        'total_active', 'total_inactive', 'total_num_users'],
                               rows=[[monthly_summary.month.isoformat(),
                                      monthly_summary.number_of_performing_users,
                                      monthly_summary.number_of_low_performing_users, monthly_summary.active,
                                      monthly_summary.inactive, monthly_summary.total_users_by_month]
                                     for monthly_summary in six_months])

    @property
    def export_table(self):
        six_months_reports = self.previous_six_months()
        last_month = six_months_reports[-2]

        header = ['user_id', 'username', 'last_month_forms', 'delta_last_month',
                  'this_month_forms', 'delta_this_month', 'is_performing']

        def extract_user_stat(user_list):
            return [[user.user_id, user.username, user.num_forms_submitted, user.delta_forms,
                    user.num_forms_submitted_next_month, user.delta_forms_next_month,
                    user.is_performing] for user in user_list]

        return [
            self.export_summary(six_months_reports),
            build_worksheet(title="Inactive Users", headers=header,
                            rows=extract_user_stat(last_month.get_dropouts())),
            build_worksheet(title="Low Performing Users", headers=header,
                            rows=extract_user_stat(last_month.get_unhealthy_users())),
            build_worksheet(title="New Performing Users", headers=header,
                            rows=extract_user_stat(last_month.get_newly_performing())),
        ]

    @property
    def template_context(self):
        six_months_reports = self.previous_six_months()
        performance_threshold = get_performance_threshold(self.domain)
        return {
            'six_months_reports': six_months_reports,
            'this_month': six_months_reports[-1],
            'last_month': six_months_reports[-2],
            'threshold': performance_threshold,
            'domain': self.domain,
        }
