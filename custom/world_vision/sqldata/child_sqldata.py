import calendar
from sqlagg import CountUniqueColumn
from sqlagg.columns import SimpleColumn
from sqlagg.filters import LT, LTE, AND, GTE, GT, EQ, NOTEQ, OR
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.sqlreport import DatabaseColumn, calculate_total_row
from custom.world_vision.custom_queries import CustomMedianColumn, MeanColumnWithCasting
from custom.world_vision.sqldata import BaseSqlData
from custom.world_vision.sqldata.main_sqldata import ImmunizationOverview
from custom.world_vision.sqldata.mother_sqldata import MotherRegistrationDetails, ClosedMotherCasesBreakdown


class ChildRegistrationDetails(MotherRegistrationDetails):
    table_name = "fluff_WorldVisionChildFluff"
    slug = 'child_registration_details'
    title = 'Child Registration Details'

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Total children registered ever",
                CountUniqueColumn('doc_id',
                    alias="total",
                    filters=self.filters
                )
            ),
        ]
        if 'startdate' not in self.config and 'enddate' not in self.config:
            columns.extend([
                DatabaseColumn("Total open children cases",
                    CountUniqueColumn('doc_id',
                        alias="opened",
                        filters=self.filters + [EQ('closed_on', 'empty')]
                    )
                ),
                DatabaseColumn("Total closed children cases",
                    CountUniqueColumn('doc_id',
                        alias="closed",
                        filters=self.filters +  [NOTEQ('closed_on', 'empty')]
                    )
                ),
                DatabaseColumn("New registrations during last 30 days",
                        CountUniqueColumn('doc_id',
                            alias="new_registrations",
                            filters=self.filters + [AND([LTE('opened_on', "last_month"), GTE('opened_on', "today")])]
                        )
                )
            ])
        else:
            columns.extend([
                DatabaseColumn("Children cases open at end of time period",
                    CountUniqueColumn('doc_id',
                        alias="opened",
                        filters=self.filters + [AND([LTE('opened_on', "stred"), OR([EQ('closed_on', 'empty'), GT('closed_on', "stred")])])]
                    )
                ),
                DatabaseColumn("Children cases closed during the time period",
                    CountUniqueColumn('doc_id',
                        alias="closed",
                        filters=self.filters + [AND([NOTEQ('closed_on', 'empty'), LTE('opened_on', "stred"), LTE('closed_on', "stred")])]
                    )
                ),
                DatabaseColumn("Total children followed during the time period",
                    CountUniqueColumn('doc_id',
                        alias="followed",
                        filters=self.filters + [AND([LTE('opened_on', "stred"), OR([EQ('closed_on', 'empty'), GTE('closed_on', "strsd")])])]
                    )
                ),
                DatabaseColumn("New registrations during time period",
                    CountUniqueColumn('doc_id',
                        alias="new_registrations",
                        filters=self.filters + [AND([LTE('opened_on', "stred"), GTE('opened_on', "strsd")])]
                    )
                )
            ])
        return columns

class ClosedChildCasesBreakdown(ClosedMotherCasesBreakdown):
    table_name = "fluff_WorldVisionChildFluff"
    slug = 'closed_child_cases_breakdown'
    title = 'Closed Child Cases Breakdown'
    total_row_name = "Children cases closed during the time period"

    @property
    def group_by(self):
        return ['reason_for_child_closure']

    @property
    def filters(self):
        filter = super(ClosedMotherCasesBreakdown, self).filters
        filter.append(NOTEQ('reason_for_child_closure', 'empty'))
        return filter

    @property
    def columns(self):
        return [
            DatabaseColumn("Reason for closure", SimpleColumn('reason_for_child_closure')),
            DatabaseColumn("Number", CountUniqueColumn('doc_id'))
        ]


