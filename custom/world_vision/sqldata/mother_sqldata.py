from sqlagg import CountUniqueColumn, AliasColumn
from sqlagg.columns import SimpleColumn, SumColumn
from sqlagg.filters import LTE, AND, GTE, GT, EQ, NOTEQ, OR, IN
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn
from corehq.apps.reports.util import get_INFilter_bindparams
from custom.utils.utils import clean_IN_filter_value
from custom.world_vision.sqldata import BaseSqlData
from custom.world_vision.sqldata.main_sqldata import AnteNatalCareServiceOverview, DeliveryPlaceDetails


class MotherRegistrationDetails(BaseSqlData):
    table_name = "fluff_WorldVisionMotherFluff"
    slug = 'mother_registration_details'
    title = 'Mother Registration Details'

    @property
    def filters(self):
        return super(MotherRegistrationDetails, self).filters[1:]

    @property
    def rows(self):
        from custom.world_vision import MOTHER_INDICATOR_TOOLTIPS
        result = []
        for column in self.columns:
            result.append([{'sort_key': column.header, 'html': column.header,
                            'tooltip': self.get_tooltip(MOTHER_INDICATOR_TOOLTIPS['mother_registration_details'], column.slug)},
                           {'sort_key': self.data[column.slug], 'html': self.data[column.slug]}])
        return result

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Entity'), DataTablesColumn('Number')])

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Total mothers registered ever",  CountUniqueColumn('doc_id', alias="total")),
        ]
        if 'startdate' not in self.config and 'enddate' not in self.config or 'startdate' not in self.config and 'enddate' in self.config:
            columns.extend([
                DatabaseColumn("Total open mother cases",
                    CountUniqueColumn('doc_id',
                        alias="no_date_opened",
                        filters=self.filters + [EQ('closed_on', 'empty')]
                    )
                ),
                DatabaseColumn("Total closed mother cases",
                    CountUniqueColumn('doc_id',
                        alias="no_date_closed",
                        filters=self.filters +  [NOTEQ('closed_on', 'empty')]
                    )
                ),
                DatabaseColumn("New registrations during last 30 days",
                        CountUniqueColumn('doc_id',
                            alias="no_date_new_registrations",
                            filters=self.filters + [AND([GTE('opened_on', "last_month"), LTE('opened_on', "today")])]
                        )
                )
            ])
        else:
            columns.extend([
                DatabaseColumn(
                    "Mother cases open at end of period", CountUniqueColumn(
                        'doc_id', alias="opened",
                        filters=self.filters + [AND([LTE('opened_on', "stred"), OR([EQ('closed_on', 'empty'),
                                                                                    GT('closed_on', "stred")])])]
                    )
                ),
                DatabaseColumn(
                    "Mother cases closed during period", CountUniqueColumn(
                        'doc_id', alias="closed",
                        filters=self.filters + [AND([GTE('closed_on', "strsd"), LTE('closed_on', "stred")])]
                    )
                ),
                DatabaseColumn(
                    "Total mothers followed during period", CountUniqueColumn(
                        'doc_id', alias="followed",
                        filters=self.filters + [AND([LTE('opened_on', "stred"), OR([EQ('closed_on', 'empty'),
                                                                                    GTE('closed_on', "strsd")])])]
                    )
                ),
                DatabaseColumn(
                    "Total pregnant", CountUniqueColumn(
                        'doc_id', alias="total_pregnant",
                        filters=self.filters + [AND([LTE('opened_on', "stred"),
                                                     OR([EQ('closed_on', 'empty'), GTE('closed_on', "strsd")]),
                                                     EQ('mother_state', 'pregnant_mother_type')])]
                    )
                ),
                DatabaseColumn(
                    "New registrations during time period", CountUniqueColumn(
                        'doc_id', alias="new_registrations",
                        filters=self.filters + [AND([LTE('opened_on', "stred"), GTE('opened_on', "strsd")])]
                    )
                )
            ])
        return columns


