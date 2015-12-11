from operator import itemgetter

from sqlagg.filters import BETWEEN

from corehq.apps.groups.models import Group
from corehq.apps.reports import util
from corehq.apps.reports.standard import CommCareUserMemoizer
from corehq.apps.reports.util import format_datatables_data, make_ctable_table_name
from corehq.apps.userreports.sql import get_table_name
from corehq.sql_db.connections import UCR_ENGINE_ID
from custom.apps.cvsu.mixins import CVSUSqlDataMixin, FilterMixin, DateColumnMixin, combine_month_year, format_date, \
    combine_quarter_year, format_year
from custom.apps.cvsu.utils import dynamic_date_aggregation
from .filters import ALL_CVSU_GROUP
from dimagi.utils.decorators.memoized import memoized
from sqlagg import AliasColumn
from sqlagg.columns import SimpleColumn, YearColumn, MonthColumn, YearQuarterColumn, SumColumn
from corehq.apps.reports.datatables import DataTablesColumnGroup
from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn, SqlData


def make_trend(reportdata):
    class TR(reportdata):
        chart_x_label = 'Date'

        @property
        @memoized
        def years(self):
            delta = self.datespan.enddate - self.datespan.startdate
            return delta.days / 365

        @property
        @memoized
        def keys(self):
            if self.grouping == 'month':
                return self.month_keys
            elif self.grouping == 'quarter':
                return self.quarter_keys
            else:
                return self.year_keys

        @property
        @memoized
        def grouping(self):
            if self.years < 2:
                return 'month'
            elif self.years < 6:
                return 'quarter'
            else:
                return 'year'

        @property
        @memoized
        def month_keys(self):
            dt1 = self.datespan.startdate
            dt2 = self.datespan.enddate
            start_month = dt1.month
            end_months = (dt2.year - dt1.year) * 12 + dt2.month + 1
            dates = [[float(yr), float(mn)] for (yr, mn) in (
                ((m - 1) / 12 + dt1.year, (m - 1) % 12 + 1) for m in range(start_month, end_months)
            )]
            return dates

        @property
        @memoized
        def quarter_keys(self):
            months = self.month_keys
            quarter_set = set([(t[0], (t[1] - 1) // 3 + 1) for t in months])
            return sorted(list(quarter_set), key=lambda x: int(x[0] * 10 + x[1]))

        @property
        @memoized
        def year_keys(self):
            dt1 = self.datespan.startdate
            dt2 = self.datespan.enddate
            return [[year] for year in range(dt1.year, dt2.year + 1)]

        @property
        def group_by(self):
            if self.grouping == 'month':
                return ['year', 'month']
            elif self.grouping == 'quarter':
                return ['year', 'quarter']
            else:
                return ['year']

        @property
        def columns(self):
            cols = super(TR, self).columns
            if self.grouping == 'month':
                cols[0] = AggregateColumn(
                    "Month", combine_month_year,
                    [YearColumn('date', alias='year'), MonthColumn('date', alias='month')],
                    format_fn=format_date)
            elif self.grouping == 'quarter':
                cols[0] = AggregateColumn(
                    "Quarter", combine_quarter_year,
                    [YearColumn('date', alias='year'), YearQuarterColumn('date', alias='quarter')],
                    format_fn=format_date)
            else:
                cols[0] = DatabaseColumn("Year", YearColumn('date', alias='year'), format_fn=format_year)

            return cols

    return TR


class BaseSqlData(SqlData):
    has_total_column = True

    def __init__(self, config=None):
        self.config = config

        for slug, value in self.config.items():
            if not hasattr(self, slug):
                setattr(self, slug, value)

    @property
    def location_column(self):
        if self.group_by_district:
            return DatabaseColumn("Location", SimpleColumn('group_id'), format_fn=self.groupname, sort_type=None)
        else:
            return DatabaseColumn("Location", SimpleColumn('user_id'), format_fn=self.username, sort_type=None)

    @property
    def group_by_district(self):
        return self.group_id == ALL_CVSU_GROUP

    @property
    def filters(self):
        return []

    @property
    def filter_values(self):
        users = tuple([user.user_id for user in self.users])
        return dict(startdate=self.datespan.startdate,
                    enddate=self.datespan.enddate,
                    users=users)

    @property
    def data(self):
        if not self.users:
            # don't bother querying if there are no users
            return {}

        return super(BaseSqlData, self).data

    @property
    def group_by(self):
        if self.group_by_district:
            return ['group_id']
        else:
            return ['user_id']

    @property
    @memoized
    def group(self):
        if self.group_id:
            return Group.get(self.group_id)

    @property
    @memoized
    def users(self):
        group = self.group if not self.user_id else None
        user_ids = (self.user_id,)
        users = list(util.get_all_users_by_domain(
            domain=self.domain,
            user_ids=user_ids,
            group=group,
            simplified=True,
            CommCareUser=CommCareUserMemoizer()
        ))

        return sorted(users, key=itemgetter('raw_username'))

    @property
    @memoized
    def keys(self):
        if self.group_by_district:
            return [[g.get_id] for g in Group.by_domain(self.domain) if g.get_id != ALL_CVSU_GROUP]
        else:
            return [[user.user_id] for user in self.users]

    @property
    @memoized
    def usernames(self):
        return {user.user_id: user.raw_username for user in self.users}

    def username(self, user_id):
        try:
            username = self.usernames[user_id]
        except KeyError:
            username = user_id

        return format_datatables_data(username, username)

    def groupname(self, group_id):
        try:
            groupname = Group.get(group_id).name
        except KeyError:
            groupname = group_id

        return format_datatables_data(groupname, groupname)


class AgeGenderFilteredReport(BaseSqlData):
    @property
    def filters(self):
        filters = super(AgeGenderFilteredReport, self).filters

        if self.gender:
            filters.append('sex = :sex')
        if self.age:
            if self.age == 'lt5':
                filters.append('age < :ageupper')
            elif self.age == '5-18':
                filters.append('age between :agelower and :ageupper')
            elif self.age == 'lt18':
                filters.append('age < :ageupper')
            elif self.age == 'gte18':
                filters.append('age between :agelower and :ageupper')
        return filters

    @property
    def filter_values(self):
        vals = super(AgeGenderFilteredReport, self).filter_values

        if self.gender:
            vals['sex'] = self.gender
        if self.age:
            if self.age == 'lt5':
                vals['ageupper'] = 5
            elif self.age == '5-18':
                vals['agelower'] = 5
                vals['ageupper'] = 18
            elif self.age == 'lt18':
                vals['ageupper'] = 18
            elif self.age == 'gte18':
                vals['agelower'] = 18
                vals['ageupper'] = 500

        return vals


class ChildProtectionData(AgeGenderFilteredReport):
    title = 'Number and Type of Incidents of Abuse Reported at CVSU'
    chart_x_label = 'CVSU Location'
    chart_y_label = 'Number of incidents'
    table_name = make_ctable_table_name('cvsulive_UnicefMalawiFluff')

    @property
    def filters(self):
        return [BETWEEN('date_reported', 'startdate', 'enddate')] + super(ChildProtectionData, self).filters[1:]

    @property
    def engine_id(self):
        return UCR_ENGINE_ID

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], 'unicef_malawi')

    @property
    def columns(self):
        cat_group = DataTablesColumnGroup("Category of abuse")
        return [
            self.location_column,
            DatabaseColumn("Physical", SumColumn('abuse_category_physical_total'), header_group=cat_group),
            DatabaseColumn("Sexual", SumColumn('abuse_category_sexual_total'), header_group=cat_group),
            DatabaseColumn("Emotional", SumColumn('abuse_category_psychological_total'), header_group=cat_group),
            DatabaseColumn("Neglect", SumColumn('abuse_category_neglect_total'), header_group=cat_group),
            DatabaseColumn("Exploitation", SumColumn('abuse_category_exploitation_total'), header_group=cat_group),
            DatabaseColumn("Other", SumColumn('abuse_category_other_total'), header_group=cat_group),
            DatabaseColumn("Total incidents reported", SumColumn('abuse_category_total_total'),
                           header_group=cat_group)
        ]


class ChildrenInHouseholdData(AgeGenderFilteredReport):
    title = 'Number of Children in Survivor Household'
    chart_x_label = 'CVSU Location'
    chart_y_label = 'Number of children'
    table_name = make_ctable_table_name('cvsulive_UnicefMalawiFluff')
    has_total_column = False

    @property
    def filters(self):
        filters = super(ChildrenInHouseholdData, self).filters[1:]
        return [BETWEEN('date_reported', 'startdate', 'enddate')] + filters

    @property
    def engine_id(self):
        return UCR_ENGINE_ID

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], 'unicef_malawi')

    @property
    def columns(self):
        return [
            self.location_column,
            DatabaseColumn(
                "Children per household experiencing abuse", SumColumn('abuse_children_abused_total')
            ),
            DatabaseColumn(
                "Total number of children in household", SumColumn('abuse_children_in_household_total')
            ),
        ]