class ChildrenDeaths(BaseSqlData):
    table_name = "fluff_WorldVisionChildFluff"
    slug = 'children_deaths'
    title = 'Children Death Details'
    total_row_name = "Total Deaths"
    show_total = True
    show_charts = True
    chart_x_label = ''
    chart_y_label = ''

    @property
    def group_by(self):
        return ['type_of_child_death']

    @property
    def rows(self):
        from custom.world_vision import CHILD_DEATH_TYPE
        return self._get_rows(CHILD_DEATH_TYPE, super(ChildrenDeaths, self).rows)

    @property
    def filters(self):
        filter = super(ChildrenDeaths, self).filters
        filter.append(EQ('reason_for_child_closure', 'death'))
        return filter

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Children Death Type'), DataTablesColumn('Number'), DataTablesColumn('Percentage')])

    @property
    def columns(self):
        return [
            DatabaseColumn("Reason", SimpleColumn('type_of_child_death')),
            DatabaseColumn("Number", CountUniqueColumn('doc_id'))
        ]

class ChildrenDeathDetails(BaseSqlData):
    table_name = "fluff_WorldVisionChildFluff"
    slug = 'children_death_details'
    title = ''
    show_total = True
    total_row_name = "Total Deaths"
    show_charts = True
    chart_x_label = ''
    chart_y_label = ''

    @property
    def group_by(self):
        return ['cause_of_death_child']

    @property
    def rows(self):
        from custom.world_vision import CHILD_CAUSE_OF_DEATH
        return self._get_rows(CHILD_CAUSE_OF_DEATH, super(ChildrenDeathDetails, self).rows)

    @property
    def filters(self):
        filter = super(ChildrenDeathDetails, self).filters
        filter.extend([EQ('reason_for_child_closure', 'death'), NOTEQ('cause_of_death_child', 'empty')])
        return filter

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Cause of death'), DataTablesColumn('Number'), DataTablesColumn('Percentage')])

    @property
    def columns(self):
        return [
            DatabaseColumn("Cause of death", SimpleColumn('cause_of_death_child')),
            DatabaseColumn("Number", CountUniqueColumn('doc_id')),
        ]


class ChildrenDeathsByMonth(BaseSqlData):

    table_name = "fluff_WorldVisionChildFluff"
    slug = 'children_death_by_month'
    title = ''
    show_charts = True
    chart_x_label = ''
    chart_y_label = ''

    @property
    def group_by(self):
        return ['month_of_death', 'year_of_death']

    @property
    def filters(self):
        filters = super(ChildrenDeathsByMonth, self).filters
        filters.extend([NOTEQ('month_of_death', 'empty')])
        return filters

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Month'), DataTablesColumn('Deaths'), DataTablesColumn('Percentage')])

    @property
    def rows(self):
        rows = sorted(super(ChildrenDeathsByMonth, self).rows, key=lambda r: (r[1], r[0]))
        sum_of_deaths = 0
        for row in rows:
            sum_of_deaths += row[2]['sort_key']
            row[0] = calendar.month_name[int(row[0])]
            del row[1]

        for row in rows:
            row.append({'sort_key': self.percent_fn(sum_of_deaths, row[1]['sort_key']),
                        'html': self.percent_fn(sum_of_deaths, row[1]['sort_key'])})
        return rows

    @property
    def columns(self):
        return [DatabaseColumn("Month", SimpleColumn('month_of_death')),
                DatabaseColumn("Year", SimpleColumn('year_of_death')),
                DatabaseColumn("Number", CountUniqueColumn('doc_id'))]


class NutritionMeanMedianBirthWeightDetails(BaseSqlData):
    table_name = "fluff_WorldVisionChildFluff"
    slug = 'children_birth_weights_1'
    title = 'Nutrition Details'

    @property
    def filters(self):
        filters = super(NutritionMeanMedianBirthWeightDetails, self).filters
        filters.append(NOTEQ('weight_birth', 'empty'))
        return filters

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Entity'), DataTablesColumn('Mean'), DataTablesColumn('Median')])

    @property
    def columns(self):
        return [
            DatabaseColumn("Median Birth Weight",
                MeanColumnWithCasting('weight_birth', alias='mean_birth_weight')
            ),
            DatabaseColumn("Median Birth Weight",
                CustomMedianColumn('weight_birth', alias='median_birth_weight')
            )
        ]

    @property
    def rows(self):
        return [['Birth Weight (kg)',
                 "%.2f" % (self.data['mean_birth_weight'] if self.data['mean_birth_weight'] else 0),
                 "%.2f" % (self.data['median_birth_weight'] if self.data['mean_birth_weight'] else 0)]
        ]

