from datetime import datetime, date

from django.http import HttpRequest, QueryDict
from django.test import SimpleTestCase, TestCase
from django.utils.http import urlencode

from corehq.apps.locations.util import load_locs_json, location_hierarchy_config
from corehq.apps.locations.tests.util import LocationHierarchyTestCase
from corehq.apps.reports_core.exceptions import FilterValueException
from corehq.apps.reports_core.filters import DatespanFilter, ChoiceListFilter, \
    NumericFilter, DynamicChoiceListFilter, Choice, PreFilter, LocationDrilldownFilter, REQUEST_USER_KEY
from corehq.apps.users.models import CommCareUser
from corehq.apps.userreports.const import UCR_SQL_BACKEND
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.models import DataSourceConfiguration, ReportConfiguration
from corehq.apps.userreports.reports.filters.values import SHOW_ALL_CHOICE, \
    CHOICE_DELIMITER, NumericFilterValue, DateFilterValue, PreFilterValue, LocationDrilldownFilterValue
from corehq.apps.userreports.reports.filters.factory import ReportFilterFactory
from corehq.apps.userreports.reports.filters.specs import create_filter_value
from corehq.apps.userreports.reports.view import ConfigurableReportView, query_dict_to_dict
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.apps.userreports.tests.test_view import ConfigurableReportTestMixin
from corehq.apps.userreports.util import get_indicator_adapter
from dimagi.utils.dates import DateSpan
import six


class FilterTestCase(SimpleTestCase):

    def test_no_type(self):
        with self.assertRaises(BadSpecError):
            ReportFilterFactory.from_spec({
                "field": "some_field",
                "slug": "some_slug",
                "display": "Some display name"
            })

    def test_bad_type(self):
        with self.assertRaises(BadSpecError):
            ReportFilterFactory.from_spec({
                "type": "invalid_type",
                "field": "some_field",
                "slug": "some_slug",
                "display": "Some display name"
            })

    def test_missing_field(self):
        with self.assertRaises(BadSpecError):
            ReportFilterFactory.from_spec({
                "type": "date",
                "slug": "some_slug",
                "display": "Some display name"
            })

    def test_missing_slug(self):
        with self.assertRaises(BadSpecError):
            ReportFilterFactory.from_spec({
                "type": "date",
                "field": "some_field",
                "display": "Some display name"
            })

    def test_translation(self):
        shared_conf = {
            "type": "date",
            "field": "some_field",
            "slug": "some_slug",
        }

        # Plain string
        conf = {"display": "foo"}
        conf.update(shared_conf)
        filter = ReportFilterFactory.from_spec(conf)
        self.assertEqual(filter.context({}, None, lang=None)['label'], "foo")
        self.assertEqual(filter.context({}, None, lang="fr")['label'], "foo")

        # Translation
        conf = {"display": {"en": "english", "fr": "french"}}
        conf.update(shared_conf)
        filter = ReportFilterFactory.from_spec(conf)
        self.assertEqual(filter.context({}, None, lang=None)['label'], "english")
        self.assertEqual(filter.context({}, None, lang="fr")['label'], "french")
        self.assertEqual(filter.context({}, None, lang="en")['label'], "english")
        self.assertEqual(filter.context({}, None, lang="es")['label'], "english")


class DateFilterTestCase(SimpleTestCase):

    def test_date_filter(self):
        filter = ReportFilterFactory.from_spec({
            "type": "date",
            "field": "modified_on_field",
            "slug": "modified_on_slug",
            "display": "Date Modified"
        })
        self.assertEqual(DatespanFilter, type(filter))
        self.assertEqual('modified_on_slug', filter.name)
        self.assertEqual('Date Modified', filter.label)

    def test_compare_as_string_option(self):

        def get_query_value(compare_as_string):

            spec = {
                "type": "date",
                "field": "modified_on_field",
                "slug": "my_slug",
                "display": "date Modified",
                "compare_as_string": compare_as_string,
            }
            reports_core_filter = ReportFilterFactory.from_spec(spec)
            reports_core_value = reports_core_filter.get_value({
                "my_slug-start": "2015-06-07",
                "my_slug-end": "2015-06-08",
                "date_range_inclusive": True,
            })

            return create_filter_value(spec, reports_core_value).to_sql_values()

        val = get_query_value(compare_as_string=False)
        self.assertEqual(type(val['my_slug_startdate']), datetime)
        self.assertEqual(type(val['my_slug_enddate']), datetime)

        val = get_query_value(compare_as_string=True)
        self.assertEqual(type(val['my_slug_startdate']), str)
        self.assertEqual(type(val['my_slug_enddate']), str)


