from __future__ import absolute_import
from sqlagg import CountUniqueColumn
from sqlagg.filters import LTE, AND, EQ, OR, GTE
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.sqlreport import DatabaseColumn
from custom.world_vision.sqldata import BaseSqlData
from six.moves import range


class AnteNatalCareServiceOverview(BaseSqlData):
    table_name = "fluff_WorldVisionMotherFluff"
    slug = 'ante_natal_care_service_overview'
    title = 'Ante Natal Care Service Overview'

    @property
    def filters(self):
        filter = super(AnteNatalCareServiceOverview, self).filters
        filter.append(EQ('mother_state', 'pregnant_mother_type'))
        return filter

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Entity'), DataTablesColumn('Number'),
                                  DataTablesColumn('Total Eligible'), DataTablesColumn('Percentage')])

    @property
    def rows(self):
        from custom.world_vision import MOTHER_INDICATOR_TOOLTIPS
        result = [[{'sort_key': self.columns[0].header, 'html': self.columns[0].header},
                  {'sort_key': self.data[self.columns[0].slug], 'html': self.data[self.columns[0].slug]},
                  {'sort_key': 'n/a', 'html': 'n/a'},
                  {'sort_key': 'n/a', 'html': 'n/a'}]]
        return result

    @property
    def columns(self):
        return [

            DatabaseColumn("Total pregnant", CountUniqueColumn('doc_id', alias="total_pregnant")),
            DatabaseColumn("ANC3", CountUniqueColumn('doc_id', alias="anc_3",
                                                     filters=self.filters + [EQ('anc_3', 'yes')])),
            DatabaseColumn("TT Completed (TT2 or Booster)",
                           CountUniqueColumn('doc_id', alias="tt_completed",
                                             filters=self.filters + [OR([EQ('tt_2', 'yes'),
                                                                         EQ('tt_booster', 'yes')])])),
            DatabaseColumn("Taking IFA tablets",
                           CountUniqueColumn('doc_id', alias="ifa_tablets",
                                             filters=self.filters + [EQ('iron_folic', 'yes')])),
            DatabaseColumn("Completed 100 IFA tablets",
                           CountUniqueColumn('doc_id', alias="100_tablets",
                                             filters=self.filters[1:-1] + [AND([EQ('completed_100_ifa', 'yes'),
                                                                                GTE('delivery_date', 'strsd'),
                                                                                LTE('delivery_date', 'stred')])])),
            DatabaseColumn("ANC3 Total Eligible",
                           CountUniqueColumn('doc_id', alias="anc_3_eligible",
                                             filters=self.filters + [AND([EQ('anc_2', 'yes'),
                                                                          LTE('edd', 'today_plus_56')])])),
            DatabaseColumn("TT Completed (TT2 or Booster) Total Eligible",
                           CountUniqueColumn('doc_id', alias="tt_completed_eligible",
                                             filters=self.filters + [OR([EQ('tt_1', 'yes'),
                                                                         EQ('previous_tetanus', 'yes')])])),
            DatabaseColumn("Taking IFA tablets Total Eligible", CountUniqueColumn('doc_id',
                                                                                  alias="ifa_tablets_eligible")),
            DatabaseColumn("Completed 100 IFA tablets Total Eligible",
                           CountUniqueColumn('doc_id', alias="100_tablets_eligible",
                                             filters=self.filters[1:-1] + [AND([GTE('delivery_date', 'strsd'),
                                                                               LTE('delivery_date', 'stred')])])),
        ]


class DeliveryPlaceDetails(BaseSqlData):
    table_name = "fluff_WorldVisionMotherFluff"
    slug = 'delivery_place_details'
    title = 'Delivery Details'
    accordion_start = True
    accordion_end = False

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Entity'), DataTablesColumn('Number'), DataTablesColumn('Percentage')])

    @property
    def filters(self):
        filter =  super(DeliveryPlaceDetails, self).filters[1:]
        if 'strsd' in self.config:
            filter.append(GTE('delivery_date', 'strsd'))
        if 'stred' in self.config:
            filter.append(LTE('delivery_date', 'stred'))
        return filter

    @property
    def columns(self):
        return [
            DatabaseColumn("Total Deliveries (with/without outcome)",
                CountUniqueColumn('doc_id', alias="total_delivery", filters=self.filters),
            ),
            DatabaseColumn("Institutional deliveries",
                CountUniqueColumn('doc_id', alias="institutional_deliveries",
                                  filters=self.filters + [OR([EQ('place_of_birth', 'health_center'), EQ('place_of_birth', "hospital")])]
                )
            )
        ]

    @property
    def rows(self):
        from custom.world_vision import MOTHER_INDICATOR_TOOLTIPS
        result = []
        for idx, column in enumerate(self.columns):
            if idx == 0:
                percent = 'n/a'
            else:
                percent = self.percent_fn(self.data['total_delivery'], self.data[column.slug])

            result.append([{'sort_key': column.header, 'html': column.header,
                            'tootip': self.get_tooltip(MOTHER_INDICATOR_TOOLTIPS['delivery_details'], column.slug)},
                           {'sort_key': self.data[column.slug], 'html': self.data[column.slug]},
                           {'sort_key': 'percentage', 'html': percent}]
            )
        return result