class NutritionBirthWeightDetails(BaseSqlData):
    table_name = "fluff_WorldVisionChildFluff"
    slug = 'children_birth_details_2'
    title = ''
    show_charts = True
    chart_x_label = ''
    chart_y_label = ''

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Entity'), DataTablesColumn('Number'), DataTablesColumn('Percentage')])

    @property
    def rows(self):
        result = []
        for idx, column in enumerate(self.columns):
            if idx == 0:
                percent = 'n/a'
            else:
                percent = self.percent_fn(self.data['total_birthweight_known'], self.data[column.slug])

            result.append([{'sort_key': column.header, 'html': column.header},
                           {'sort_key': self.data[column.slug], 'html': self.data[column.slug]},
                           {'sort_key': 'percentage', 'html': percent}]
            )
        return result

    @property
    def columns(self):
        columns = [
            DatabaseColumn("Total children with with birthweight known",
                CountUniqueColumn('doc_id',
                    alias="total_birthweight_known",
                    filters=self.filters + [NOTEQ('weight_birth', 'empty')]
                )
            ),
        ]
        columns.extend([
            DatabaseColumn("Birthweight < 2.5 kg",
                CountUniqueColumn('doc_id',
                    alias="total_birthweight_lt_25",
                    filters=self.filters + [AND([LT('weight_birth', 'weight_birth_25'), NOTEQ('weight_birth', 'empty')])]
                )
            ),
            DatabaseColumn("Birthweight >= 2.5 kg",
                CountUniqueColumn('doc_id',
                    alias="total_birthweight_gte_25",
                    filters=self.filters + [AND([GTE('weight_birth', 'weight_birth_25'), NOTEQ('weight_birth', 'empty')])]
                )
            )
        ])
        return columns


class NutritionFeedingDetails(BaseSqlData):
    table_name = "fluff_WorldVisionChildFluff"
    slug = 'children_feeding_details'
    title = ''

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Feeding type'), DataTablesColumn('Number'), DataTablesColumn('Total Eligible'), DataTablesColumn('Percentage')])

    @property
    def rows(self):
        result = []
        for i in range(0,4):
            result.append([{'sort_key': self.columns[2*i].header, 'html': self.columns[2*i].header},
                           {'sort_key': self.data[self.columns[2*i].slug], 'html': self.data[self.columns[2*i].slug]},
                           {'sort_key': self.data[self.columns[2*i+1].slug], 'html': self.data[self.columns[2*i + 1].slug]},
                           {'sort_key': self.percent_fn(self.data[self.columns[2*i + 1].slug], self.data[self.columns[2*i].slug]),
                           'html': self.percent_fn(self.data[self.columns[2*i + 1].slug], self.data[self.columns[2*i].slug])}

            ])
        return result

    @property
    def columns(self):
        return [
            DatabaseColumn("Colostrum feeding",
                CountUniqueColumn('doc_id',
                    alias="colostrum_feeding",
                    filters=self.filters + [EQ('breastfeed_1_hour', 'yes')]
                )
            ),
            DatabaseColumn("Colostrum feeding Total Eligible",
                CountUniqueColumn('doc_id',
                    alias="colostrum_feeding_total_eligible",
                    filters=self.filters + [NOTEQ('breastfeed_1_hour', 'empty')]
                )
            ),

            DatabaseColumn("Exclusive Breastfeeding (EBF)",
                CountUniqueColumn('doc_id',
                    alias="exclusive_breastfeeding",
                    filters=self.filters + [AND([EQ('exclusive_breastfeeding', "yes"), LTE('dob', "days_183")])]
                )
            ),
            DatabaseColumn("Exclusive Breastfeeding (EBF) Total Eligible",
                CountUniqueColumn('doc_id',
                    alias="exclusive_breastfeeding_total_eligible",
                    filters=self.filters + [GTE('dob', 'days_183')]
                )
            ),

            DatabaseColumn("Supplementary feeding",
                CountUniqueColumn('doc_id',
                    alias="supplementary_feeding",
                    filters=self.filters + [AND([EQ('supplementary_feeding_baby', 'yes'), GTE('dob', 'days_182')])]
                )
            ),
            DatabaseColumn("Supplementary feeding Total Eligible",
                CountUniqueColumn('doc_id',
                    alias="supplementary_feeding_total_eligible",
                    filters=self.filters + [GTE('dob', 'days_182')]
                )
            ),

            DatabaseColumn("Complementary feeding",
                CountUniqueColumn('doc_id',
                    alias="complementary_feeding",
                    filters=self.filters + [AND([EQ('comp_breastfeeding', 'yes'), LTE('dob', 'days_183'), GTE('dob', 'days_730')])]
                )
            ),
            DatabaseColumn("Complementary feeding Total Eligible",
                CountUniqueColumn('doc_id',
                    alias="complementary_feeding_total_eligible",
                    filters=self.filters + [AND([LTE('dob', 'days_183'), GTE('dob', 'days_730')])]
                )
            )
        ]


