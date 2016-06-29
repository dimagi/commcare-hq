import functools
from sqlagg.columns import *
from sqlagg.base import AliasColumn
from sqlagg.filters import *
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader, DataTablesColumnGroup, DTSortType
from corehq.apps.reports.graph_models import MultiBarChart, LineChart, Axis
from corehq.apps.reports.sqlreport import DatabaseColumn, SummingSqlTabularReport, AggregateColumn, calculate_total_row
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.standard.maps import GenericMapReport
from corehq.apps.reports.util import format_datatables_data
from corehq.apps.style.decorators import use_maps, maps_prefer_canvas, use_nvd3
from corehq.apps.userreports.sql import get_table_name
from corehq.const import USER_MONTH_FORMAT
from corehq.util.dates import iso_string_to_date
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_date
from util import get_unique_combinations,  capitalize_fn

from datetime import timedelta


class StaticColumn(AliasColumn):
    column_key = None

    def __init__(self, key, value):
        super(StaticColumn, self).__init__(key)
        self.value = value

    def get_value(self, row):
        return self.value


class GSIDSQLReport(SummingSqlTabularReport, CustomProjectReport, DatespanMixin):
    fields = ['custom.apps.gsid.reports.TestField', 
              'corehq.apps.reports.filters.dates.DatespanFilter', 
              'custom.apps.gsid.reports.AsyncClinicField',
              'custom.apps.gsid.reports.AggregateAtField']

    exportable = True
    emailable = True
    default_aggregation = "clinic"

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(GSIDSQLReport, self).decorator_dispatcher(request, *args, **kwargs)

    def __init__(self, request, base_context=None, domain=None, **kwargs):
        self.is_map = kwargs.pop('map', False)
        super(GSIDSQLReport, self).__init__(request, base_context=base_context, domain=domain, **kwargs)

    @property
    def table_name(self):
        return get_table_name(self.domain, 'patient_summary')

    @property
    def daterange_display(self):
        format = "%d %b %Y"
        st = self.datespan.startdate.strftime(format)
        en = self.datespan.enddate.strftime(format)
        return "%s to %s" % (st, en)

    @property
    def report_subtitles(self):
        if self.needs_filters:
            return []

        subtitles = ["Date range: %s" % self.daterange_display]
        if self.selected_fixture():
            tag, id = self.selected_fixture()
            location = FixtureDataItem.get(id).fields_without_attributes['%s_name' % tag]
            subtitles.append('Location: %s' % location)

        if self.disease:
            location = FixtureDataItem.get(self.disease[1]).fields_without_attributes['disease_name']
            subtitles.append('Disease: %s' % location)

        if self.test_version:
            test_version = FixtureDataItem.get(self.test_version[1]).fields_without_attributes['visible_test_name']
            subtitles.append('Test Version: %s' % test_version)

        return subtitles

    @property
    @memoized
    def diseases(self):
        disease_fixtures = FixtureDataItem.by_data_type(
            self.domain, 
            FixtureDataType.by_domain_tag(self.domain, "diseases").one()
        )
        return {
            "ids": [d.fields_without_attributes["disease_id"] for d in disease_fixtures],
            "names": [d.fields_without_attributes["disease_name"] for d in disease_fixtures]
        }

    @property
    def test_types(self):
        test_fixtures = FixtureDataItem.by_data_type(
            self.domain, 
            FixtureDataType.by_domain_tag(self.domain, "test").one()
        )
        return [t.fields_without_attributes["test_name"] for t in test_fixtures]

    @property
    def filter_values(self):
        ret = dict(
            domain=self.domain,
            startdate=self.datespan.startdate_param,
            enddate=self.datespan.enddate_param,
            male="male",
            female="female",
            positive="POSITIVE"
        )

        DISEASES = self.diseases["ids"]
        TESTS = self.test_types

        ret.update(zip(DISEASES, DISEASES))
        ret.update(zip(TESTS, TESTS))

        return ret

    @property
    def filters(self):
        return [EQ("domain", "domain"), BETWEEN("date", "startdate", "enddate")] + self.disease_filters

    @property
    def disease(self):
        disease = self.request.GET.get('test_type_disease', '')
        return disease.split(':') if disease else None

    @property
    def test_version(self):
        test = self.request.GET.get('test_type_test', '')
        return test.split(':') if test else None

    @property
    def disease_filters(self):
        disease = self.disease
        test = self.test_version
        
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
        if agg_at and not agg_at == "clinic":
            gps_key = "gps_" + agg_at
        return gps_key

    @property
    def group_by(self):
        return self.place_types

    @property
    def keys(self):
        combos = get_unique_combinations(self.domain, place_types=self.place_types, place=self.selected_fixture())
        for c in combos:
            yield [c[pt] for pt in self.place_types]

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
            columns.append(DatabaseColumn(place.capitalize(), SimpleColumn(place), format_fn=capitalize_fn))

        return columns


