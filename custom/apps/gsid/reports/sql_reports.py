from sqlagg.columns import *
from sqlagg.base import AliasColumn
from sqlagg.filters import *
from sqlalchemy import func
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.reports.basic import Column
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader, DataTablesColumnGroup
from corehq.apps.reports.graph_models import MultiBarChart, LineChart, Axis
from corehq.apps.reports.sqlreport import SqlTabularReport, DatabaseColumn, SummingSqlTabularReport, AggregateColumn
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.standard.inspect import GenericMapReport
from dimagi.utils.decorators.memoized import memoized
from util import get_unique_combinations

from datetime import datetime, timedelta

import hashlib


class GSIDSQLReport(SummingSqlTabularReport, CustomProjectReport, DatespanMixin):
    fields = ['custom.apps.gsid.reports.TestField', 
              'custom.apps.gsid.reports.RelativeDatespanField', 
              'custom.apps.gsid.reports.AsyncClinicField',
              'custom.apps.gsid.reports.AggregateAtField']

    exportable = True
    emailable = True
    table_name = "gsid_patient_summary"
    default_aggregation = "clinic"

    @property
    def diseases(self):
        disease_fixtures = FixtureDataItem.by_data_type(
            self.domain, 
            FixtureDataType.by_domain_tag(self.domain, "diseases").one()
        )
        return [d.fields["disease_id"] for d in disease_fixtures]

    @property
    def test_types(self):
        test_fixtures = FixtureDataItem.by_data_type(
            self.domain, 
            FixtureDataType.by_domain_tag(self.domain, "tests").one()
        )        
        return [t.fields["test_name"] for t in test_fixtures]

    @property
    def filter_values(self):
        ret = dict(
            domain=self.domain,
            startdate=self.datespan.startdate_param_utc,
            enddate=self.datespan.enddate_param_utc,
            male="male",
            female="female",
            positive="POSITIVE"
        )

        DISEASES = self.diseases
        TESTS = self.test_types

        ret.update(zip(DISEASES, DISEASES))
        ret.update(zip(TESTS, TESTS))

        return ret

    @property
    def filters(self):
        return [EQ("domain", "domain"), BETWEEN("date", "startdate", "enddate")] + self.disease_filters

    @property
    def disease_filters(self):
        disease = self.request.GET.get('test_type_disease', '')
        test = self.request.GET.get('test_type_test', '')
        
        disease = disease.split(':') if disease else None
        test = test.split(':') if test else None
        
        filters = []
        if test:
            filters.append(EQ("test_version", test[0]))
        elif disease:
            filters.append(EQ("disease_name", disease[0]))

        return filters

    @property
    @memoized
    def gps_key(self):
        gps_key = "gps"
        agg_at = self.request.GET.get('aggregate_at', None)
        if agg_at and agg_at is not "clinic":
            gps_key = "gps_" + agg_at
        return gps_key

    @property
    def group_by(self):
        return self.place_types + [self.gps_key]

    @property
    def keys(self):
        combos = get_unique_combinations(self.domain, place_types=self.place_types, place=self.selected_fixture())
        for c in combos:
            yield [c[pt] for pt in self.place_types] + [c["gps"]]

    def selected_fixture(self):
        fixture = self.request.GET.get('fixture_id', "")
        return fixture.split(':') if fixture else None

    @property
    @memoized
    def place_types(self):
        opts = ['country', 'province', 'district', 'clinic']
        agg_at = self.request.GET.get('aggregate_at', None)
        agg_at = agg_at if agg_at and opts.index(agg_at) <= opts.index(self.default_aggregation) else self.default_aggregation
        place = self.selected_fixture()
        agg_at = place[0] if place and opts.index(agg_at) < opts.index(place[0]) else agg_at 
        return opts[:opts.index(agg_at) + 1]

    @property
    def common_columns(self):
        columns = []
        for place in self.place_types:
            columns.append(DatabaseColumn(place.capitalize(), SimpleColumn(place)))

        return columns + [DatabaseColumn("gps", SimpleColumn(self.gps_key))]