class ChildHealthIndicators(BaseSqlData):
    table_name = "fluff_WorldVisionChildFluff"
    slug = 'Child_health_indicators'
    title = 'Child Health Indicators'

    @property
    def rows(self):
        result = [[{'sort_key': self.columns[0].header, 'html': self.columns[0].header},
                  {'sort_key': self.data[self.columns[0].slug], 'html': self.data[self.columns[0].slug]}],
                  [{'sort_key': self.columns[1].header, 'html': self.columns[1].header},
                  {'sort_key': self.data[self.columns[1].slug], 'html': self.data[self.columns[1].slug]}]]
        for i in range(2,4):
            result.append([{'sort_key': self.columns[i].header, 'html': self.columns[i].header},
                           {'sort_key': self.data[self.columns[i].slug], 'html': self.data[self.columns[i].slug]},
                           {'sort_key': self.percent_fn(self.data[self.columns[1].slug], self.data[self.columns[i].slug]),
                            'html': self.percent_fn(self.data[self.columns[1].slug], self.data[self.columns[i].slug])}])
        return result

    @property
    def columns(self):
        return [
            DatabaseColumn("ARI (Pneumonia) cases",
                CountUniqueColumn('doc_id', alias="ari_cases", filters=self.filters + [EQ('pneumonia_since_last_visit', 'yes')])
            ),
            DatabaseColumn("Diarrhea cases",
                CountUniqueColumn('doc_id', alias="diarrhea_cases", filters=self.filters + [EQ('has_diarrhea_since_last_visit', 'yes')])
            ),
            DatabaseColumn("ORS given during diarrhea",
                CountUniqueColumn('doc_id', alias="ors",
                                  filters=self.filters + [AND([EQ('dairrhea_treated_with_ors', 'yes'), EQ('has_diarrhea_since_last_visit', 'yes')])])
            ),
            DatabaseColumn("Zinc given during diarrhea",
                CountUniqueColumn('doc_id', alias="zinc",
                                  filters=self.filters + [AND([EQ('dairrhea_treated_with_zinc', 'yes'), EQ('has_diarrhea_since_last_visit', 'yes')])])
            )
        ]


