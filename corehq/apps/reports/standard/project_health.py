from collections import namedtuple
import datetime
from django.utils.translation import ugettext_noop
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
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


class UserActivityStub(namedtuple('UserStub', ['user_id', 'username', 'num_forms_submitted', 'delta_forms',
                                               'num_forms_submitted_next_month', 'delta_forms_next_month',
                                               'is_performing', 'previous_stub', 'next_stub'])):

    @property
    def is_active(self):
        return self.num_forms_submitted > 0

    @property
    def is_newly_performing(self):
        return self.is_performing and (self.previous_stub is None or not self.previous_stub.is_performing)


class MonthlyPerformanceSummary(jsonobject.JsonObject):
    month = jsonobject.DateProperty()
    domain = jsonobject.StringProperty()
    performance_threshold = jsonobject.IntegerProperty()
    active = jsonobject.IntegerProperty()
    performing = jsonobject.IntegerProperty()

    def __init__(self, domain, month, users, has_filter, performance_threshold, previous_summary=None):
        self._previous_summary = previous_summary
        self._next_summary = None
        base_queryset = MALTRow.objects.filter(
            domain_name=domain,
            month=month,
            user_type__in=['CommCareUser', 'CommCareUser-Deleted'],
        )
        if has_filter:
            base_queryset = base_queryset.filter(
                user_id__in=users,
            )
        self._distinct_user_ids = base_queryset.distinct('user_id')

        num_performing_user = (base_queryset
                               .filter(num_of_forms__gte=performance_threshold)
                               .distinct('user_id')
                               .count())

        super(MonthlyPerformanceSummary, self).__init__(
            month=month,
            domain=domain,
            performance_threshold=performance_threshold,
            active=self._distinct_user_ids.count(),
            inactive=0,
            total_users_by_month=0,
            percent_active=0,
            performing=num_performing_user,
        )

    def set_next_month_summary(self, next_month_summary):
        self._next_summary = next_month_summary

    def set_num_inactive_users(self, num_inactive_users):
        self.inactive = num_inactive_users

    def set_percent_active(self):
        self.total_users_by_month = self.number_of_inactive_users + self.number_of_active_users
        self.percent_active = float(self.number_of_active_users) / float(self.total_users_by_month)

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
    def delta_performing(self):
        if self._previous_summary:
            return self.number_of_performing_users - self._previous_summary.number_of_performing_users
        else:
            return self.number_of_performing_users

    @property
    def delta_performing_pct(self):
        if self.delta_performing and self._previous_summary and self._previous_summary.number_of_performing_users:
            return float(self.delta_performing / float(self._previous_summary.number_of_performing_users)) * 100.

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

    @memoized
    def get_all_user_stubs(self):
        return {
            row.user_id: UserActivityStub(
                user_id=row.user_id,
                username=raw_username(row.username),
                num_forms_submitted=row.num_of_forms,
                delta_forms=0,
                num_forms_submitted_next_month=0,
                delta_forms_next_month=0,
                is_performing=row.num_of_forms >= self.performance_threshold,
                previous_stub=None,
                next_stub=None,
            ) for row in self._distinct_user_ids
        }

    def calc_delta_forms_this_month(self, this_month_forms, previous_stub):
        if previous_stub is None:
            previous_month_forms = 0
        else:
            previous_month_forms = previous_stub.num_forms_submitted
        return this_month_forms - previous_month_forms

    def calc_delta_forms_next_month(self, this_month_forms, next_stub):
        if next_stub is None:
            next_month_forms = 0
        else:
            next_month_forms = next_stub.num_forms_submitted
        return next_month_forms - this_month_forms

    @memoized
    def get_all_user_stubs_with_extra_data(self):
        if self._previous_summary:
            previous_stubs = self._previous_summary.get_all_user_stubs()
            next_stubs = self._next_summary.get_all_user_stubs() if self._next_summary else {}
            user_stubs = self.get_all_user_stubs()
            ret = []
            for user_stub in user_stubs.values():
                prev_stub = previous_stubs.get(user_stub.user_id)
                next_stub = next_stubs.get(user_stub.user_id)
                num_forms_submitted_next_month = 0
                if next_stub:
                    num_forms_submitted_next_month = next_stub.num_forms_submitted
                user_activity = UserActivityStub(
                    user_id=user_stub.user_id,
                    username=user_stub.username,
                    num_forms_submitted=user_stub.num_forms_submitted,
                    num_forms_submitted_next_month=num_forms_submitted_next_month,
                    delta_forms=self.calc_delta_forms_this_month(user_stub.num_forms_submitted, prev_stub),
                    delta_forms_next_month=self.calc_delta_forms_next_month(user_stub.num_forms_submitted,
                                                                            next_stub),
                    is_performing=user_stub.is_performing,
                    previous_stub=prev_stub,
                    next_stub=next_stub,
                )
                ret.append(user_activity)
            for missing_user_id in set(previous_stubs.keys()) - set(user_stubs.keys()):
                prev_stub = previous_stubs[missing_user_id]
                next_stub = next_stubs.get(missing_user_id)
                num_forms_submitted_next_month = 0
                if next_stub:
                    num_forms_submitted_next_month = next_stub.num_forms_submitted
                ret.append(UserActivityStub(
                    user_id=prev_stub.user_id,
                    username=prev_stub.username,
                    num_forms_submitted=0,
                    num_forms_submitted_next_month=num_forms_submitted_next_month,
                    delta_forms=self.calc_delta_forms_this_month(0, prev_stub),
                    delta_forms_next_month=self.calc_delta_forms_this_month(0, next_stub),
                    is_performing=False,
                    previous_stub=prev_stub,
                    next_stub=next_stub,
                ))
            return ret

    def get_unhealthy_users(self):
        """
        Get a list of unhealthy users - defined as those who were "performing" last month
        but are not this month (though are still active).
        """
        if self._previous_summary:
            unhealthy_users = filter(
                lambda stub: stub.is_active and not stub.is_performing and not
                CommCareUser.get(stub.user_id).is_deleted(),
                self.get_all_user_stubs_with_extra_data()
            )
            sorted_unhealthy_users = sorted(unhealthy_users, key=lambda stub: stub.delta_forms)
            unhealthy_users = [user._asdict() for user in sorted_unhealthy_users]
            return unhealthy_users

    def get_dropouts(self):
        """
        Get a list of dropout users - defined as those who were active last month
        but are not active this month
        """
        if self._previous_summary:
            dropouts = filter(
                lambda stub: not stub.is_active and not
                CommCareUser.get(stub.user_id).is_deleted(),
                self.get_all_user_stubs_with_extra_data()
            )
            sorted_dropouts = sorted(dropouts, key=lambda stub: stub.delta_forms)
            dropouts = [user._asdict() for user in sorted_dropouts]
            return dropouts

    def get_newly_performing(self):
        """
        Get a list of "newly performing" users - defined as those who are "performing" this month
        after not performing last month.
        """
        if self._previous_summary:
            high_performers = filter(
                lambda stub: stub.is_newly_performing and not
                CommCareUser.get(stub.user_id).is_deleted(),
                self.get_all_user_stubs_with_extra_data()
            )
            sorted_high_performers = sorted(high_performers, key=lambda stub: -stub.delta_forms)
            high_performers = [user._asdict() for user in sorted_high_performers]
            return high_performers