class GSIDSQLPatientReport(GSIDSQLReport):

    name = "Patient Summary Report"
    slug = "patient_summary_sql"
    section_name = "patient summary"
    
    @property
    def columns(self):
        age_fn = lambda x, y: str(x or "-") + "-" + str(y or "-")
        sum_fn = lambda x, y: int(x or 0) + int(y or 0)
        percent_agg_fn = lambda x, m, f: "%(x)s (%(p)s%%)" % \
            {
                "x": x or 0,
                "p": (100 * int(x or 0) / (sum_fn(m, f) or 1))
            }
        total_percent_agg_fn = lambda x, y, m, f: "%(x)s (%(p)s%%)" % \
            {
                "x": sum_fn(x, y),
                "p": (100 * sum_fn(x, y) / (sum_fn(m, f) or 1))
            }

        patient_number_group = DataTablesColumnGroup("Tests")
        positive_group = DataTablesColumnGroup("Positive Tests")
        age_range_group = DataTablesColumnGroup("Age Range")

        male_filter = EQ("gender", "male")
        female_filter = EQ("gender", "female")

        return self.common_columns + [
            
            DatabaseColumn(
                "Number of Males ", 
                CountColumn('gender', alias="male-total", filters=self.filters + [male_filter]),
                header_group=patient_number_group
            ),
            DatabaseColumn(
                "Number of Females ", 
                CountColumn('gender', alias="female-total", filters=self.filters + [female_filter]),
                header_group=patient_number_group
            ),
            AggregateColumn(
                "Total", sum_fn, 
                [AliasColumn("male-total"), AliasColumn("female-total")],
                header_group=patient_number_group
            ),

            AggregateColumn(
                "Male +ve Percent", percent_agg_fn,
                [
                    CountColumn(
                        "diagnosis", 
                        alias="male-positive", 
                        filters=self.filters + [AND([male_filter, EQ("diagnosis", "positive")])]
                    ), 
                    AliasColumn("male-total"), AliasColumn("female-total")
                ],
                header_group=positive_group
            ),
            AggregateColumn(
                "Female +ve Percent", percent_agg_fn,
                [
                    CountColumn(
                        "diagnosis", 
                        alias="female-positive", 
                        filters=self.filters + [AND([female_filter, EQ("diagnosis", "positive")])]
                    ), 
                    AliasColumn("male-total"), AliasColumn("female-total")
                ],
                header_group=positive_group
            ),
            AggregateColumn(
                "Total +ve Percent", total_percent_agg_fn,
                [
                    AliasColumn("female-positive"), 
                    AliasColumn("male-positive"),
                    AliasColumn("male-total"), AliasColumn("female-total")
                ],
                header_group=positive_group
            ),

            AggregateColumn(
                "Male age range", age_fn,
                [
                    MinColumn("age", alias="male-min", filters=self.filters + [male_filter]),
                    MaxColumn("age", alias="male-max", filters=self.filters + [male_filter])
                ],
                header_group=age_range_group
            ),
            AggregateColumn(
                "Female age range", age_fn,
                [
                    MinColumn("age", alias="female-min", filters=self.filters + [female_filter]),
                    MaxColumn("age", alias="female-max", filters=self.filters + [female_filter])
                ],
                header_group=age_range_group
            ),
            AggregateColumn(
                "All age range", age_fn,
                [
                    MinColumn("age", alias="age-min", filters=self.filters + [OR([female_filter, male_filter])]),
                    MaxColumn("age", alias="age-max", filters=self.filters + [OR([female_filter, male_filter])])
                ],
                header_group=age_range_group
            ),
        ]

    @property
    def charts(self):
        rows = super(GSIDSQLPatientReport, self).rows
        loc_axis = Axis(label="Location")
        tests_axis = Axis(label="Number of Tests", format=",.1d")
        chart = MultiBarChart("Number of Tests Per Location", loc_axis, tests_axis)
        chart.stacked = True
        chart.tooltipFormat = " in "
        chart.add_dataset(
            "Male Tests", 
            [{'x':row[-11], 'y':row[-9]['html'] if row[-9] != "--" else 0} for row in rows],
            color="#1f07b4"
        )
        chart.add_dataset(
            "Female Tests", 
            [{'x':row[-11], 'y':row[-8]['html'] if row[-8] != "--" else 0} for row in rows],
            color="#1077b4"
        )
        return [chart]