class ImmunizationDetailsFirstYear(ImmunizationOverview):
    title = 'Immunization Overview (0 - 1 yrs)'

    @property
    def columns(self):
        columns = super(ImmunizationDetailsFirstYear, self).columns
        del columns[6:8]
        del columns[-2:]
        cols1 = [
            DatabaseColumn("OPV0",
                CountUniqueColumn('doc_id', alias="opv0", filters=self.filters + [EQ('opv0', 'yes')])
            ),
            DatabaseColumn("HEP0",
                CountUniqueColumn('doc_id', alias="hep0", filters=self.filters + [EQ('hepb0', 'yes')])
            ),
            DatabaseColumn("OPV1",
                CountUniqueColumn('doc_id', alias="opv1", filters=self.filters + [EQ('opv1', 'yes')])
            ),
            DatabaseColumn("HEP1",
                CountUniqueColumn('doc_id', alias="hep1", filters=self.filters + [EQ('hepb1', 'yes')])
            ),
            DatabaseColumn("DPT1",
                CountUniqueColumn('doc_id', alias="dpt1", filters=self.filters + [EQ('dpt1', 'yes')])
            ),
            DatabaseColumn("OPV2",
                CountUniqueColumn('doc_id', alias="opv2", filters=self.filters + [EQ('opv2', 'yes')])
            ),
            DatabaseColumn("HEP2",
                CountUniqueColumn('doc_id', alias="hep2", filters=self.filters + [EQ('hepb2', 'yes')])
            ),
            DatabaseColumn("DPT2",
                CountUniqueColumn('doc_id', alias="dpt2", filters=self.filters + [EQ('dpt2', 'yes')])
            ),
        ]
        cols2 = [
            DatabaseColumn("OPV0 Total Eligible",
                CountUniqueColumn('doc_id', alias="opv0_eligible", filters=self.filters)
            ),
            DatabaseColumn("HEP0 Total Eligible",
                CountUniqueColumn('doc_id', alias="hep0_eligible", filters=self.filters)
            ),
            DatabaseColumn("OPV1 Total Eligible",
                CountUniqueColumn('doc_id', alias="opv1_eligible", filters=self.filters + [LTE('dob', 'days_40')])
            ),
            DatabaseColumn("HEP1 Total Eligible",
                CountUniqueColumn('doc_id', alias="hep1_eligible", filters=self.filters + [LTE('dob', 'days_40')])
            ),
            DatabaseColumn("DPT1 Total Eligible",
                CountUniqueColumn('doc_id', alias="dpt1_eligible", filters=self.filters + [LTE('dob', 'days_40')])
            ),
            DatabaseColumn("OPV2 Total Eligible",
                CountUniqueColumn('doc_id', alias="opv2_eligible", filters=self.filters + [LTE('dob', 'days_75')])
            ),
            DatabaseColumn("HEP2 Total Eligible",
                CountUniqueColumn('doc_id', alias="hep2_eligible", filters=self.filters + [LTE('dob', 'days_75')])
            ),
            DatabaseColumn("DPT2 Total Eligible",
                CountUniqueColumn('doc_id', alias="dpt2_eligible", filters=self.filters + [LTE('dob', 'days_75')])
            )
        ]
        return columns[:1] + cols1 + columns[1:-5] + cols2 + columns[-5:]

class ImmunizationDetailsSecondYear(ImmunizationOverview):
    title = 'Immunization Overview (1 - 2 yrs)'

    @property
    def columns(self):
        return [
            DatabaseColumn("VitA1",
                CountUniqueColumn('doc_id', alias="vita1", filters=self.filters + [EQ('vita1', 'yes')])
            ),
            DatabaseColumn("VitA2",
                CountUniqueColumn('doc_id', alias="vita2", filters=self.filters + [EQ('vita2', 'yes')])
            ),
            DatabaseColumn("DPT-OPT Booster",
                CountUniqueColumn('doc_id', alias="dpt_opv_booster", filters=self.filters + [EQ('dpt_opv_booster', 'yes')])
            ),
            DatabaseColumn("VitA3",
                CountUniqueColumn('doc_id', alias="vita3", filters=self.filters + [EQ('vita3', 'yes')])
            ),
            DatabaseColumn("VitA1 Total Eligible",
                CountUniqueColumn('doc_id', alias="vita1_eligible", filters=self.filters + [LTE('dob', 'days_273')])
            ),
            DatabaseColumn("VitA2 Total Eligible",
                CountUniqueColumn('doc_id', alias="vita2_eligible", filters=self.filters + [LTE('dob', 'days_547')])
            ),
            DatabaseColumn("DPT-OPT Booster Total Eligible",
                CountUniqueColumn('doc_id', alias="dpt_opv_booster_eligible", filters=self.filters + [LTE('dob', 'days_548')])
            ),
            DatabaseColumn("VitA3 Total Eligible",
                CountUniqueColumn('doc_id', alias="vita3_eligible", filters=self.filters + [LTE('dob', 'days_700')])
            )

        ]