class GSIDSQLPatientReport(GSIDSQLReport):

    name = "Patient Summary Report"
    slug = "patient_summary_sql"
    section_name = "patient summary"

    age_range_map = {'male': [None, None], 'female': [None, None], 'total': [None, None]}

    def age_fn(self, key, min, max):
        age_range = self.age_range_map[key]
        if min is not None and (age_range[0] is None or min < age_range[0]):
            self.age_range_map[key][0] = min
        if max is not None and (age_range[1] is None or max > age_range[1]):
            self.age_range_map[key][1] = max

        return self.format_age_range(min, max)

    def format_age_range(self, min, max):
        return str(min if min is not None else "-") + " - " + str(max if max is not None else "-")

    def percent_agg_fn(self, x, t):
        return dict(sort_key=x or 0, html="%(x)s (%(p)s%%)" % \
            {
                "x": x or 0,
                "p": (100 * int(x or 0) / (t or 1))
            })

    @property
    def columns(self):
        sum_fn = lambda x, y: int(x or 0) + int(y or 0)

        total_percent_agg_fn = lambda f_pos, m_pos, f_tot, m_tot: dict(sort_key=sum_fn(f_pos, m_pos), html="%(x)s (%(p)s%%)" % \
            {
                "x": sum_fn(f_pos, m_pos),
                "p": (100 * sum_fn(f_pos, m_pos) / (sum_fn(m_tot, f_tot) or 1))
            })

        patient_number_group = DataTablesColumnGroup("Tests")
        positive_group = DataTablesColumnGroup("Positive Tests")
        age_range_group = DataTablesColumnGroup("Age Range")

        male_filter = EQ("gender", "male")
        female_filter = EQ("gender", "female")

        columns = self.common_columns + [
            
            DatabaseColumn(
                "Number of Males ", 
                CountColumn('doc_id', alias="male-total", filters=self.filters + [male_filter]),
                header_group=patient_number_group
            ),
            DatabaseColumn(
                "Number of Females ", 
                CountColumn('doc_id', alias="female-total", filters=self.filters + [female_filter]),
                header_group=patient_number_group
            ),
            AggregateColumn(
                "Total", sum_fn,
                [AliasColumn("male-total"), AliasColumn("female-total")],
                header_group=patient_number_group
            ),

            AggregateColumn(
                "Male +ve Percent", self.percent_agg_fn,
                [
                    CountColumn(
                        'doc_id',
                        alias="male-positive", 
                        filters=self.filters + [AND([male_filter, EQ("diagnosis", "positive")])]
                    ), 
                    AliasColumn("male-total")
                ],
                header_group=positive_group, sort_type=DTSortType.NUMERIC
            ),
            AggregateColumn(
                "Female +ve Percent", self.percent_agg_fn,
                [
                    CountColumn('doc_id',
                        alias="female-positive", 
                        filters=self.filters + [AND([female_filter, EQ("diagnosis", "positive")])]
                    ), 
                    AliasColumn("female-total")
                ],
                header_group=positive_group, sort_type=DTSortType.NUMERIC
            ),
            AggregateColumn(
                "Total +ve Percent", total_percent_agg_fn,
                [
                    AliasColumn("female-positive"), 
                    AliasColumn("male-positive"),
                    AliasColumn("female-total"), AliasColumn("male-total")
                ],
                header_group=positive_group, sort_type=DTSortType.NUMERIC
            ),

            AggregateColumn(
                "Male age range", functools.partial(self.age_fn, 'male'),
                [
                    MinColumn("age", alias="male-min", filters=self.filters + [male_filter]),
                    MaxColumn("age", alias="male-max", filters=self.filters + [male_filter])
                ],
                header_group=age_range_group
            ),
            AggregateColumn(
                "Female age range", functools.partial(self.age_fn, 'female'),
                [
                    MinColumn("age", alias="female-min", filters=self.filters + [female_filter]),
                    MaxColumn("age", alias="female-max", filters=self.filters + [female_filter])
                ],
                header_group=age_range_group
            ),
            AggregateColumn(
                "All age range", functools.partial(self.age_fn, 'total'),
                [
                    MinColumn("age", alias="age-min", filters=self.filters + [OR([female_filter, male_filter])]),
                    MaxColumn("age", alias="age-max", filters=self.filters + [OR([female_filter, male_filter])])
                ],
                header_group=age_range_group
            ),
        ]

        if self.is_map:
            columns.append(DatabaseColumn("gps", MaxColumn(self.gps_key), format_fn=lambda x: x))
            disease = FixtureDataItem.get(self.disease[1]).fields_without_attributes['disease_name'] if self.disease else 'All diseases'
            columns.append(DatabaseColumn('disease', StaticColumn('disease', disease)))

        return columns

    @property
    def rows(self):
        rows = super(GSIDSQLPatientReport, self).rows
        self.total_row[0] = 'Total'

        # total age ranges
        col_start = -5 if self.is_map else -3
        self.total_row[col_start] = self.format_age_range(self.age_range_map['male'][0], self.age_range_map['male'][1])
        self.total_row[col_start+1] = self.format_age_range(self.age_range_map['female'][0], self.age_range_map['female'][1])
        self.total_row[col_start+2] = self.format_age_range(self.age_range_map['total'][0], self.age_range_map['total'][1])

        # formatted percent totals
        pos_col_start = -8 if self.is_map else -6
        tot_col_start = -11 if self.is_map else -9
        m_tot = self.total_row[tot_col_start]
        f_tot = self.total_row[tot_col_start+1]
        tot = self.total_row[tot_col_start+2]

        m_pos = self.total_row[pos_col_start]
        f_pos = self.total_row[pos_col_start+1]
        tot_pos = self.total_row[pos_col_start+2]

        self.total_row[pos_col_start] = self.percent_agg_fn(m_pos, m_tot)
        self.total_row[pos_col_start+1] = self.percent_agg_fn(f_pos, f_tot)
        self.total_row[pos_col_start+2] = self.percent_agg_fn(tot_pos, tot)
        return rows

    @property
    def charts(self):
        rows = self.rows
        loc_axis = Axis(label="Location")
        tests_axis = Axis(label="Number of Tests", format=",.1d")
        chart = MultiBarChart("Number of Tests Per Location", loc_axis, tests_axis)
        chart.stacked = True
        chart.tooltipFormat = " in "
        chart.add_dataset(
            "Male Tests", 
            [{'x':row[-10], 'y':row[-9]['html'] if row[-9] != "--" else 0} for row in rows],
            color="#0006CE"
        )
        chart.add_dataset(
            "Female Tests", 
            [{'x':row[-10], 'y':row[-8]['html'] if row[-8] != "--" else 0} for row in rows],
            color="#70D7FF"
        )
        return [chart]