class ClosedMotherCasesBreakdown(BaseSqlData):
    table_name = "fluff_WorldVisionMotherFluff"
    slug = 'closed_mother_cases-breakdown'
    title = 'Closed Mother Cases Breakdown'
    show_total = True
    total_row_name = "Mother cases closed during the time period"
    chart_title = 'Closed Maternal Cases'
    show_charts = True
    chart_x_label = ''
    chart_y_label = ''
    chart_only = True

    @property
    def group_by(self):
        return ['reason_for_mother_closure']

    @property
    def rows(self):
        from custom.world_vision import REASON_FOR_CLOSURE_MAPPING
        return self._get_rows(REASON_FOR_CLOSURE_MAPPING, super(ClosedMotherCasesBreakdown, self).rows)

    @property
    def filters(self):
        filter = super(ClosedMotherCasesBreakdown, self).filters[1:]
        if 'strsd' in self.config:
            filter.append(GTE('closed_on', 'strsd'))
        if 'stred' in self.config:
            filter.append(LTE('closed_on', 'stred'))
        return filter

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Reason for closure'), DataTablesColumn('Number'), DataTablesColumn('Percentage')])

    @property
    def columns(self):
        return [
            DatabaseColumn("Reason for closure", SimpleColumn('reason_for_mother_closure')),
            DatabaseColumn("Number", CountUniqueColumn('doc_id'))
        ]


class PregnantMotherBreakdownByTrimester(BaseSqlData):
    table_name = "fluff_WorldVisionMotherFluff"
    slug = 'pregnant_mother_by_trimester'
    title = 'Pregnant Woman Breakdown by Trimester'
    chart_title = 'Pregnant Mother Visits'
    show_total = True
    total_row_name = "Total pregnant "
    show_charts = True
    chart_x_label = ''
    chart_y_label = ''
    chart_only = True

    def percent_fn(self, y):
        x = self.data['trimester_1'] + self.data['trimester_2'] + self.data['trimester_3']
        return "%(p).0f%%" % \
            {
                "p": (100 * float(y or 0) / float(x or 1))
            }

    @property
    def filters(self):
        filter = super(PregnantMotherBreakdownByTrimester, self).filters
        filter.append(EQ('mother_state', 'pregnant_mother_type'))
        filter.append(NOTEQ('edd', 'empty'))
        return filter

    @property
    def rows(self):
        result = []
        for column in self.columns:
            percent = self.percent_fn(self.data[column.slug])
            result.append([{'sort_key': column.header, 'html': column.header},
                           {'sort_key': self.data[column.slug], 'html': self.data[column.slug]},
                           {'sort_key': 'percentage', 'html': percent}]
            )
        return result

    @property
    def columns(self):
        return [
            DatabaseColumn("Trimester 1",
                CountUniqueColumn('doc_id',
                    alias="trimester_1", filters=self.filters + [GT('edd', "today_plus_196")]
                )
            ),
            DatabaseColumn("Trimester 2",
                CountUniqueColumn('doc_id',
                    alias="trimester_2",
                    filters=self.filters + [AND([LTE('edd', "today_plus_196"), GT('edd', "today_plus_84")])]
                )
            ),
            DatabaseColumn("Trimester 3",
                CountUniqueColumn('doc_id',
                    alias="trimester_3", filters=self.filters + [LTE('edd', 'today_plus_84')]
                )
            )
        ]