class GSIDSQLByDayReport(GSIDSQLReport):
    name = "Day Summary Report"
    slug = "day_summary_sql"
    section_name = "day summary"

    @property
    def group_by(self):
        return super(GSIDSQLByDayReport, self).group_by + ["date"]

    @property
    def columns(self):
        return self.common_columns + \
            [
                DatabaseColumn("Count", CountColumn("age", alias="day_count"))
            ]

    def daterange(self, start_date, end_date):
        for n in range(int ((end_date - start_date).days)):
            yield (start_date + timedelta(n)).strftime("%Y-%m-%d")

    @property
    def headers(self):
        startdate = self.datespan.startdate_utc
        enddate = self.datespan.enddate_utc

        column_headers = []
        group_by = self.group_by[:-1]
        for place in group_by:
            column_headers.append(DataTablesColumn(place))

        prev_month = startdate.month
        month_columns = [startdate.strftime("%B %Y")]
        for n, day in enumerate(self.daterange(startdate, enddate)):
            day_obj = datetime.strptime(day, "%Y-%m-%d")
            month = day_obj.month
            day_column = DataTablesColumn("Day%(n)s (%(day)s)" % {'n':n+1, 'day': day})

            if month == prev_month:
                month_columns.append(day_column)
            else:
                month_group = DataTablesColumnGroup(*month_columns)
                column_headers.append(month_group)
                month_columns = [day_obj.strftime("%B %Y")]
                month_columns.append(day_column)
                prev_month = month
        
        month_group = DataTablesColumnGroup(*month_columns)
        column_headers.append(month_group)

        return DataTablesHeader(*column_headers)

    @property
    def rows(self):
        startdate = self.datespan.startdate_utc
        enddate = self.datespan.enddate_utc

        old_data = self.data
        rows = []
        for loc_key in self.keys:
            row = [x for x in loc_key]
            for n, day in enumerate(self.daterange(startdate, enddate)):
                temp_key = [loc for loc in loc_key]
                temp_key.append(datetime.strptime(day, "%Y-%m-%d").date())
                keymap = old_data.get(tuple(temp_key), None)
                day_count = (keymap["day_count"] if keymap else None) or self.no_value
                row.append(day_count)
            rows.append(row)
        return rows

    @property
    def charts(self):
        rows = self.rows
        date_index = len(self.place_types)
        startdate = self.datespan.startdate_utc
        enddate = self.datespan.enddate_utc
        date_axis = Axis(label="Date", dateFormat="%b %d")
        tests_axis = Axis(label="Number of Tests")
        chart = LineChart("Number of Tests Per Day", date_axis, tests_axis)
        for row in rows:
            data_points = []
            for n, day in enumerate(self.daterange(startdate, enddate)):
                x = day
                y = 0 if row[date_index + n + 1] == "--" else row[date_index + n + 1]
                data_points.append({'x': x, 'y': y})
            color = int(hashlib.md5(row[date_index-1]).hexdigest(), 16)
            color = str(hex(color))
            chart.add_dataset(row[date_index-1], data_points, color="#" + color[2:8])
        return [chart]

class GSIDSQLTestLotsReport(GSIDSQLReport):
    name = "Test Lots Report"
    slug = "test_lots_sql"
    section_name = "test lots"

    @property
    def group_by(self):
        return super(GSIDSQLTestLotsReport, self).group_by + ["test_version", "lot_number"]

    @property
    def columns(self):
        return self.common_columns + [
            DatabaseColumn("Test", CountColumn("gender", alias="lot_count"))
        ]

    @property
    def test_lots_map(self):
        old_data = self.data
        lots_map = dict()
        for key in old_data.keys():
            if lots_map.get(key[-2], None):
                lots_map[key[-2]].append(key[-1])
            else:
                lots_map[key[-2]] = [key[-1]]
        return lots_map

    @property
    def selected_tests(self):
        disease = self.request.GET.get('test_type_disease', '')
        test = self.request.GET.get('test_type_test', '')

        disease = disease.split(':') if disease else None
        test = test.split(':') if test else None

        if test:
            return [test[0]]
        elif disease:
            test_fixtures = FixtureDataItem.by_field_value(
                self.domain, 
                FixtureDataType.by_domain_tag(self.domain, "tests").one(),
                "disease_id",
                disease[0]
            )
            return [t.fields["test_name"] for t in test_fixtures]
        else:
            return self.test_types         

    
    @property
    def rows(self):
        test_lots_map = self.test_lots_map
        selected_tests = self.selected_tests
        old_data = self.data
        rows = []
        for loc_key in self.keys:
            row = [loc for loc in loc_key]
            for test in selected_tests:
                test_lots = test_lots_map.get(test, None)
                if not test_lots:
                    row.append(self.no_value)
                    continue
                total_test_count = 0
                for lot_number in test_lots:
                    temp_key = [loc for loc in loc_key] + [test, lot_number]
                    data_map = old_data.get(tuple(temp_key), None)
                    lot_count = data_map["lot_count"] if data_map else self.no_value
                    row.append(lot_count)
                    total_test_count += data_map["lot_count"] if data_map else 0
                row.append(total_test_count or self.no_value)
            rows.append(row)
        
        return rows

    @property
    def headers(self):
        column_headers = [ DataTablesColumn(loc) for loc in self.group_by[:-2]]
        test_lots_map = self.test_lots_map
        for test in self.selected_tests:
            lots_headers = [test]
            lots = test_lots_map.get(test, None)
            if not lots:
                lots_headers.append(DataTablesColumn("NO-LOTS"))
                column_headers.append(DataTablesColumnGroup(*lots_headers))
                continue
            for lot in lots:
                lots_headers.append(DataTablesColumn(str(lot)))
            lots_headers.append(DataTablesColumn("TOTAL"))
            column_headers.append(DataTablesColumnGroup(*lots_headers))

        return DataTablesHeader(*column_headers)


