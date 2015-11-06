from sqlagg import SumColumn, AliasColumn
from sqlagg.columns import MonthColumn, YearColumn, YearQuarterColumn
from sqlagg.filters import BETWEEN
from corehq.apps.reports.datatables import DataTablesColumnGroup
from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn
from corehq.apps.userreports.sql import get_table_name
from custom.apps.cvsu.mixins import FilterMixin, CVSUSqlDataMixin, DateColumnMixin
from custom.apps.cvsu.sqldata import ChildProtectionData, ChildrenInHouseholdData, CVSUActivityData, \
    CVSUServicesData, CVSUIncidentResolutionData, make_trend, combine_month_year, format_date, \
    combine_quarter_year, \
    format_year
from custom.apps.cvsu.utils import dynamic_date_aggregation


class NewChildProtectionData(ChildProtectionData):
    @property
    def filters(self):
        return [BETWEEN('date_reported', 'startdate', 'enddate')] + super(NewChildProtectionData, self).filters[1:]

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


class NewChildrenInHouseholdData(ChildrenInHouseholdData):
    @property
    def filters(self):
        return [BETWEEN('date_reported', 'startdate', 'enddate')] + super(NewChildrenInHouseholdData,
                                                                          self).filters[1:]

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


class NewCVSUActivityData(FilterMixin, CVSUActivityData):

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


class NewCVSUServicesData(FilterMixin, CVSUServicesData):

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


class NewCVSUIncidentResolutionData(FilterMixin, CVSUIncidentResolutionData):
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


class NewChildProtectionDataTrend(DateColumnMixin, make_trend(NewChildProtectionData)):

    @property
    def columns(self):
        cols = super(NewChildProtectionDataTrend, self).columns
        cols[0] = self.date_column
        return cols


class NewChildrenInHouseholdDataTrend(DateColumnMixin, make_trend(NewChildrenInHouseholdData)):

    @property
    def columns(self):
        cols = super(NewChildrenInHouseholdDataTrend, self).columns
        cols[0] = self.date_column
        return cols


class NewCVSUServicesDataTrend(DateColumnMixin, CVSUSqlDataMixin, make_trend(NewCVSUServicesData)):
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


class NewCVSUActivityDataTrend(DateColumnMixin, CVSUSqlDataMixin, make_trend(NewCVSUActivityData)):
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


class NewCVSUIncidentResolutionDataTrend(DateColumnMixin, CVSUSqlDataMixin,
                                         make_trend(NewCVSUIncidentResolutionData)):
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