class AnteNatalCareServiceOverviewExtended(AnteNatalCareServiceOverview):
    slug = 'ante_natal_care_service_overview_extended'
    show_charts = True
    chart_x_label = ''
    chart_y_label = ''
    chart_only = True

    @property
    def rows(self):
        from custom.world_vision import MOTHER_INDICATOR_TOOLTIPS
        result = [[{'sort_key': self.columns[0].header, 'html': self.columns[0].header},
                  {'sort_key': self.data[self.columns[0].slug], 'html': self.data[self.columns[0].slug]},
                  {'sort_key': 'n/a', 'html': 'n/a'},
                  {'sort_key': 'n/a', 'html': 'n/a'}]]
        for i in range(1,15):
            result.append([{'sort_key': self.columns[i].header, 'html': self.columns[i].header,
                            'tooltip': self.get_tooltip(MOTHER_INDICATOR_TOOLTIPS['ante_natal_care_service_details'], self.columns[i].slug)},
                           {'sort_key': self.data[self.columns[i].slug], 'html': self.data[self.columns[i].slug]},
                           {'sort_key': self.data[self.columns[i + 14].slug], 'html': self.data[self.columns[i + 14].slug],
                            'tooltip': self.get_tooltip(MOTHER_INDICATOR_TOOLTIPS['ante_natal_care_service_details'], self.columns[i+ 14].slug)},
                           {'sort_key': self.percent_fn(self.data[self.columns[i + 14].slug], self.data[self.columns[i].slug]),
                            'html': self.percent_fn(self.data[self.columns[i + 14].slug], self.data[self.columns[i].slug])}])
        return result

    @property
    def columns(self):
        return [
            DatabaseColumn("Total pregnant", CountUniqueColumn('doc_id', alias="total_pregnant")),
            DatabaseColumn("No ANC", CountUniqueColumn('doc_id', alias="no_anc",
                                                       filters=self.filters + [NOTEQ('anc_1', 'yes')])),
            DatabaseColumn("ANC1", CountUniqueColumn('doc_id', alias="anc_1",
                                                     filters=self.filters + [EQ('anc_1', 'yes')])),
            DatabaseColumn("ANC2", CountUniqueColumn('doc_id', alias="anc_2",
                                                     filters=self.filters + [EQ('anc_2', 'yes')])),
            DatabaseColumn("ANC3", CountUniqueColumn('doc_id', alias="anc_3",
                                                     filters=self.filters + [EQ('anc_3', 'yes')])),
            DatabaseColumn("ANC4", CountUniqueColumn('doc_id', alias="anc_4",
                                                     filters=self.filters + [EQ('anc_4', 'yes')])),
            DatabaseColumn("TT1", CountUniqueColumn('doc_id', alias="tt_1",
                                                    filters=self.filters + [EQ('tt_1', 'yes')])),
            DatabaseColumn("TT2", CountUniqueColumn('doc_id', alias="tt_2",
                                                    filters=self.filters + [EQ('tt_2', 'yes')])),
            DatabaseColumn("TT Booster", CountUniqueColumn('doc_id', alias="tt_booster",
                                                           filters=self.filters + [EQ('tt_booster', 'yes')])),
            DatabaseColumn("TT Complete",
                           CountUniqueColumn('doc_id', alias="tt_completed",
                                             filters=self.filters + [OR([EQ('tt_2', 'yes'),
                                                                         EQ('tt_booster', 'yes')])])),
            DatabaseColumn("IFA received", CountUniqueColumn('doc_id', alias="ifa_tablets",
                                                             filters=self.filters + [EQ('iron_folic', 'yes')])),
            DatabaseColumn("100 IFA consumed",
                           CountUniqueColumn('doc_id', alias="100_tablets",
                                             filters=self.filters[1:-1] + [AND([EQ('completed_100_ifa', 'yes'),
                                                                                GTE('delivery_date', 'strsd'),
                                                                                LTE('delivery_date', 'stred')])])),
            DatabaseColumn("Clinically anemic mothers",
                           CountUniqueColumn('doc_id', alias="clinically_anemic",
                                             filters=self.filters + [EQ('anemia_signs', 'yes')])),
            DatabaseColumn("Number of pregnant mother referrals due to danger signs",
                           CountUniqueColumn('doc_id', alias="danger_signs",
                                             filters=self.filters + [EQ('currently_referred', 'yes')])),
            DatabaseColumn("Knows closest health facility",
                           CountUniqueColumn('doc_id', alias="knows_closest_facility",
                                             filters=self.filters + [EQ('knows_closest_facility', 'yes')])),
            DatabaseColumn("No ANC Total Eligible",
                           CountUniqueColumn('doc_id', alias="no_anc_eligible",
                                             filters=self.filters + [LTE('edd', 'today_plus_196')])),
            DatabaseColumn("ANC1 Total Eligible",
                           CountUniqueColumn('doc_id', alias="anc_1_eligible",
                                             filters=self.filters + [LTE('edd', 'today_plus_196')])),
            DatabaseColumn("ANC2 Total Eligible",
                           CountUniqueColumn('doc_id', alias="anc_2_eligible",
                                             filters=self.filters + [AND([EQ('anc_1', 'yes'),
                                                                          LTE('edd', 'today_plus_112')])])),
            DatabaseColumn("ANC3 Total Eligible",
                           CountUniqueColumn('doc_id', alias="anc_3_eligible",
                                             filters=self.filters + [AND([EQ('anc_2', 'yes'),
                                                                          LTE('edd', 'today_plus_56')])])),
            DatabaseColumn("ANC4 Total Eligible",
                           CountUniqueColumn('doc_id', alias="anc_4_eligible",
                                             filters=self.filters + [AND([EQ('anc_3', 'yes'),
                                                                          LTE('edd', 'today_plus_35')])])),
            DatabaseColumn("TT1 Total Eligible",
                           CountUniqueColumn('doc_id', alias="tt_1_eligible",
                                             filters=self.filters + [NOTEQ('previous_tetanus', 'yes')])),
            DatabaseColumn("TT2 Total Eligible", CountUniqueColumn('doc_id', alias="tt_2_eligible",
                                                                   filters=self.filters + [EQ('tt_1', 'yes')])),
            DatabaseColumn("TT Booster Total Eligible",
                           CountUniqueColumn('doc_id', alias="tt_booster_eligible",
                                             filters=self.filters + [EQ('previous_tetanus', 'yes')])),
            DatabaseColumn("TT Completed (TT2 or Booster) Total Eligible",
                           CountUniqueColumn('doc_id', alias="tt_completed_eligible",
                                             filters=self.filters + [OR([EQ('tt_1', 'yes'),
                                                                         EQ('previous_tetanus', 'yes')])])),
            DatabaseColumn("Taking IFA tablets Total Eligible",
                           CountUniqueColumn('doc_id', alias="ifa_tablets_eligible")),
            DatabaseColumn("Completed 100 IFA tablets Total Eligible",
                           CountUniqueColumn('doc_id', alias="100_tablets_eligible",
                                             filters=self.filters[1:-1] + [AND([GTE('delivery_date', 'strsd'),
                                                                               LTE('delivery_date', 'stred')])])),
            DatabaseColumn("Clinically anemic mothers Total Eligible",
                           CountUniqueColumn('doc_id', alias="clinically_anemic_eligible")),
            DatabaseColumn("Number of mother referrals due to danger signs Total Eligible",
                           CountUniqueColumn('doc_id', alias="danger_signs_eligible")),
            DatabaseColumn("Know closest health facility Total Eligible",
                           CountUniqueColumn('doc_id', alias="knows_closest_facility_eligible"))
        ]