class ProjectHealthDashboard(ProjectReport):
    slug = 'project_health'
    name = ugettext_noop("Project Performance")
    base_template = "reports/project_health/project_health_dashboard.html"

    fields = [
        'corehq.apps.reports.filters.location.LocationGroupFilter',
    ]

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

    def previous_six_months(self):
        now = datetime.datetime.utcnow()
        six_month_summary = []
        last_month_summary = None
        performance_threshold = get_performance_threshold(self.domain)
        filtered_users = self.get_users_by_filter()
        for i in range(-6, 1):
            year, month = add_months(now.year, now.month, i)
            month_as_date = datetime.date(year, month, 1)
            this_month_summary = MonthlyPerformanceSummary(
                domain=self.domain,
                performance_threshold=performance_threshold,
                month=month_as_date,
                previous_summary=last_month_summary,
                users=filtered_users,
                has_filter=bool(self.get_group_location_ids()),
            )
            six_month_summary.append(this_month_summary)
            if last_month_summary is not None:
                last_month_summary.set_next_month_summary(this_month_summary)
                this_month_summary.set_num_inactive_users(len(this_month_summary.get_dropouts()))
            this_month_summary.set_percent_active()
            last_month_summary = this_month_summary
        return six_month_summary[1:]

    @property
    def template_context(self):
        six_months_reports = self.previous_six_months()
        performance_threshold = get_performance_threshold(self.domain)
        return {
            'six_months_reports': six_months_reports,
            'this_month': six_months_reports[-1],
            'last_month': six_months_reports[-2],
            'threshold': performance_threshold,
        }
