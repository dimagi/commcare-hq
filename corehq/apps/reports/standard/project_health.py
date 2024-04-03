import datetime
from collections import namedtuple
from itertools import chain

from django.db.models import Sum
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from memoized import memoized

from dimagi.ext import jsonobject
from dimagi.utils.dates import add_months

from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.domain.models import Domain
from corehq.apps.es.groups import GroupES
from corehq.apps.es.users import UserES
from corehq.apps.hqwebapp.decorators import use_nvd3
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.users.util import raw_username


def get_performance_threshold(domain_name):
    return Domain.get_by_name(domain_name).internal.performance_threshold or 15


UserStub = namedtuple('UserStub', [
    'user_id',
    'username',
    'num_forms_submitted',
    'is_performing',
    'previous_stub',
    'next_stub',
])


class UserActivityStub(UserStub):

    @property
    def is_active(self):
        return self.num_forms_submitted > 0

    @property
    def is_newly_performing(self):
        return self.is_performing and (
            self.previous_stub is None
            or not self.previous_stub.is_performing
        )

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


class MonthlyPerformanceSummary(jsonobject.JsonObject):
    month = jsonobject.DateProperty()
    domain = jsonobject.StringProperty()
    performance_threshold = jsonobject.IntegerProperty()
    active = jsonobject.IntegerProperty()
    performing = jsonobject.IntegerProperty()

    def __init__(
        self,
        domain,
        month,
        selected_users,
        active_not_deleted_users,
        performance_threshold,
        previous_summary=None,
        delta_high_performers=0,
        delta_low_performers=0,
    ):
        self._previous_summary = previous_summary
        self._next_summary = None
        self._is_final = None

        base_queryset = MALTRow.objects.filter(
            domain_name=domain,
            month=month,
            user_type__in=['CommCareUser', 'CommCareUser-Deleted'],
            user_id__in=active_not_deleted_users,
        )
        if selected_users:
            base_queryset = base_queryset.filter(
                user_id__in=selected_users,
            )

        self._user_stat_from_malt = (base_queryset
                                     .values('user_id', 'username')
                                     .annotate(total_num_forms=Sum('num_of_forms')))

        num_performing_users = (self._user_stat_from_malt
                                .filter(total_num_forms__gte=performance_threshold)
                                .count())

        num_active_users = self._user_stat_from_malt.count()
        num_low_performing_user = num_active_users - num_performing_users

        if self._previous_summary:
            delta_high_performers = num_performing_users - self._previous_summary.number_of_performing_users
            delta_low_performers = num_low_performing_user - self._previous_summary.number_of_low_performing_users

        super(MonthlyPerformanceSummary, self).__init__(
            month=month,
            domain=domain,
            performance_threshold=performance_threshold,
            active=num_active_users,
            total_users_by_month=0,
            percent_active=0,
            performing=num_performing_users,
            delta_high_performers=delta_high_performers,
            delta_low_performers=delta_low_performers,
        )

    def set_next_month_summary(self, next_month_summary):
        self._next_summary = next_month_summary

    def set_percent_active(self):
        self.total_users_by_month = self.inactive + self.number_of_active_users
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
    @memoized
    def inactive(self):
        dropouts = self.get_dropouts()
        return len(dropouts) if dropouts else 0

    @property
    def previous_month(self):
        prev_year, prev_month = add_months(self.month.year, self.month.month, -1)
        return datetime.datetime(prev_year, prev_month, 1)

    @property
    def delta_inactive(self):
        return self.inactive - self._previous_summary.inactive if self._previous_summary else self.inactive

    @property
    def delta_inactive_pct(self):
        if self.delta_inactive and self._previous_summary:
            if self._previous_summary.inactive == 0:
                return self.delta_inactive * 100.
            return self.delta_inactive / float(self._previous_summary.inactive) * 100

    def _get_all_user_stubs(self):
        return {
            row['user_id']: UserActivityStub(
                user_id=row['user_id'],
                username=raw_username(row['username']),
                num_forms_submitted=row['total_num_forms'],
                is_performing=row['total_num_forms'] >= self.performance_threshold,
                previous_stub=None,
                next_stub=None,
            ) for row in self._user_stat_from_malt
        }

    def finalize(self):
        """
        Before a summary is "finalized" certain fields can't be accessed.
        """
        self._is_final = True

    @memoized
    def _get_all_user_stubs_with_extra_data(self):
        if not self._is_final:
            # intentionally fail-hard with developer-facing error
            raise Exception("User stubs accessed before finalized. "
                            "Please call finalize() before calling this method.")
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
            unhealthy_users = [stub for stub in self._get_all_user_stubs_with_extra_data()
                               if stub.is_active and not stub.is_performing]
            return sorted(unhealthy_users, key=lambda stub: stub.delta_forms)

    def get_dropouts(self):
        """
        Get a list of dropout users - defined as those who were active last month
        but are not active this month
        """
        if self._previous_summary:
            dropouts = [stub for stub in self._get_all_user_stubs_with_extra_data() if not stub.is_active]
            return sorted(dropouts, key=lambda stub: stub.delta_forms)

    def get_newly_performing(self):
        """
        Get a list of "newly performing" users - defined as those who are "performing" this month
        after not performing last month.
        """
        if self._previous_summary:
            new_performers = [stub for stub in self._get_all_user_stubs_with_extra_data()
                              if stub.is_newly_performing]
            return sorted(new_performers, key=lambda stub: -stub.delta_forms)


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
    name = gettext_lazy("Project Performance")
    report_template_path = "reports/async/bootstrap3/project_health_dashboard.html"
    description = gettext_lazy("A summary of the overall health of your project"
                               " based on how your users are doing over time.")

    fields = [
        'corehq.apps.reports.filters.location.LocationGroupFilter',
        'corehq.apps.reports.filters.dates.HiddenLastMonthDateFilter',
    ]

    exportable = True
    emailable = True

    @property
    @memoized
    def template_report(self):
        if self.is_rendered_as_email:
            self.report_template_path = "reports/project_health/project_health_email.html"
        return super(ProjectHealthDashboard, self).template_report

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(ProjectHealthDashboard, self).decorator_dispatcher(request, *args, **kwargs)

    def get_number_of_months(self):
        try:
            return int(self.request.GET.get('months', 6))
        except ValueError:
            return 6

    def get_group_location_ids(self):
        params = [_f for _f in self.request.GET.getlist('grouplocationfilter') if _f]
        return params

    def parse_group_location_params(self, param_ids):
        locationids_param = []
        groupids_param = []

        if param_ids:
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
        locationids_param, groupids_param = self.parse_group_location_params(self.get_group_location_ids())
        users_list_by_location = self.get_users_by_location_filter(locationids_param)
        users_list_by_group = self.get_users_by_group_filter(groupids_param)

        users_set = self.get_unique_users(users_list_by_location, users_list_by_group)
        return users_set

    def previous_months_summary(self, months=6):
        now = datetime.datetime.utcnow()
        six_month_summary = []
        last_month_summary = None
        performance_threshold = get_performance_threshold(self.domain)
        filtered_users = self.get_users_by_filter()
        active_not_deleted_users = UserES().domain(self.domain).values_list("_id", flat=True)
        for i in range(-months, 1):
            year, month = add_months(now.year, now.month, i)
            month_as_date = datetime.date(year, month, 1)
            this_month_summary = MonthlyPerformanceSummary(
                domain=self.domain,
                performance_threshold=performance_threshold,
                month=month_as_date,
                previous_summary=last_month_summary,
                selected_users=filtered_users,
                active_not_deleted_users=active_not_deleted_users,
            )
            six_month_summary.append(this_month_summary)
            if last_month_summary is not None:
                last_month_summary.set_next_month_summary(this_month_summary)
            last_month_summary = this_month_summary

        # these steps have to be done in a second outer loop so that 'next month summary' is available
        # whenever it is needed
        for summary in six_month_summary:
            summary.finalize()
            summary.set_percent_active()

        return six_month_summary[1:]

    def export_summary(self, six_months):
        return build_worksheet(
            title="Six Month Performance Summary",
            headers=[
                'month',
                'num_high_performing_users',
                'num_low_performing_users',
                'total_active',
                'total_inactive',
                'total_num_users',
            ],
            rows=[[
                monthly_summary.month.isoformat(),
                monthly_summary.number_of_performing_users,
                monthly_summary.number_of_low_performing_users,
                monthly_summary.active,
                monthly_summary.inactive,
                monthly_summary.total_users_by_month,
            ] for monthly_summary in six_months]
        )

    @property
    def export_table(self):
        previous_months_reports = self.previous_months_summary(self.get_number_of_months())
        last_month = previous_months_reports[-2]

        header = [
            'user_id',
            'username',
            'last_month_forms',
            'delta_last_month',
            'this_month_forms',
            'delta_this_month',
            'is_performing',
        ]

        def extract_user_stat(user_list):
            return [[
                user.user_id,
                user.username,
                user.num_forms_submitted,
                user.delta_forms,
                user.num_forms_submitted_next_month,
                user.delta_forms_next_month,
                user.is_performing,
            ] for user in user_list]

        return [
            self.export_summary(previous_months_reports),
            build_worksheet(
                title="Inactive Users",
                headers=header,
                rows=extract_user_stat(last_month.get_dropouts()),
            ),
            build_worksheet(
                title=_("Low Performing Users"),
                headers=header,
                rows=extract_user_stat(last_month.get_unhealthy_users()),
            ),
            build_worksheet(
                title=_("New Performing Users"),
                headers=header,
                rows=extract_user_stat(last_month.get_newly_performing()),
            ),
        ]

    @property
    def template_context(self):
        context = super().template_context
        performance_threshold = get_performance_threshold(self.domain)
        prior_months_reports = self.previous_months_summary(self.get_number_of_months())
        six_months_reports = []

        for report in prior_months_reports:
            r = report.to_json()
            # inactive is a calculated property and this is transformed to json in
            # the template so we need to precompute here
            r.update({'inactive': report.inactive})
            six_months_reports.append(r)

        context.update({
            'six_months_reports': six_months_reports,
            'this_month': prior_months_reports[-1],
            'last_month': prior_months_reports[-2],
            'threshold': performance_threshold,
            'domain': self.domain,
        })
        return context