class DeliveryMothersIds(BaseSqlData):
    table_name = "fluff_WorldVisionMotherFluff"

    @property
    def filters(self):
        filter =  super(DeliveryMothersIds, self).filters[1:]
        if 'strsd' in self.config:
            filter.append(GTE('delivery_date', 'strsd'))
        if 'stred' in self.config:
            filter.append(LTE('delivery_date', 'stred'))
        return filter

    @property
    def group_by(self):
        return ['doc_id']

    @property
    def columns(self):
        return [
            DatabaseColumn("Mother ID",  SimpleColumn('doc_id'))
        ]

class DeliveryLiveBirthDetails(BaseSqlData):
    table_name = "fluff_WorldVisionChildFluff"
    slug = 'delivery_live_birth_details'
    title = ''
    show_charts = True
    chart_x_label = ''
    chart_y_label = ''
    show_total = True
    total_row_name = "Total live births"
    chart_title = 'Live Births'
    accordion_start = False
    accordion_end = False
    chart_only = True

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Entity'), DataTablesColumn('Number'), DataTablesColumn('Percentage')])

    @property
    def filters(self):
        self.config['mother_ids'] = tuple(DeliveryMothersIds(config=self.config).data.keys()) + ('',)
        return [IN('mother_id', get_INFilter_bindparams('mother_ids', self.config['mother_ids']))]

    @property
    def filter_values(self):
        return clean_IN_filter_value(super(DeliveryLiveBirthDetails, self).filter_values, 'mother_ids')

    @property
    def columns(self):
        return [
            DatabaseColumn("Live birth (Male)",
                CountUniqueColumn('doc_id', alias='girls', filters=self.filters + [EQ('gender', 'female')])
            ),
            DatabaseColumn("Live birth (Female)",
                CountUniqueColumn('doc_id', alias='boys', filters=self.filters + [EQ('gender', 'male')])
            )
        ]

    @property
    def rows(self):
        total = sum(v if v else 0 for v in self.data.values())
        result = []
        for column in self.columns:
            percent = self.percent_fn(total, self.data[column.slug])
            result.append([{'sort_key': column.header, 'html': column.header},
                           {'sort_key': self.data[column.slug] if self.data[column.slug] else 0,
                            'html': self.data[column.slug] if self.data[column.slug] else 0},
                           {'sort_key': 'percentage', 'html': percent}
            ])

        return result