class GSIDSQLByDayReport(GSIDSQLReport):
    name = "Day Summary Report"
    slug = "day_summary_sql"
    section_name = "day summary"

    @property
    def group_by(self):
        return super(GSIDSQLByDayReport, self).group_by + ["date", "disease_name"] 

    @property
    def columns(self):
        return self.common_columns + \
            [
                DatabaseColumn("Count", CountColumn("doc_id", alias="day_count")),
                DatabaseColumn("disease", SimpleColumn("disease_name", alias="disease_name"))
            ]

    def daterange(self, start_date, end_date):
        for n in range(int((end_date - start_date).days) + 1):
            yield json_format_date(start_date + timedelta(n))

    @property
    def headers(self):
        startdate = self.datespan.startdate
        enddate = self.datespan.enddate

        column_headers = []
        group_by = self.group_by[:-2]
        for place in group_by:
            column_headers.append(DataTablesColumn(place.capitalize()))
        column_headers.append(DataTablesColumn("Disease"))

        prev_month = startdate.month
        month_columns = [startdate.strftime(USER_MONTH_FORMAT)]
        for n, day in enumerate(self.daterange(startdate, enddate)):
            day_obj = iso_string_to_date(day)
            month = day_obj.month
            day_column = DataTablesColumn("Day%(n)s (%(day)s)" % {'n':n+1, 'day': day})

            if month == prev_month:
                month_columns.append(day_column)
            else:
                month_group = DataTablesColumnGroup(*month_columns)
                column_headers.append(month_group)
                month_columns = [day_obj.strftime(USER_MONTH_FORMAT), day_column]
                prev_month = month
        
        month_group = DataTablesColumnGroup(*month_columns)
        column_headers.append(month_group)

        return DataTablesHeader(*column_headers)

    @property
    def rows(self):
        startdate = self.datespan.startdate
        enddate = self.datespan.enddate

        old_data = self.data
        rows = []
        for loc_key in self.keys:
            selected_disease = self.request.GET.get('test_type_disease', '')
            selected_disease = selected_disease.split(':') if selected_disease else None
            diseases = [selected_disease[0]] if selected_disease else self.diseases["ids"]
            for disease in diseases:
                row = [capitalize_fn(x) for x in loc_key]
                disease_names = self.diseases["names"]
                index = self.diseases['ids'].index(disease)
                row.append(disease_names[index])
                for n, day in enumerate(self.daterange(startdate, enddate)):
                    temp_key = [loc for loc in loc_key]
                    temp_key.append(iso_string_to_date(day))
                    temp_key.append(disease)
                    keymap = old_data.get(tuple(temp_key), None)
                    day_count = (keymap["day_count"] if keymap else None)
                    row.append(format_datatables_data(day_count or self.no_value, day_count or 0))
                rows.append(row)

        self.total_row = calculate_total_row(rows)
        self.total_row[0] = 'Total'
        return rows

    @property
    def charts(self):
        rows = self.rows
        date_index = len(self.place_types)
        startdate = self.datespan.startdate
        enddate = self.datespan.enddate
        date_axis = Axis(label="Date", dateFormat="%b %d")
        tests_axis = Axis(label="Number of Tests")
        chart = LineChart("Number of Tests Per Day", date_axis, tests_axis)
        for row in rows:
            data_points = []
            for n, day in enumerate(self.daterange(startdate, enddate)):
                x = day
                y = 0 if row[date_index + n + 1] == "--" else row[date_index + n + 1]
                data_points.append({'x': x, 'y': y['sort_key']})
            chart.add_dataset(row[date_index-1] + "(" + row[date_index] + ")", data_points)
        return [chart]