class ImmunizationOverview(BaseSqlData):
    table_name = "fluff_WorldVisionChildFluff"
    slug = 'immunization_overview'
    title = 'Immunization Overview (0 - 2 yrs)'
    show_charts = True
    chart_x_label = ''
    chart_y_label = ''
    chart_title = 'Child Immunisation and Vitamin A'
    chart_only = True

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Vaccine'), DataTablesColumn('Number'),
                                  DataTablesColumn('Total Eligible'), DataTablesColumn('Percentage'),
                                  DataTablesColumn('Dropout Number'), DataTablesColumn('Dropout Percentage')])

    @property
    def rows(self):
        from custom.world_vision import CHILD_INDICATOR_TOOLTIPS
        result = []
        rg = len(self.columns) / 2
        for i in range(0, rg):
            dropout = self.data[self.columns[i + rg].slug] - self.data[self.columns[i].slug]
            result.append([{'sort_key': self.columns[i].header, 'html': self.columns[i].header,
                            'tooltip': self.get_tooltip(CHILD_INDICATOR_TOOLTIPS['immunization_details'], self.columns[i].slug)},
                           {'sort_key': self.data[self.columns[i].slug], 'html': self.data[self.columns[i].slug]},
                           {'sort_key': self.data[self.columns[i + rg].slug], 'html': self.data[self.columns[i + rg].slug],
                            'tooltip': self.get_tooltip(CHILD_INDICATOR_TOOLTIPS['immunization_details'], self.columns[i + rg].slug)},
                           {'sort_key': self.percent_fn(self.data[self.columns[i + rg].slug], self.data[self.columns[i].slug]),
                            'html': self.percent_fn(self.data[self.columns[i + rg].slug], self.data[self.columns[i].slug])},
                           {'sort_key': dropout, 'html': dropout},
                           {'sort_key': self.percent_fn(self.data[self.columns[i + rg].slug], dropout),
                            'html': self.percent_fn(self.data[self.columns[i + rg].slug], dropout)}
            ])
        return result

    @property
    def columns(self):
        return [
            DatabaseColumn("BCG",
                CountUniqueColumn('doc_id', alias="bcg", filters=self.filters + [EQ('bcg', 'yes')])
            ),
            DatabaseColumn("OPV3",
                CountUniqueColumn('doc_id', alias="opv3", filters=self.filters + [EQ('opv3', 'yes')])
            ),
            DatabaseColumn("HEP3",
                CountUniqueColumn('doc_id', alias="hep3", filters=self.filters + [EQ('hepb3', 'yes')])
            ),
            DatabaseColumn("DPT3",
                CountUniqueColumn('doc_id', alias="dpt3", filters=self.filters + [EQ('dpt3', 'yes')])
            ),
            DatabaseColumn("Measles",
                CountUniqueColumn('doc_id', alias="measles", filters=self.filters + [EQ('measles', 'yes')])
            ),
            DatabaseColumn("Fully Immunized in 1st year",
                CountUniqueColumn('doc_id', alias="fully_immunized",
                                  filters=self.filters + [AND([EQ('bcg', 'yes'), EQ('opv0', 'yes'), EQ('hepb0', 'yes'),
                                  EQ('opv1', 'yes'), EQ('hepb1', 'yes'), EQ('dpt1', 'yes'), EQ('opv2', 'yes'), EQ('hepb2', 'yes'),
                                  EQ('dpt2', 'yes'), EQ('opv3', 'yes'), EQ('hepb3', 'yes'), EQ('dpt3', 'yes'), EQ('measles', 'yes')])])
            ),
            DatabaseColumn("DPT-OPT Booster",
                CountUniqueColumn('doc_id', alias="dpt_opv_booster", filters=self.filters + [EQ('dpt_opv_booster', 'yes')])
            ),
            DatabaseColumn("VitA3",
                CountUniqueColumn('doc_id', alias="vita3", filters=self.filters + [EQ('vita3', 'yes')])
            ),
            DatabaseColumn("BCG Total Eligible",
                CountUniqueColumn('doc_id', alias="bcg_eligible"),
            ),
            DatabaseColumn("OPV3 Total Eligible",
                CountUniqueColumn('doc_id', alias="opv3_eligible", filters=self.filters + [LTE('dob', 'today_minus_106')])
            ),
            DatabaseColumn("HEP3 Total Eligible",
                CountUniqueColumn('doc_id', alias="hep3_eligible", filters=self.filters + [LTE('dob', 'today_minus_106')])
            ),
            DatabaseColumn("DPT3 Total Eligible",
                CountUniqueColumn('doc_id', alias="dpt3_eligible", filters=self.filters + [LTE('dob', 'today_minus_106')])
            ),
            DatabaseColumn("Measles Total Eligible",
                CountUniqueColumn('doc_id', alias="measles_eligible", filters=self.filters + [LTE('dob', 'today_minus_273')])
            ),
            DatabaseColumn("Fully Immunized Total Eligible",
                CountUniqueColumn('doc_id', alias="fully_immunized_eligible", filters=self.filters + [LTE('dob', 'today_minus_273')])
            ),
            DatabaseColumn("DPT-OPT Booster Total Eligible",
                CountUniqueColumn('doc_id', alias="dpt_opv_booster_eligible", filters=self.filters + [LTE('dob', 'today_minus_548')])
            ),
            DatabaseColumn("VitA3 Total Eligible",
                CountUniqueColumn('doc_id', alias="vita3_eligible", filters=self.filters + [LTE('dob', 'today_minus_700')])
            )
        ]
