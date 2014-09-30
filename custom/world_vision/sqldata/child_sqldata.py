from sqlagg import CountUniqueColumn
from sqlagg.columns import SimpleColumn
from sqlagg.filters import LT, LTE, AND, GTE, GT, EQ, NOTEQ, OR
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.sqlreport import DatabaseColumn
from custom.world_vision.custom_queries import CustomMedianColumn, MeanColumnWithCasting
from custom.world_vision.sqldata import BaseSqlData
from custom.world_vision.sqldata.main_sqldata import DeliveryPlaceDetails
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
        #TODO: if date_not_selected:
        if False:
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
                 "%.2f" % (self.data['mean_birth_weight']),
                 "%.2f" % (self.data['median_birth_weight'])]
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


class DeliveryPlaceDetailsExtended(DeliveryPlaceDetails):

    @property
    def columns(self):
        columns = super(DeliveryPlaceDetailsExtended, self).columns
        additional_columns = [
            DatabaseColumn("Home deliveries",
                           CountUniqueColumn('doc_id', alias="home_deliveries",
                                             filters=self.filters + [OR([EQ('place_of_birth', 'home'),
                                                                         EQ('place_of_birth', "on_route")])])),
            DatabaseColumn("Other places",
                           CountUniqueColumn('doc_id', alias="other_places",
                                             filters=self.filters + [OR([EQ('place_of_birth', 'empty'),
                                                                         EQ('place_of_birth', "other")])]))
        ]
        columns.extend(additional_columns)
        return columns