class GSIDSQLTestLotsReport(GSIDSQLReport):
    name = "Test Lots Report"
    slug = "test_lots_sql"
    section_name = "test lots"

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return user and user.is_previewer()

    @property
    def group_by(self):
        return super(GSIDSQLTestLotsReport, self).group_by + ["test_version", "lot_number"]

    @property
    def columns(self):
        return self.common_columns + [
            DatabaseColumn("Test", CountColumn('doc_id', alias="lot_count"))
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
                FixtureDataType.by_domain_tag(self.domain, "test").one(),
                "disease_id",
                disease[0]
            )
            return [t.fields_without_attributes["test_name"] for t in test_fixtures]
        else:
            return self.test_types         

    @property
    def rows(self):
        test_lots_map = self.test_lots_map
        selected_tests = self.selected_tests
        old_data = self.data
        rows = []
        for loc_key in self.keys:
            row = [capitalize_fn(loc) for loc in loc_key]
            for test in selected_tests:
                test_lots = test_lots_map.get(test, None)
                if not test_lots:
                    row.append(format_datatables_data(self.no_value, 0))
                    continue
                total_test_count = 0
                for lot_number in test_lots:
                    temp_key = [loc for loc in loc_key] + [test, lot_number]
                    data_map = old_data.get(tuple(temp_key), None)
                    lot_count = data_map["lot_count"] if data_map else None
                    row.append(format_datatables_data(lot_count or self.no_value, lot_count or 0))
                    total_test_count += data_map["lot_count"] if data_map else 0
                row.append(format_datatables_data(total_test_count or self.no_value, total_test_count or 0))
            rows.append(row)

        self.total_row = calculate_total_row(rows)
        self.total_row[0] = 'Total'
        return rows

    @property
    def headers(self):
        column_headers = [DataTablesColumn(loc.capitalize()) for loc in self.group_by[:-2]]
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

    def percent_fn(self, x, y):
        return dict(
            sort_key=x or 0,
            html="%(x)s (%(p)s%%)" % {"x": int(x or 0), "p": 100*(x or 0) / (y or 1)})

    @property
    def columns(self):
        female_range_group = DataTablesColumnGroup("Female Positive Tests (% positive)")
        male_range_group = DataTablesColumnGroup("Male Positive Tests (% positive)")

        def age_range_filter(gender, age_from, age_to):
            return [AND([EQ("gender", gender), EQ("diagnosis", "positive"), BETWEEN("age", age_from, age_to)])]

        def generate_columns(gender):
            age_range_group = male_range_group if gender is "male" else female_range_group
            return [
                AggregateColumn(
                    "0-10", self.percent_fn,
                    [   
                        CountColumn(
                            'doc_id',
                            alias="zero_ten_" + gender, 
                            filters=self.filters + age_range_filter(gender, "zero", "ten")
                        ),
                        AliasColumn(gender + "_total")
                    ],
                    header_group=age_range_group, sort_type=DTSortType.NUMERIC
                ),
                AggregateColumn(
                    "10-20", self.percent_fn,
                    [
                        CountColumn(
                            'doc_id',
                            alias="ten_twenty_" + gender, 
                            filters=self.filters + age_range_filter(gender, "ten_plus", "twenty")
                        ),
                        AliasColumn(gender + "_total")
                    ],
                    header_group=age_range_group, sort_type=DTSortType.NUMERIC
                ),
                AggregateColumn(
                    "20-50", self.percent_fn,
                    [
                        CountColumn(
                            'doc_id',
                            alias="twenty_fifty_" + gender, 
                            filters= self.filters + age_range_filter(gender, "twenty_plus", "fifty")
                        ),
                        AliasColumn(gender + "_total")
                    ],
                    header_group=age_range_group, sort_type=DTSortType.NUMERIC
                ),
                AggregateColumn(
                    "50+", self.percent_fn,
                    [
                        CountColumn(
                            'doc_id',
                            alias="fifty_" + gender, 
                            filters=self.filters + [AND([EQ("gender", gender), EQ("diagnosis", "positive"), GT("age", "fifty")])]),
                        AliasColumn(gender + "_total")
                    ],
                    header_group=age_range_group, sort_type=DTSortType.NUMERIC
                ),
                AggregateColumn(
                    "Total", self.percent_fn,
                    [
                        CountColumn(
                            'doc_id',
                            alias="positive_total_" + gender,
                            filters=self.filters + [AND([EQ("gender", gender), EQ("diagnosis", "positive")])]),
                        CountColumn(
                            'doc_id',
                            alias=gender + "_total",
                            filters=self.filters + [EQ("gender", gender)]),
                    ],
                    header_group=age_range_group, sort_type=DTSortType.NUMERIC
                ),
            ]
        
        totals_group = DataTablesColumnGroup("Total tests")
        sum_fn = lambda x, y: int(x or 0) + int(y or 0)

        return self.common_columns + [
            DatabaseColumn(
                "Males ",
                AliasColumn("male_total"),
                header_group=totals_group
            ),
            DatabaseColumn(
                "Females ",
                AliasColumn("female_total"),
                header_group=totals_group
            ),
            AggregateColumn(
                "Total", sum_fn,
                [AliasColumn("male_total"), AliasColumn("female_total")],
                header_group=totals_group
            ),
        ] + generate_columns("male") + generate_columns("female")

    @property
    def rows(self):
        rows = super(GSIDSQLByAgeReport, self).rows
        self.total_row[0] = 'Total'

        # custom total row formatting
        tot_col_start = -13
        m_tot = self.total_row[tot_col_start]
        f_tot = self.total_row[tot_col_start+1]

        m_pos_start = -10
        self.total_row[m_pos_start] = self.percent_fn(self.total_row[m_pos_start], m_tot)
        self.total_row[m_pos_start+1] = self.percent_fn(self.total_row[m_pos_start+1], m_tot)
        self.total_row[m_pos_start+2] = self.percent_fn(self.total_row[m_pos_start+2], m_tot)
        self.total_row[m_pos_start+3] = self.percent_fn(self.total_row[m_pos_start+3], m_tot)
        self.total_row[m_pos_start+4] = self.percent_fn(self.total_row[m_pos_start+4], m_tot)

        f_pos_start = -5
        self.total_row[f_pos_start] = self.percent_fn(self.total_row[f_pos_start], f_tot)
        self.total_row[f_pos_start+1] = self.percent_fn(self.total_row[f_pos_start+1], f_tot)
        self.total_row[f_pos_start+2] = self.percent_fn(self.total_row[f_pos_start+2], f_tot)
        self.total_row[f_pos_start+3] = self.percent_fn(self.total_row[f_pos_start+3], f_tot)
        self.total_row[f_pos_start+4] = self.percent_fn(self.total_row[f_pos_start+4], f_tot)
        return rows