class DateFilterDBTest(ConfigurableReportTestMixin, TestCase):

    @classmethod
    def setUpClass(cls):
        super(DateFilterDBTest, cls).setUpClass()
        cls._create_data()
        cls._create_data_source()
        cls.report_config = cls._create_report()

    @classmethod
    def _create_data(cls):
        cls._new_case({"my_date": date(2017, 1, 1), "my_datetime": datetime(2017, 1, 1, 9)}).save()

    @classmethod
    def _create_data_source(cls):
        cls.data_sources = {}
        cls.adapters = {}

        config = DataSourceConfiguration(
            domain=cls.domain,
            display_name=cls.domain,
            referenced_doc_type='CommCareCase',
            table_id="foo",
            configured_filter={
                "type": "boolean_expression",
                "operator": "eq",
                "expression": {
                    "type": "property_name",
                    "property_name": "type"
                },
                "property_value": cls.case_type,
            },
            configured_indicators=[
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'my_date'
                    },
                    "column_id": 'date_as_string',
                    "display_name": 'date_as_string',
                    "datatype": "string"
                },
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'my_date'
                    },
                    "column_id": 'date_as_date',
                    "datatype": "date"
                },
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": "my_datetime",
                    },
                    "column_id": "datetime_as_datetime",
                    "datatype": "datetime"
                }
            ],
        )
        config.validate()
        config.save()
        rebuild_indicators(config._id)
        adapter = get_indicator_adapter(config)
        cls.data_sources[UCR_SQL_BACKEND] = config
        cls.adapters[UCR_SQL_BACKEND] = adapter

    @classmethod
    def _create_report(cls):
        report_config = ReportConfiguration(
            domain=cls.domain,
            config_id=cls.data_sources[UCR_SQL_BACKEND]._id,
            title='foo',
            filters=[
                {
                    "type": "date",
                    "field": "date_as_date",
                    "slug": "date_as_date_filter",
                    "display": "Date as Date filter"
                },
                {
                    "type": "date",
                    "field": "date_as_string",
                    "slug": "date_as_string_filter",
                    "display": "Date as String filter",
                    "compare_as_string": True,
                },
                {
                    "type": "date",
                    "field": "datetime_as_datetime",
                    "slug": "datetime_as_datetime_filter",
                    "display": "Datetime as Datetime filter",
                    "compare_as_string": False,
                }
            ],
            aggregation_columns=['doc_id'],
            columns=[{
                # We don't really care what columns are returned, we're testing the filters
                "type": "field",
                "display": "doc_id",
                "field": 'doc_id',
                'column_id': 'doc_id',
                'aggregation': 'simple'
            }],
        )
        report_config.save()
        return report_config

    def _create_view(self, filter_values):
        request = HttpRequest()
        request.method = 'GET'
        request.GET.update(filter_values)
        view = ConfigurableReportView(request=request)
        view._domain = self.domain
        view._lang = "en"
        view._report_config_id = self.report_config._id
        return view

    @classmethod
    def tearDownClass(cls):
        for key, adapter in six.iteritems(cls.adapters):
            adapter.drop_table()
        cls._delete_everything()
        super(DateFilterDBTest, cls).tearDownClass()

    def docs_returned(self, export_table):
        rows = export_table[0][1]
        return len(rows) - 1  # the first row is the headers, not a document

    def test_standard_date_filter(self):
        # Confirm that date filters include rows that match the start and/or end date.
        view = self._create_view({
            "date_as_date_filter": "2017-01-01 to 2017-01-01",
            "date_as_date_filter-start": "2017-01-01",
            "date_as_date_filter-end": "2017-01-01",
        })
        self.assertEqual(1, self.docs_returned(view.export_table))

    def test_string_date_filter(self):
        # Confirm that "compare_as_string" date filters include rows that match the start and/ord end date
        view = self._create_view({
            "date_as_string_filter": "2017-01-01 to 2017-01-01",
            "date_as_string_filter-start": "2017-01-01",
            "date_as_string_filter-end": "2017-01-01",
        })
        self.assertEqual(1, self.docs_returned(view.export_table))

    def test_standard_datetime_filter(self):
        view = self._create_view({
            "datetime_as_datetime_filter": "2017-01-01 to 2017-01-01",
            "datetime_as_datetime_filter-start": "2017-01-01",
            "datetime_as_datetime_filter-end": "2017-01-01",
        })
        self.assertEqual(1, self.docs_returned(view.export_table))