class CVSUActivityData(FilterMixin, BaseSqlData):
    title = 'Activities Performed'
    chart_x_label = 'CVSU Location'
    chart_y_label = 'Number of reports'
    table_name = make_ctable_table_name('cvsulive_UnicefMalawiFluff')

    @property
    def engine_id(self):
        return UCR_ENGINE_ID

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], 'unicef_malawi')

    @property
    def columns(self):
        return [
            self.location_column,
            DatabaseColumn(
                "Incidents of Abuse",
                SumColumn('incidents_total',
                          filters=self.filters + [BETWEEN('date_reported', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Outreach activities",
                SumColumn('outreach_total', filters=self.filters + [BETWEEN('date', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "IGA Reports",
                SumColumn('iga_total', filters=self.filters + [BETWEEN('start_date', 'startdate', 'enddate')])
            ),
            AggregateColumn(
                "Total", self.sum,
                [AliasColumn('incidents_total'), AliasColumn('outreach_total')]),
        ]

    def sum(self, no_incidents, outreach):
        return (no_incidents or 0) + (outreach or 0)


class CVSUServicesData(FilterMixin, BaseSqlData):
    title = 'Services Provided'
    chart_x_label = 'CVSU Location'
    chart_y_label = 'Number of incidents'
    table_name = make_ctable_table_name('cvsulive_UnicefMalawiFluff')

    @property
    def engine_id(self):
        return UCR_ENGINE_ID

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], 'unicef_malawi')

    @property
    def columns(self):
        return [
            self.location_column,
            DatabaseColumn(
                "Counselling",
                SumColumn('service_counselling_total',
                          filters=self.filters + [BETWEEN('date_reported', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Psychosocial Support",
                SumColumn('service_psychosocial_support_total',
                          filters=self.filters + [BETWEEN('date_reported', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "First Aid",
                SumColumn('service_first_aid_total',
                          filters=self.filters + [BETWEEN('date_reported', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Shelter", SumColumn('service_shelter_total',
                                     filters=self.filters + [BETWEEN('date_reported', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Referral",
                SumColumn('service_referral_total',
                          filters=self.filters + [BETWEEN('date_reported_mediated', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Mediation",
                SumColumn('service_mediation_total',
                          filters=self.filters + [BETWEEN('date_reported', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Other",
                SumColumn('service_other_total',
                          filters=self.filters + [BETWEEN('date_reported', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Total",
                SumColumn('service_total_total',
                          filters=self.filters + [BETWEEN('date_reported_mediated', 'startdate', 'enddate')])
            ),
        ]


class CVSUIncidentResolutionData(FilterMixin, BaseSqlData):
    title = 'Incident Resolution'
    chart_x_label = 'CVSU Location'
    chart_y_label = 'Number of incidents'
    table_name = make_ctable_table_name('cvsulive_UnicefMalawiFluff')

    @property
    def engine_id(self):
        return UCR_ENGINE_ID

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], 'unicef_malawi')

    @property
    def columns(self):
        return [
            self.location_column,
            DatabaseColumn(
                "Resolved at CVSU",
                SumColumn('resolution_resolved_at_cvsu_total',
                          filters=self.filters + [BETWEEN('mediation_provided_date', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Referred to TA",
                SumColumn('resolution_referred_ta_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Referred to TA Court",
                SumColumn('resolution_referral_ta_court_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Referred to Police",
                SumColumn('resolution_referral_police_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Referred to Social Welfare",
                SumColumn('resolution_referral_social_welfare_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Referred to NGO",
                SumColumn('resolution_referral_ngo_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Referred to Other",
                SumColumn('resolution_referral_other_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Unresolved",
                SumColumn('resolution_unresolved_total',
                          filters=self.filters + [BETWEEN('mediation_provided_date', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Case Withdrawn",
                SumColumn('resolution_case_withdrawn_total',
                          filters=self.filters + [BETWEEN('mediation_provided_date', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Other",
                SumColumn('resolution_other_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ),
            DatabaseColumn(
                "Total",
                SumColumn('resolution_total_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ),
        ]


class ChildProtectionDataTrend(DateColumnMixin, make_trend(ChildProtectionData)):

    @property
    def columns(self):
        cols = super(ChildProtectionDataTrend, self).columns
        cols[0] = self.date_column
        return cols


class ChildrenInHouseholdDataTrend(DateColumnMixin, make_trend(ChildrenInHouseholdData)):

    @property
    def columns(self):
        cols = super(ChildrenInHouseholdDataTrend, self).columns
        cols[0] = self.date_column
        return cols


class CVSUServicesDataTrend(DateColumnMixin, CVSUSqlDataMixin, make_trend(CVSUServicesData)):
    @property
    def columns(self):
        cols = [
            self.location_column,
            dynamic_date_aggregation(DatabaseColumn(
                "Counselling",
                SumColumn('service_counselling_total',
                          filters=self.filters + [BETWEEN('date_reported', 'startdate', 'enddate')])
            ), date_column='date_reported'),
            dynamic_date_aggregation(DatabaseColumn(
                "Psychosocial Support",
                SumColumn('service_psychosocial_support_total',
                          filters=self.filters + [BETWEEN('date_reported', 'startdate', 'enddate')])
            ), date_column='date_reported'),
            dynamic_date_aggregation(DatabaseColumn(
                "First Aid",
                SumColumn('service_first_aid_total',
                          filters=self.filters + [BETWEEN('date_reported', 'startdate', 'enddate')])
            ), date_column='date_reported'),
            dynamic_date_aggregation(DatabaseColumn(
                "Shelter", SumColumn('service_shelter_total',
                                     filters=self.filters + [BETWEEN('date_reported', 'startdate', 'enddate')])
            ), date_column='date_reported'),
            dynamic_date_aggregation(DatabaseColumn(
                "Referral",
                SumColumn('service_referral_total',
                          filters=self.filters + [BETWEEN('date_reported_mediated', 'startdate', 'enddate')])
            ), date_column='date_reported_mediated'),
            dynamic_date_aggregation(DatabaseColumn(
                "Mediation",
                SumColumn('service_mediation_total',
                          filters=self.filters + [BETWEEN('date_reported', 'startdate', 'enddate')])
            ), date_column='date_reported'),
            dynamic_date_aggregation(DatabaseColumn(
                "Other",
                SumColumn('service_other_total',
                          filters=self.filters + [BETWEEN('date_reported', 'startdate', 'enddate')])
            ), date_column='date_reported'),
            dynamic_date_aggregation(DatabaseColumn(
                "Total",
                SumColumn('service_total_total',
                          filters=self.filters + [BETWEEN('date_reported_mediated', 'startdate', 'enddate')])
            ), date_column='date_reported_mediated'),
        ]

        cols[0] = self.date_column
        return cols


class CVSUActivityDataTrend(DateColumnMixin, CVSUSqlDataMixin, make_trend(CVSUActivityData)):
    @property
    def columns(self):
        cols = [
            self.location_column,
            dynamic_date_aggregation(DatabaseColumn(
                "Incidents of Abuse",
                SumColumn('incidents_total', filters=self.filters + [
                    BETWEEN('date_reported', 'startdate', 'enddate')] + self.filters),
            ), date_column='date_reported'),
            dynamic_date_aggregation(DatabaseColumn(
                "Outreach activities",
                SumColumn('outreach_total', filters=self.filters + [BETWEEN('date', 'startdate', 'enddate')])
            ), date_column='date'),
            dynamic_date_aggregation(DatabaseColumn(
                "IGA Reports",
                SumColumn('iga_total', filters=self.filters + [BETWEEN('start_date', 'startdate', 'enddate')])
            ), date_column='start_date'),
            AggregateColumn(
                "Total", self.sum,
                [AliasColumn('incidents_total'), AliasColumn('outreach_total')]),
        ]

        cols[0] = self.date_column
        return cols


class CVSUIncidentResolutionDataTrend(DateColumnMixin, CVSUSqlDataMixin, make_trend(CVSUIncidentResolutionData)):

    @property
    def columns(self):
        cols = [
            self.location_column,
            dynamic_date_aggregation(DatabaseColumn(
                "Resolved at CVSU",
                SumColumn('resolution_resolved_at_cvsu_total',
                          filters=self.filters + [BETWEEN('mediation_provided_date', 'startdate', 'enddate')])
            ), date_column='mediation_provided_date'),
            dynamic_date_aggregation(DatabaseColumn(
                "Referred to TA",
                SumColumn('resolution_referred_ta_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ), date_column='date_reported_provided_mediated'),
            dynamic_date_aggregation(DatabaseColumn(
                "Referred to TA Court",
                SumColumn('resolution_referral_ta_court_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ), date_column='date_reported_provided_mediated'),
            dynamic_date_aggregation(DatabaseColumn(
                "Referred to Police",
                SumColumn('resolution_referral_police_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ), date_column='date_reported_provided_mediated'),
            dynamic_date_aggregation(DatabaseColumn(
                "Referred to Social Welfare",
                SumColumn('resolution_referral_social_welfare_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ), date_column='date_reported_provided_mediated'),
            dynamic_date_aggregation(DatabaseColumn(
                "Referred to NGO",
                SumColumn('resolution_referral_ngo_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ), date_column='date_reported_provided_mediated'),
            dynamic_date_aggregation(DatabaseColumn(
                "Referred to Other",
                SumColumn('resolution_referral_other_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ), date_column='date_reported_provided_mediated'),
            dynamic_date_aggregation(DatabaseColumn(
                "Unresolved",
                SumColumn('resolution_unresolved_total',
                          filters=self.filters + [BETWEEN('mediation_provided_date', 'startdate', 'enddate')])
            ), date_column='mediation_provided_date'),
            dynamic_date_aggregation(DatabaseColumn(
                "Case Withdrawn",
                SumColumn('resolution_case_withdrawn_total',
                          filters=self.filters + [BETWEEN('mediation_provided_date', 'startdate', 'enddate')])
            ), date_column='mediation_provided_date'),
            dynamic_date_aggregation(DatabaseColumn(
                "Other",
                SumColumn('resolution_other_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ), date_column='mediation_provided_date'),
            dynamic_date_aggregation(DatabaseColumn(
                "Total",
                SumColumn('resolution_total_total',
                          filters=self.filters + [
                              BETWEEN('date_reported_provided_mediated', 'startdate', 'enddate')])
            ), date_column='date_reported_provided_mediated'),
        ]

        cols[0] = self.date_column
        return cols