class PatientMapReport(GenericMapReport, CustomProjectReport):
    name = "Patient Summary (Map)"
    slug = "patient_summary_map"

    fields = ['custom.apps.gsid.reports.TestField', 
              'corehq.apps.reports.filters.dates.DatespanFilter', 
              'custom.apps.gsid.reports.AsyncClinicField',
              'custom.apps.gsid.reports.AggregateAtField']

    data_source = {
        'adapter': 'legacyreport',
        'geo_column': 'gps',
        'report': 'custom.apps.gsid.reports.sql_reports.GSIDSQLPatientReport',
        'report_params': {'map': True}
    }

    @maps_prefer_canvas
    @use_maps
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(PatientMapReport, self).decorator_dispatcher(request, *args, **kwargs)

    @property
    def display_config(self):
        return {
            'column_titles': {
                'Positive Tests::Female +ve Percent': 'Positive tests: Female',
                'Positive Tests::Male +ve Percent': 'Positive tests: Male',
                'Positive Tests::Total +ve Percent': 'Positive tests: Total',
                'Tests::Number of Females ': 'Total tests: Female',
                'Tests::Number of Males ': 'Total tests: Male',
                'Tests::Total': 'Total tests',
                'Age Range::All age range': 'Age range: All',
                'Age Range::Female age range': 'Age range: Female',
                'Age Range::Male age range': 'Age range: Male',
                'disease': 'Disease',
            },
            'detail_columns': self.place_types + [
                'disease',
                '__space__',
                'Positive Tests::Female +ve Percent',
                'Positive Tests::Male +ve Percent',
                'Positive Tests::Total +ve Percent',
                'Tests::Number of Females ',
                'Tests::Number of Males ',
                'Tests::Total',
            ],
            'table_columns': self.place_types + [
                'Tests::Number of Females ',
                'Tests::Number of Males ',
                'Tests::Total',
                'Positive Tests::Female +ve Percent',
                'Positive Tests::Male +ve Percent',
                'Positive Tests::Total +ve Percent',
                'Age Range::Female age range',
                'Age Range::Male age range',
                'Age Range::All age range',
            ],
            'detail_template': """<div class="default-popup">
                  <table>
                    <% _.each(info, function(field) { %>
                    <tr class="data data-<%= field.slug %>">
                      <% if (field.slug === '__space__') { %>
                        <td>&nbsp;</td><td>&nbsp;</td>
                      <% } else { %>
                        <td><%= field.label %></td>
                        <td class="detail_data">
                          <%= field.value %>
                        </td>
                      <% } %>
                    </tr>
                    <% }); %>
                  </table>
                </div>"""
        }

    @property
    def agg_level(self):
        agg_at = self.request.GET.get('aggregate_at', None)
        return agg_at if agg_at else 'clinic'

    @property
    def place_types(self):
        opts = ['country', 'province', 'district', 'clinic']
        agg_at = self.agg_level
        return [o.title() for o in opts[:opts.index(agg_at) + 1]]