class QuarterFilterTestCase(SimpleTestCase):

    def test_date_filter(self):
        def get_query_value(year, quarter):
            spec = {
                "type": "quarter",
                "field": "modified_on_field",
                "slug": "my_slug",
                "display": "date Modified",
            }
            reports_core_filter = ReportFilterFactory.from_spec(spec)
            reports_core_value = reports_core_filter.get_value({
                "my_slug-year": year,
                "my_slug-quarter": quarter
            })

            return create_filter_value(spec, reports_core_value).to_sql_values()

        value = get_query_value(2016, 1)
        self.assertEqual(value['my_slug_startdate'], datetime(2016, 1, 1))
        self.assertEqual(value['my_slug_enddate'], datetime(2016, 4, 1))

        value = get_query_value(2016, 2)
        self.assertEqual(value['my_slug_startdate'], datetime(2016, 4, 1))
        self.assertEqual(value['my_slug_enddate'], datetime(2016, 7, 1))

        value = get_query_value(2016, 3)
        self.assertEqual(value['my_slug_startdate'], datetime(2016, 7, 1))
        self.assertEqual(value['my_slug_enddate'], datetime(2016, 10, 1))

        value = get_query_value(2016, 4)
        self.assertEqual(value['my_slug_startdate'], datetime(2016, 10, 1))
        self.assertEqual(value['my_slug_enddate'], datetime(2017, 1, 1))


class NumericFilterTestCase(SimpleTestCase):

    def test_numeric_filter(self):
        filter = ReportFilterFactory.from_spec({
            "type": "numeric",
            "field": "number_of_children_field",
            "slug": "number_of_children_slug",
            "display": "Number of Children",
        })
        self.assertEqual(NumericFilter, type(filter))
        self.assertEqual("number_of_children_slug", filter.name)
        self.assertEqual("Number of Children", filter.label)

    def test_numeric_filter_value(self):
        filter = {
            "type": "numeric",
            "field": "number_of_children_field",
            "slug": "number_of_children_slug",
            "display": "Number of Children",
        }
        NumericFilterValue(filter, None)
        NumericFilterValue(filter, {'operator': '<', 'operand': 3})
        with self.assertRaises(AssertionError):
            NumericFilterValue(filter, {'operator': 'sql injection', 'operand': 3})