class DeliveryStillBirthDetails(BaseSqlData):
    table_name = "fluff_WorldVisionMotherFluff"
    slug = 'delivery_still_birth_details'
    title = ''
    accordion_start = False
    accordion_end = True

    @property
    def filters(self):
        filter =  super(DeliveryStillBirthDetails, self).filters[1:]
        if 'strsd' in self.config:
            filter.append(GTE('delivery_date', 'strsd'))
        if 'stred' in self.config:
            filter.append(LTE('delivery_date', 'stred'))
        return filter

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn(''), DataTablesColumn('Number')])

    @property
    def columns(self):
        return [
            DatabaseColumn("Still births",
                SumColumn('number_of_children_born_dead_total')
            ),
            DatabaseColumn("Abortions",
                CountUniqueColumn('doc_id', alias="abortions", filters=self.filters + [EQ('reason_for_mother_closure', 'abortion')]),
            ),
        ]

    @property
    def rows(self):
        from custom.world_vision import MOTHER_INDICATOR_TOOLTIPS
        result = []
        for column in self.columns:
            result.append([{'sort_key': column.header, 'html': column.header,
                            'tooltip': self.get_tooltip(MOTHER_INDICATOR_TOOLTIPS['delivery_details'], column.slug)},
                           {'sort_key': self.data[column.slug] if self.data[column.slug] else 0,
                            'html': self.data[column.slug] if self.data[column.slug] else 0}]
            )
        return result


class PostnatalCareOverview(BaseSqlData):
    table_name = "fluff_WorldVisionMotherFluff"
    slug = 'postnatal_care_overview'
    title = 'Postnatal Care Overview'
    show_charts = True
    chart_title = 'PNC Visits'
    chart_x_label = ''
    chart_y_label = ''
    accordion_end = False
    chart_only = True

    @property
    def filters(self):
        filter =  super(PostnatalCareOverview, self).filters[1:]
        if 'strsd' in self.config:
            filter.append(GTE('delivery_date', 'strsd'))
        if 'stred' in self.config:
            filter.append(LTE('delivery_date', 'stred'))
        return filter

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Entity'), DataTablesColumn('Number'),
                                  DataTablesColumn('Total Eligible'), DataTablesColumn('Percentage')])

    @property
    def rows(self):
        from custom.world_vision import MOTHER_INDICATOR_TOOLTIPS
        result = []
        for i in range(0,4):
            result.append([{'sort_key': self.columns[i].header, 'html': self.columns[i].header,
                            'tooltip': self.get_tooltip(MOTHER_INDICATOR_TOOLTIPS['postnatal_care_details'], self.columns[i].slug)},
                           {'sort_key': self.data[self.columns[i].slug], 'html': self.data[self.columns[i].slug]},
                           {'sort_key': self.data[self.columns[i + 4].slug], 'html': self.data[self.columns[i + 4].slug],
                            'tooltip': self.get_tooltip(MOTHER_INDICATOR_TOOLTIPS['postnatal_care_details'], self.columns[i+4].slug)},
                           {'sort_key': self.percent_fn(self.data[self.columns[i + 4].slug], self.data[self.columns[i].slug]),
                            'html': self.percent_fn(self.data[self.columns[i + 4].slug], self.data[self.columns[i].slug])}])
        return result

    @property
    def columns(self):
        return [
            DatabaseColumn(
                "PNC in 48 hours",
                CountUniqueColumn('doc_id', alias="pnc_1", filters=self.filters + [EQ('pp_1_done', 'yes')]),
            ),
            DatabaseColumn(
                "PNC in 2-4 days",
                CountUniqueColumn('doc_id', alias="pnc_2", filters=self.filters + [EQ('pp_2_done', 'yes')]),
            ),
            DatabaseColumn(
                "PNC in 5-7",
                CountUniqueColumn('doc_id', alias="pnc_3", filters=self.filters + [EQ('pp_3_done', 'yes')]),
            ),
            DatabaseColumn(
                "PNC in 21-42 days",
                CountUniqueColumn('doc_id', alias="pnc_4", filters=self.filters + [EQ('pp_4_done', 'yes')]),
            ),
            DatabaseColumn(
                "PNC 1 visits Total Eligible",
                CountUniqueColumn('doc_id', alias="pnc_1_eligible",
                                  filters=self.filters + [AND([NOTEQ('delivery_date', 'empty'),
                                                               LTE('delivery_date', 'today')])]),
            ),
            DatabaseColumn("PNC 2 visits Total Eligible",
                CountUniqueColumn('doc_id', alias="pnc_2_eligible",
                                  filters=self.filters + [AND([NOTEQ('delivery_date', 'empty'), LTE('delivery_date', 'today_minus_2')])]),
            ),
            DatabaseColumn("PNC 3 visits Total Eligible",
                CountUniqueColumn('doc_id', alias="pnc_3_eligible",
                                  filters=self.filters + [AND([NOTEQ('delivery_date', 'empty'), LTE('delivery_date', 'today_minus_25')])]),
            ),
            DatabaseColumn("PNC 4 visits Total Eligible",
                CountUniqueColumn('doc_id', alias="pnc_4_eligible",
                                  filters=self.filters + [AND([NOTEQ('delivery_date', 'empty'), LTE('delivery_date', 'today_minus_21')])]),
            )
        ]