class GSIDSQLByAgeReport(GSIDSQLReport):
    name = "Age Summary Report"
    slug = "age_summary_sql"
    section_name = "age summary"
    
    @property
    def filter_values(self):
        age_filters = dict(
            zero=0,
            ten=10,
            ten_plus=11,
            twenty=20,
            twenty_plus=21,
            fifty=50
        )
        default_filter_values = super(GSIDSQLByAgeReport, self).filter_values
        default_filter_values.update(age_filters)
        return default_filter_values

    @property
    def columns(self):
        percent_fn = lambda x, y: "%(x)s (%(p)s%%)" % {"x": int(x or 0), "p": 100*(x or 0) / (y or 1)}
        
        female_range_group = DataTablesColumnGroup("Female Positive Tests (% positive)")
        male_range_group = DataTablesColumnGroup("Male Positive Tests (% positive)")

        def age_range_filter(gender, age_from, age_to):
            return [AND([EQ("gender", gender), EQ("diagnosis", "positive"), BETWEEN("age", age_from, age_to)])]

        def generate_columns(gender):
            age_range_group = male_range_group if gender is "male" else female_range_group
            return [
                AggregateColumn(
                    "0-10", percent_fn,
                    [   
                        CountColumn(
                            "age", 
                            alias="zero_ten_" + gender, 
                            filters=self.filters + age_range_filter(gender, "zero", "ten")
                        ),
                        CountColumn(
                            "age", 
                            alias=gender + "_total", 
                            filters=self.filters + [EQ("gender", gender)]
                        )
                    ],
                    header_group=age_range_group
                ),
                AggregateColumn(
                    "10-20", percent_fn, 
                    [
                        CountColumn(
                            "age", 
                            alias="ten_twenty_" + gender, 
                            filters=self.filters + age_range_filter(gender, "ten_plus", "twenty")
                        ),
                        AliasColumn(gender + "_total")
                    ],
                    header_group=age_range_group
                ),
                AggregateColumn(
                    "20-50", percent_fn,
                    [
                        CountColumn(
                            "age", 
                            alias="twenty_fifty_" + gender, 
                            filters= self.filters + age_range_filter(gender, "twenty_plus", "fifty")
                        ),
                        AliasColumn(gender + "_total")
                    ],
                    header_group=age_range_group
                ),
                AggregateColumn(
                    "50+", percent_fn,
                    [
                        CountColumn(
                            "age", 
                            alias="fifty_" + gender, 
                            filters=self.filters + [AND([EQ("gender", gender), EQ("diagnosis", "positive"), GT("age", "fifty")])]),
                        AliasColumn(gender + "_total")
                    ],
                    header_group=age_range_group
                ),
            ]

        return self.common_columns + generate_columns("male") + generate_columns("female")


class PatientMapReport(GenericMapReport, CustomProjectReport):
    name = "Patient Summary (Map)"
    slug = "patient_summary_map"

    fields = ['custom.apps.gsid.reports.TestField', 
              'custom.apps.gsid.reports.RelativeDatespanField', 
              'custom.apps.gsid.reports.AsyncClinicField',
              'custom.apps.gsid.reports.AggregateAtField']

    data_source = {
        'adapter': 'legacyreport',
        'geo_column': 'gps',
        'report': 'custom.apps.gsid.reports.sql_reports.GSIDSQLPatientReport',
    }

    display_config = {}