class PreFilterTestCase(SimpleTestCase):

    def test_pre_filter(self):
        filter_ = ReportFilterFactory.from_spec({
            'type': 'pre',
            'field': 'at_risk_field',
            'slug': 'at_risk_slug',
            'datatype': 'string',
            'pre_value': 'true'
        })
        self.assertEqual(type(filter_), PreFilter)
        self.assertEqual(filter_.name, 'at_risk_slug')
        self.assertEqual(filter_.default_value(), {'operator': '=', 'operand': 'true'})

    def test_pre_filter_value(self):
        pre_value = 'yes'
        filter_ = {
            'type': 'pre',
            'field': 'at_risk_field',
            'slug': 'at_risk_slug',
            'datatype': 'string',
            'pre_value': pre_value
        }
        filter_value = PreFilterValue(filter_, {'operand': pre_value})
        self.assertEqual(filter_value.to_sql_values(), {'at_risk_slug': 'yes'})

    def test_pre_filter_value_null(self):
        pre_value = None
        filter_ = {
            'type': 'pre',
            'field': 'at_risk_field',
            'slug': 'at_risk_slug',
            'datatype': 'string',
            'pre_value': pre_value
        }
        filter_value = PreFilterValue(filter_, {'operand': pre_value})
        self.assertEqual(filter_value.to_sql_values(), {})
        self.assertEqual(
            str(filter_value.to_sql_filter().build_expression()),
            'at_risk_field IS NULL'
        )

    def test_pre_filter_value_array(self):
        pre_value = ['yes', 'maybe']
        filter_ = {
            'type': 'pre',
            'field': 'at_risk_field',
            'slug': 'at_risk_slug',
            'datatype': 'array',
            'pre_value': pre_value
        }
        filter_value = PreFilterValue(filter_, {'operand': pre_value})
        self.assertEqual(filter_value.to_sql_values(), {'at_risk_slug_0': 'yes', 'at_risk_slug_1': 'maybe'})
        self.assertEqual(
            str(filter_value.to_sql_filter().build_expression()),
            'at_risk_field IN (:at_risk_slug_0, :at_risk_slug_1)'
        )

    def test_pre_filter_operator(self):
        value = {'operator': '<=', 'operand': '99'}
        filter_ = ReportFilterFactory.from_spec({
            'type': 'pre',
            'field': 'risk_indicator_field',
            'slug': 'risk_indicator_slug',
            'datatype': 'integer',
            'pre_value': value['operand'],
            'pre_operator': value['operator'],
        })
        self.assertEqual(type(filter_), PreFilter)
        self.assertEqual(filter_.default_value(), {'operator': '<=', 'operand': 99})  # operand will be coerced

    def test_pre_filter_invalid_operator(self):
        value = {'operator': 'in', 'operand': 'no'}  # "in" is invalid for scalar operand
        filter_ = {
            'type': 'pre',
            'field': 'at_risk_field',
            'slug': 'at_risk_slug',
            'datatype': 'string',
            'pre_value': value['operand'],
            'pre_operator': value['operator'],
        }
        filter_value = PreFilterValue(filter_, value)
        with self.assertRaises(TypeError):
            filter_value.to_sql_filter()

    def test_pre_filter_between_operator(self):
        value = {'operator': 'between', 'operand': ['2017-03-13', '2017-04-11']}
        filter_ = {
            'type': 'pre',
            'field': 'dob_field',
            'slug': 'dob_slug',
            'datatype': 'date',
            'pre_value': value['operand'],
            'pre_operator': value['operator'],
        }
        filter_value = PreFilterValue(filter_, value)
        self.assertEqual(filter_value.to_sql_values(), {'dob_slug_0': '2017-03-13', 'dob_slug_1': '2017-04-11'})
        self.assertEqual(
            str(filter_value.to_sql_filter().build_expression()),
            'dob_field BETWEEN :dob_slug_0 AND :dob_slug_1'
        )

    def test_pre_filter_distinct_from_operator(self):
        value = {'operator': 'distinct from', 'operand': 'test'}
        filter_ = {
            'type': 'pre',
            'field': 'at_risk_field',
            'slug': 'at_risk_slug',
            'datatype': 'string',
            'pre_value': value['operand'],
            'pre_operator': value['operator'],
        }
        filter_value = PreFilterValue(filter_, value)
        self.assertEqual(filter_value.to_sql_values(), {'at_risk_slug': 'test'})

    def test_pre_filter_dyn_operator(self):
        from corehq.apps.reports.daterange import get_daterange_start_end_dates
        start_date, end_date = get_daterange_start_end_dates('lastmonth')

        value = {'operator': 'lastmonth', 'operand': [None]}
        filter_ = {
            'type': 'pre',
            'field': 'dob_field',
            'slug': 'dob_slug',
            'datatype': 'array',
            'pre_value': value['operand'],
            'pre_operator': value['operator'],
        }
        filter_value = PreFilterValue(filter_, value)
        self.assertEqual(filter_value.to_sql_values(), {
            'dob_slug_0': str(start_date),
            'dob_slug_1': str(end_date),
        })
        self.assertEqual(
            str(filter_value.to_sql_filter().build_expression()),
            'dob_field BETWEEN :dob_slug_0 AND :dob_slug_1'
        )