class CauseOfMaternalDeaths(BaseSqlData):
    table_name = "fluff_WorldVisionMotherFluff"
    slug = 'Cause_of_maternal_deaths'
    title = 'Cause of Maternal Deaths'
    show_total = True
    total_row_name = "Total Mother Deaths"
    show_charts = True
    chart_x_label = ''
    chart_y_label = ''
    chart_title = 'Mother Deaths'
    table_only = True

    @property
    def group_by(self):
        return ['cause_of_death_maternal']

    @property
    def rows(self):
        from custom.world_vision import MOTHER_DEATH_MAPPING
        return self._get_rows(MOTHER_DEATH_MAPPING, super(CauseOfMaternalDeaths, self).rows)

    @property
    def filters(self):
        filter = super(CauseOfMaternalDeaths, self).filters[1:]
        filter.append(EQ('reason_for_mother_closure', 'death'))
        if 'strsd' in self.config:
            filter.append(GTE('date_of_mother_death', 'strsd'))
        if 'stred' in self.config:
            filter.append(LTE('date_of_mother_death', 'stred'))
        return filter

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Maternal Death'), DataTablesColumn('Number'),
                                  DataTablesColumn('Percentage')])

    @property
    def columns(self):
        return [
            DatabaseColumn("Reason", SimpleColumn('cause_of_death_maternal')),
            DatabaseColumn("Number", CountUniqueColumn('doc_id'))
        ]


class FamilyPlanningMethods(BaseSqlData):
    table_name = "fluff_WorldVisionMotherFluff"
    slug = 'family_planning_methods'
    title = 'Family Planning Methods'
    show_total = True
    total_row_name = "Total Families who reported using Family Planning"
    show_charts = True
    chart_title = 'Family Planning Methods'
    chart_x_label = ''
    chart_y_label = ''

    @property
    def group_by(self):
        return ['fp_method']

    @property
    def rows(self):
        from custom.world_vision import FAMILY_PLANNING_METHODS
        return self._get_rows(FAMILY_PLANNING_METHODS, super(FamilyPlanningMethods, self).rows)

    @property
    def filters(self):
        filter = super(FamilyPlanningMethods, self).filters
        filter.append(NOTEQ('fp_method', 'empty'))
        return filter

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Method'), DataTablesColumn('Number'), DataTablesColumn('Percentage')])

    @property
    def columns(self):
        return [
            DatabaseColumn("Method", SimpleColumn('fp_method')),
            DatabaseColumn("Number", CountUniqueColumn('doc_id'))
        ]


