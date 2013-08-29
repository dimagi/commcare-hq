from operator import itemgetter
from corehq.apps.groups.models import Group
from corehq.apps.reports import util
from corehq.apps.reports.standard import CommCareUserMemoizer
from corehq.apps.reports.util import format_datatables_data
from .filters import ALL_CVSU_GROUP
from dimagi.utils.decorators.memoized import memoized
from sqlagg import AliasColumn
from sqlagg.columns import SimpleColumn, YearColumn, MonthColumn, YearQuarterColumn, SumColumn
from corehq.apps.reports.datatables import DataTablesColumnGroup
from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn, SqlData


def combine_month_year(year, month):
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    return "%s %s" % (months[int(month) - 1], int(year)), int(year * 100 + month)


def combine_quarter_year(year, quarter):
    return "%s Q%s" % (int(year), int(quarter)), int(year * 10 + quarter)


def format_year(year):
    return format_datatables_data(int(year), int(year))


def format_date(value):
    return format_datatables_data(value[0], value[1])


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
                cols[0] = AggregateColumn("Month", combine_month_year,
                                          YearColumn('date', alias='year'),
                                          MonthColumn('date', alias='month'), format_fn=format_date)
            elif self.grouping == 'quarter':
                cols[0] = AggregateColumn("Quarter", combine_quarter_year,
                                          YearColumn('date', alias='year'),
                                          YearQuarterColumn('date', alias='quarter'), format_fn=format_date)
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
        filters = ['date between :startdate and :enddate']
        if not self.group_by_district:
            filters.append('"user_id" in :users')

        return filters

    @property
    def filter_values(self):
        users = tuple([user.get('user_id') for user in self.users])
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
            return [[user.get('user_id')] for user in self.users]

    @property
    @memoized
    def usernames(self):
        return dict([(user.get('user_id'), user.get('raw_username')) for user in self.users])

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
    table_name = 'cvsulive_UnicefMalawiFluff'

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
            DatabaseColumn("Total incidents reported", SumColumn('abuse_category_total_total'), header_group=cat_group)
        ]


class ChildrenInHouseholdData(AgeGenderFilteredReport):
    title = 'Number of Children in Survivor Household'
    chart_x_label = 'CVSU Location'
    chart_y_label = 'Number of children'
    table_name = 'cvsulive_UnicefMalawiFluff'
    has_total_column = False

    @property
    def columns(self):
        return [
            self.location_column,
            DatabaseColumn("Children per household experiencing abuse", SumColumn('abuse_children_abused_total')),
            DatabaseColumn("Total number of children in household", SumColumn('abuse_children_in_household_total')),
        ]


class CVSUActivityData(BaseSqlData):
    title = 'Activities Performed'
    chart_x_label = 'CVSU Location'
    chart_y_label = 'Number of reports'
    table_name = 'cvsulive_UnicefMalawiFluff'

    @property
    def columns(self):
        return [
            self.location_column,
            DatabaseColumn("Incidents of Abuse", SumColumn('incidents_total')),
            DatabaseColumn("Outreach activities", SumColumn('outreach_total')),
            DatabaseColumn("IGA Reports", SumColumn('iga_total')),
            AggregateColumn("Total", self.sum,
                            AliasColumn('incidents_total'),
                            AliasColumn('outreach_total')),
        ]

    def sum(self, no_incidents, outreach):
        return (no_incidents or 0) + (outreach or 0)


class CVSUServicesData(BaseSqlData):
    title = 'Services Provided'
    chart_x_label = 'CVSU Location'
    chart_y_label = 'Number of incidents'
    table_name = 'cvsulive_UnicefMalawiFluff'

    @property
    def columns(self):
        return [
            self.location_column,
            DatabaseColumn("Counselling", SumColumn('service_counselling_total')),
            DatabaseColumn("Psychosocial Support", SumColumn('service_psychosocial_support_total')),
            DatabaseColumn("First Aid", SumColumn('service_first_aid_total')),
            DatabaseColumn("Shelter", SumColumn('service_shelter_total')),
            DatabaseColumn("Referral", SumColumn('service_referral_total')),
            DatabaseColumn("Mediation", SumColumn('service_mediation_total')),
            DatabaseColumn("Other", SumColumn('service_other_total')),
            DatabaseColumn("Total", SumColumn('service_total_total')),
        ]


class CVSUIncidentResolutionData(BaseSqlData):
    title = 'Incident Resolution'
    chart_x_label = 'CVSU Location'
    chart_y_label = 'Number of incidents'
    table_name = 'cvsulive_UnicefMalawiFluff'

    @property
    def columns(self):
        return [
            self.location_column,
            DatabaseColumn("Resolved at CVSU", SumColumn('resolution_resolved_at_cvsu_total')),
            DatabaseColumn("Referred to TA", SumColumn('resolution_referred_ta_total')),
            DatabaseColumn("Referred to TA Court", SumColumn('resolution_referral_ta_court_total')),
            DatabaseColumn("Referred to Police", SumColumn('resolution_referral_police_total')),
            DatabaseColumn("Referred to Social Welfare", SumColumn('resolution_referral_social_welfare_total')),
            DatabaseColumn("Referred to NGO", SumColumn('resolution_referral_ngo_total')),
            DatabaseColumn("Referred to Other", SumColumn('resolution_referral_other_total')),
            DatabaseColumn("Unresolved", SumColumn('resolution_unresolved_total')),
            DatabaseColumn("Case Withdrawn", SumColumn('resolution_case_withdrawn_total')),
            DatabaseColumn("Other", SumColumn('resolution_other_total')),
            DatabaseColumn("Total", SumColumn('resolution_total_total')),
        ]


ChildProtectionDataTrend = make_trend(ChildProtectionData)
ChildrenInHouseholdDataTrend = make_trend(ChildrenInHouseholdData)
CVSUServicesDataTrend = make_trend(CVSUServicesData)
CVSUActivityDataTrend = make_trend(CVSUActivityData)
CVSUIncidentResolutionDataTrend = make_trend(CVSUIncidentResolutionData)