class ChoiceListFilterTestCase(SimpleTestCase):
    CHOICES = [
        {
            "value": "NEGATIVE",
            "display": "negative"
        },
        {
            "value": "POSITIVE",
            "display": "positive"
        }
    ]

    def test_choice_list_filter(self):
        filter = ReportFilterFactory.from_spec({
            "type": "choice_list",
            "slug": "diagnosis_slug",
            "field": "diagnosis_field",
            "display": "Diagnosis",
            "choices": self.CHOICES,
            "show_all": False,
        })
        self.assertEqual(ChoiceListFilter, type(filter))
        self.assertEqual('diagnosis_slug', filter.name)
        self.assertEqual('Diagnosis', filter.label)
        self.assertEqual(2, len(filter.choices))
        for i, choice in enumerate(self.CHOICES):
            self.assertEqual(filter.choices[i].value, choice['value'])
            self.assertEqual(filter.choices[i].display, choice['display'])

        # check values
        self.assertEqual('positive', filter.value(diagnosis_slug='POSITIVE').display)

    def test_choice_list_filter_show_all(self):
        filter = ReportFilterFactory.from_spec({
            "type": "choice_list",
            "slug": "diagnosis_slug",
            "field": "diagnosis_field",
            "display": "Diagnosis",
            "choices": self.CHOICES,
            "show_all": True,
        })
        self.assertEqual(3, len(filter.choices))

        self.assertEqual(SHOW_ALL_CHOICE, filter.choices[0].value)
        for i, choice in enumerate(self.CHOICES):
            self.assertEqual(filter.choices[i + 1].value, choice['value'])
            self.assertEqual(filter.choices[i + 1].display, choice['display'])

        # check all value
        self.assertEqual('Show all', filter.value(diagnosis_slug=SHOW_ALL_CHOICE).display)

    def test_choice_list_filter_with_integers(self):
        choices = [
            {
                "value": 0,
                "display": "negative"
            },
            {
                "value": 1,
                "display": "positive"
            }
        ]
        filter = ReportFilterFactory.from_spec({
            "type": "choice_list",
            "slug": "diagnosis_slug",
            "field": "diagnosis_field",
            "datatype": "integer",
            "display": "Diagnosis",
            "choices": choices,
            "show_all": True,
        })
        self.assertEqual(ChoiceListFilter, type(filter))
        self.assertEqual('diagnosis_slug', filter.name)
        self.assertEqual('Diagnosis', filter.label)
        self.assertEqual(3, len(filter.choices))
        non_all_choices = filter.choices[1:]
        for i, choice in enumerate(choices):
            self.assertEqual(non_all_choices[i].value, choice['value'])
            self.assertEqual(non_all_choices[i].display, choice['display'])

        # ensure integer values work
        self.assertEqual('positive', filter.value(diagnosis_slug=1).display)
        # ensure 0 integer value works
        self.assertEqual('negative', filter.value(diagnosis_slug=0).display)
        # check string to int coercion
        self.assertEqual('positive', filter.value(diagnosis_slug='1').display)
        # ensure 0 string to int works
        self.assertEqual('negative', filter.value(diagnosis_slug='0').display)

        # check missing values raise errors
        with self.assertRaises(FilterValueException):
            filter.value(diagnosis_slug='4')

        # check non-integers raise errors
        with self.assertRaises(FilterValueException):
            filter.value(diagnosis_slug='foo')

        # check that all still works
        self.assertEqual('Show all', filter.value(diagnosis_slug=SHOW_ALL_CHOICE).display)