class DeliveryPlaceDetailsExtended(DeliveryPlaceDetails):
    show_charts = True
    chart_title = 'Delivery Place'
    chart_x_label = ''
    chart_y_label = ''
    slug = 'delivery_place_details_extended'

    @property
    def columns(self):
        columns = super(DeliveryPlaceDetailsExtended, self).columns
        additional_columns = [
            DatabaseColumn("Home deliveries",
                           CountUniqueColumn('doc_id', alias="home_deliveries",
                                             filters=self.filters + [OR([EQ('place_of_birth', 'home'),
                                                                         EQ('place_of_birth', 'on_route')])])),
            DatabaseColumn("Other places",
                           CountUniqueColumn('doc_id', alias="other_places",
                                             filters=self.filters + [OR([EQ('place_of_birth', 'empty'),
                                                                         EQ('place_of_birth', 'other')])]))
        ]
        columns.extend(additional_columns)
        return columns


class DeliveryPlaceMotherDetails(DeliveryPlaceDetails):

    title = ''
    show_charts = True
    chart_x_label = ''
    chart_y_label = ''
    chart_title = 'Delivery Place Mother'
    slug = 'delivery_place_mother_details'
    accordion_start = False
    accordion_end = False

    @property
    def columns(self):
        return [
            DatabaseColumn("Total Deliveries (with/without outcome)",
                           CountUniqueColumn('doc_id', alias="total_delivery", filters=self.filters),
            ),
            DatabaseColumn("Normal deliveries",
                           CountUniqueColumn('doc_id', alias="normal_deliveries",
                                             filters=self.filters + [EQ('type_of_delivery', 'normal_delivery')])),
            DatabaseColumn("Caesarean deliveries",
                           CountUniqueColumn('doc_id', alias="caesarean_deliveries",
                                             filters=self.filters + [EQ('type_of_delivery', 'cesarean_delivery')])),
            DatabaseColumn("Delivery type unknown",
                           CountUniqueColumn('doc_id', alias="unknown",
                                             filters=self.filters + [OR([EQ('type_of_delivery', 'empty'),
                                                                         EQ('type_of_delivery', 'unknown_delivery')])]))
        ]

    @property
    def rows(self):
        return super(DeliveryPlaceMotherDetails, self).rows[1:]


class NumberOfPNCVisits(BaseSqlData):
    table_name = "fluff_WorldVisionMotherFluff"
    slug = 'number_of_pnc_visits'
    title = ''
    show_total = True
    total_row_name = "Total mothers who delivered more than 42 days ago"
    show_charts = True
    chart_title = 'PNC Visits'
    chart_x_label = ''
    chart_y_label = ''
    accordion_start = False
    accordion_end = True

    @property
    def rows(self):
        result = []
        rows = super(NumberOfPNCVisits, self).rows
        counter = {k: 0 for k in range(0, 5)}

        for row in rows:
            counter[row[-1]['html']] += 1

        for k, v in counter.iteritems():
            percent = self.percent_fn(len(rows), v)
            result.append([{'sort_key': "Mothers with %d PNC visits within 42 days of delivery" % k,
                            'html': "Mothers with %d PNC visits within 42 days of delivery" % k},
                           {'sort_key': v, 'html': v},
                           {'sort_key': 'percentage', 'html': percent}])
        return result

    @property
    def group_by(self):
        return ['doc_id', 'pp_1_done', 'pp_2_done', 'pp_3_done', 'pp_4_done']

    @property
    def filters(self):
        filters = super(NumberOfPNCVisits, self).filters[1:]
        filters.append(AND([NOTEQ('delivery_date', 'empty'), LTE('delivery_date', 'today_minus_42')]))
        return filters

    @property
    def columns(self):
        def format_pnc_count(*args):
            return sum([1 if arg == 'yes' else 0 for arg in args])

        return [
            DatabaseColumn("PP 1", SimpleColumn('pp_1_done', alias='pp_1_done')),
            DatabaseColumn("PP 2", SimpleColumn('pp_2_done', alias='pp_2_done')),
            DatabaseColumn("PP 3", SimpleColumn('pp_3_done', alias='pp_3_done')),
            DatabaseColumn("PP 4", SimpleColumn('pp_4_done', alias='pp_4_done')),
            AggregateColumn('PNC Count', format_pnc_count,
                            [AliasColumn('pp_1_done'), AliasColumn('pp_2_done'), AliasColumn('pp_3_done'),
                             AliasColumn('pp_4_done')])]