class ChildDeworming(BaseSqlData):
    table_name = "fluff_WorldVisionChildFluff"
    slug = 'children_deworming'
    title = 'Child Deworming'

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Entity'), DataTablesColumn('Number'), DataTablesColumn('Total Eligible'), DataTablesColumn('Percentage')])

    @property
    def rows(self):
        return [[{'sort_key': self.columns[0].header, 'html': self.columns[0].header},
               {'sort_key': self.data[self.columns[0].slug], 'html': self.data[self.columns[0].slug]},
               {'sort_key': self.data[self.columns[1].slug], 'html': self.data[self.columns[1].slug]},
               {'sort_key': self.percent_fn(self.data[self.columns[1].slug], self.data[self.columns[0].slug]),
               'html': self.percent_fn(self.data[self.columns[1].slug], self.data[self.columns[0].slug])}
            ]]

    @property
    def columns(self):
        return [
            DatabaseColumn("Deworming dose in last 6 months",
                CountUniqueColumn('doc_id',
                    alias="deworming",
                    filters=self.filters + [EQ('deworm', 'yes')]
                )
            ),
            DatabaseColumn("Deworming Total Eligible",
                CountUniqueColumn('doc_id',
                    alias="deworming_total_eligible",
                    filters=self.filters + [LTE('dob', 'days_365')]
                )
            ),
        ]

class EBFStoppingDetails(BaseSqlData):
    table_name = "fluff_WorldVisionChildFluff"
    slug = 'ebf_stopping_details'
    title = 'EBF Stopping Details'
    show_total = True
    total_row_name = "EBF stopped"

    @property
    def filters(self):
        filters = super(EBFStoppingDetails, self).filters
        filters.append(EQ('exclusive_breastfeeding', 'no'))
        filters.append(LTE('dob', 'days_183'))
        filters.append(NOTEQ('ebf_stop_age_month', 'empty'))
        return filters

    @property
    def rows(self):
        total = sum(v for v in self.data.values())
        result = []
        for column in self.columns:
            percent = self.percent_fn(total, self.data[column.slug])
            result.append([{'sort_key': column.header, 'html': column.header},
                           {'sort_key': self.data[column.slug], 'html': self.data[column.slug]},
                           {'sort_key': 'percentage', 'html': percent}
            ])

        return result

    @property
    def columns(self):
        return [
            DatabaseColumn("EBF stopped between 0-1 month",
                CountUniqueColumn('doc_id', alias="stopped_0_1",
                                  filters=self.filters + [LTE('ebf_stop_age_month', '1')])
            ),
            DatabaseColumn("EBF stopped between 1-3 month",
                CountUniqueColumn('doc_id', alias="stopped_1_3",
                                  filters=self.filters + [AND([GT('ebf_stop_age_month', '1'), LTE('ebf_stop_age_month', '3')])])
            ),
            DatabaseColumn("EBF stopped between 3-5 month",
                CountUniqueColumn('doc_id', alias="stopped_3_5",
                                  filters=self.filters + [AND([GT('ebf_stop_age_month', '3'), LTE('ebf_stop_age_month', '5')])])
            ),
            DatabaseColumn("EBF stopped between 5-6 month",
                CountUniqueColumn('doc_id', alias="stopped_5_6",
                                  filters=self.filters + [AND([GT('ebf_stop_age_month', '5'), LTE('ebf_stop_age_month', '6')])])
            )
        ]