class DynamicChoiceListFilterTestCase(SimpleTestCase):

    def setUp(self):
        self.filter_spec = {
            "type": "dynamic_choice_list",
            "slug": "dynoslug",
            "field": "dynofield",
            "display": "Dynamic choice list",
            "show_all": False,
        }

    def test_choice_list_filter(self):
        filter = ReportFilterFactory.from_spec(self.filter_spec)
        self.assertEqual(DynamicChoiceListFilter, type(filter))
        self.assertEqual('dynoslug', filter.name)
        self.assertEqual('Dynamic choice list', filter.label)

    def test_string_datatype(self):
        self.filter_spec['datatype'] = 'string'
        filter = ReportFilterFactory.from_spec(self.filter_spec)
        tests = (
            ('1', '1'),
            ('1.2', '1.2'),
            ('hello', 'hello'),
        )
        for input, expected in tests:
            choices = filter.value(dynoslug=input)
            self.assertEqual(len(choices), 1)
            self.assertEqual(expected, choices[0].value)
            self.assertEqual(input, choices[0].display)

    def test_integer_datatype(self):
        self.filter_spec['datatype'] = 'integer'
        filter = ReportFilterFactory.from_spec(self.filter_spec)
        tests = (
            ('1', 1, '1'),
            ('1.2', 1, '1'),
            ('hello', None, ''),
        )
        for input, expected_value, expected_display in tests:
            choices = filter.value(dynoslug=input)
            self.assertEqual(len(choices), 1)
            self.assertEqual(expected_value, choices[0].value)
            self.assertEqual(expected_display, choices[0].display)

    def test_multiple_selections(self):
        self.filter_spec["datatype"] = "string"
        filter = ReportFilterFactory.from_spec(self.filter_spec)
        test_strings = (
            'apple',
            'apple{s}banana'.format(s=CHOICE_DELIMITER),
            'apple{s}banana{s}carrot'.format(s=CHOICE_DELIMITER)
        )
        choices = [
            Choice('apple', 'apple'),
            Choice('banana', 'banana'),
            Choice('carrot', 'carrot')
        ]
        for i, s in enumerate(test_strings):
            self.assertListEqual(choices[0:i + 1], filter.value(dynoslug=s))

    def test_ancestor_expression(self):
        filter = {
            "type": "dynamic_choice_list",
            "slug": "dynoslug",
            "field": "dynofield",
            "display": "Dynamic choice list",
            "show_all": False,
            "choice_provider": {"type": "user"},
            "ancestor_expression": {
                "field": "state_id",
                "location_type": "state",
            }
        }

        with self.assertRaises(BadSpecError):
            ReportFilterFactory.from_spec(filter)
        filter['choice_provider']['type'] = 'location'
        ReportFilterFactory.from_spec(filter)


class DateFilterOffsetTest(SimpleTestCase):
    def _computed_dates(self, actual_startdate, actual_enddate):
        filter = {
            'compare_as_string': False,
            'field': 'submission_date',
            'slug': 'submitted_on',
            'type': 'date',
            'required': False
        }
        value = DateSpan(actual_startdate, actual_enddate)
        filter_value = DateFilterValue(filter, value)
        computed_values = filter_value.to_sql_values()
        startdate = computed_values['%s_startdate' % filter['slug']]
        enddate = computed_values['%s_enddate' % filter['slug']]
        return startdate, enddate

    def test_date_objects(self):
        start, end = date(2015, 1, 1), date(2015, 1, 2)
        computed_start, computed_end = self._computed_dates(start, end)
        self.assertEqual(computed_start, start)
        self.assertEqual(computed_end, datetime.combine(end, datetime.max.time()))

    def test_datetime_objects(self):
        # computed_enddate should be last minute of the enddate
        start, end = datetime(2015, 1, 1), datetime(2015, 1, 2)
        computed_start, computed_end = self._computed_dates(start, end)
        self.assertEqual(computed_start, start)
        self.assertEqual(computed_end, datetime.combine(end, datetime.max.time()))
        self.assertEqual((computed_end - end).days, 0)


class LocationDrilldownFilterTest(LocationHierarchyTestCase):
    location_type_names = ['state', 'county', 'city']
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolk', [
                ('Boston', []),
            ])
        ])
    ]

    @classmethod
    def setUpClass(cls):
        cls.user = CommCareUser.create(cls.domain, 'test1', 'test123')
        super(LocationDrilldownFilterTest, cls).setUpClass()

    def test_filter(self):
        report = ReportConfiguration(domain=self.domain)
        ui_filter = ReportFilterFactory.from_spec({
            "slug": "block_id_drill",
            "type": "location_drilldown",
            "field": "block_id",
            "display": "Drilldown by Location",
            "include_descendants": False,
        }, report)

        self.assertEqual(type(ui_filter), LocationDrilldownFilter)

        # test filter_context
        filter_context_expected = {
            'input_name': 'block_id_drill',
            'loc_id': None,
            'hierarchy': location_hierarchy_config(self.domain),
            'locations': load_locs_json(self.domain),
            'loc_url': '/a/{}/api/v0.5/location_internal/'.format(self.domain),
            'max_drilldown_levels': 99
        }
        self.assertDictEqual(ui_filter.filter_context(self.user), filter_context_expected)

        # test include_descendants=False
        self.assertListEqual(
            ui_filter.value(
                **{ui_filter.name: self.locations.get('Middlesex').location_id, REQUEST_USER_KEY: self.user}
            ),
            [self.locations.get('Middlesex').location_id]
        )

        # test include_descendants=True
        ui_filter = ReportFilterFactory.from_spec({
            "slug": "block_id_drill",
            "type": "location_drilldown",
            "field": "block_id",
            "display": "Drilldown by Location",
            "include_descendants": True,
        }, report)
        self.assertListEqual(
            ui_filter.value(
                **{ui_filter.name: self.locations.get('Middlesex').location_id, REQUEST_USER_KEY: self.user}
            ),
            [self.locations.get(name).location_id
             for name in ['Middlesex', 'Cambridge', 'Somerville']]
        )

    def test_filter_value(self):
        filter = {
            "type": "location_drilldown",
            "field": "block_id",
            "slug": "block_id_drill",
            "display": "Drilldown by Location",
        }
        filter_value = LocationDrilldownFilterValue(filter, ['Middlesex'])
        self.assertDictEqual(filter_value.to_sql_values(), {'block_id_drill_0': 'Middlesex'})
        self.assertEqual(
            str(filter_value.to_sql_filter().build_expression()),
            'block_id IN (:block_id_drill_0)'
        )
        self.assertEqual(
            filter_value.to_sql_values(),
            {'block_id_drill_0': 'Middlesex'}
        )

    def test_ancestor_expression_missing_location_type(self):
        with self.assertRaises(BadSpecError):
            ReportFilterFactory.from_spec({
                "type": "location_drilldown",
                "field": "block_id",
                "slug": "block_id_drill",
                "display": "Drilldown by Location",
                "ancestor_expression": {
                    'field': 'state_id',
                    # missing 'location_type': 'state',
                }
            })

    def test_prefix_ancestor_location(self):
        filter = {
            "type": "location_drilldown",
            "field": "block_id",
            "slug": "block_id_drill",
            "display": "Drilldown by Location",
            "ancestor_expression": {
                'field': 'state_id',
                'location_type': 'state',
            }
        }
        middlesex_id = self.locations['Middlesex'].location_id
        mass_id = self.locations['Massachusetts'].location_id
        # make sure ancestor gets passed if right block is passed
        filter_value = LocationDrilldownFilterValue(filter, [middlesex_id])
        self.assertEqual(
            str(filter_value.to_sql_filter().build_expression()),
            'state_id = :state_id AND block_id IN (:block_id_drill_0)'
        )
        self.assertEqual(
            filter_value.to_sql_values(),
            {'state_id': mass_id, 'block_id_drill_0': middlesex_id}
        )
        # make sure ancestor doesn't get passed if multiple locations are passed
        filter_value = LocationDrilldownFilterValue(filter, [middlesex_id, 'Suffolk'])
        self.assertEqual(
            str(filter_value.to_sql_filter().build_expression()),
            'block_id IN (:block_id_drill_0, :block_id_drill_1)'
        )
        self.assertEqual(
            filter_value.to_sql_values(),
            {'block_id_drill_0': middlesex_id, 'block_id_drill_1': 'Suffolk'}
        )
        # no ancestor is passed if passed in location is invalid
        filter_value = LocationDrilldownFilterValue(filter, ['random'])
        self.assertEqual(
            str(filter_value.to_sql_filter().build_expression()),
            'block_id IN (:block_id_drill_0)'
        )
        self.assertEqual(
            filter_value.to_sql_values(),
            {'block_id_drill_0': 'random'}
        )


class QueryDictUtilTest(SimpleTestCase):
    def test_raw_boolean_strings_are_not_cast(self):
        request_dict = query_dict_to_dict(QueryDict(urlencode(
            {'my_string_key': 'true', 'another_string': 'false', 'non_string': 'true',
             'non_string_2': 'false', 'string_int': '1', 'non_string_int': '2', 'apple': 'orange'})),
            "some_domain",
            ['my_string_key', 'another_string', 'string_int']
        )
        self.assertDictEqual(
            request_dict,
            {
                # keys marked as string should not be casted to bool
                'apple': 'orange',
                'my_string_key': 'true',
                'another_string': 'false',
                'string_int': '1',
                # keys not marked as string are casted to bool
                'non_string': True,
                'non_string_2': False,
                'domain': 'some_domain',
                'non_string_int': 2,
            }
        )
