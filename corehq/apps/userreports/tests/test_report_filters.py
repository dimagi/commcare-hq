from datetime import datetime, date
from django.test import SimpleTestCase
from mock import Mock

from corehq.apps.reports_core.exceptions import FilterValueException
from corehq.apps.reports_core.filters import DatespanFilter, ChoiceListFilter, \
    NumericFilter, DynamicChoiceListFilter, Choice, PreFilter
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.reports.filters.values import SHOW_ALL_CHOICE, \
    CHOICE_DELIMITER, NumericFilterValue, DateFilterValue, PreFilterValue
from corehq.apps.userreports.reports.filters.factory import ReportFilterFactory
from corehq.apps.userreports.reports.filters.specs import ReportFilter
from dimagi.utils.dates import DateSpan


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
        self.assertEqual(filter.context(None, lang=None)['label'], "foo")
        self.assertEqual(filter.context(None, lang="fr")['label'], "foo")

        # Translation
        conf = {"display": {"en": "english", "fr": "french"}}
        conf.update(shared_conf)
        filter = ReportFilterFactory.from_spec(conf)
        self.assertEqual(filter.context(None, lang=None)['label'], "english")
        self.assertEqual(filter.context(None, lang="fr")['label'], "french")
        self.assertEqual(filter.context(None, lang="en")['label'], "english")
        self.assertEqual(filter.context(None, lang="es")['label'], "english")


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

            filter = ReportFilter.wrap(spec)
            return filter.create_filter_value(reports_core_value).to_sql_values()

        val = get_query_value(compare_as_string=False)
        self.assertEqual(type(val['my_slug_startdate']), datetime)
        self.assertEqual(type(val['my_slug_enddate']), datetime)

        val = get_query_value(compare_as_string=True)
        self.assertEqual(type(val['my_slug_startdate']), str)
        self.assertEqual(type(val['my_slug_enddate']), str)


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
        filter = ReportFilter.wrap({
            "type": "numeric",
            "field": "number_of_children_field",
            "slug": "number_of_children_slug",
            "display": "Number of Children",
        })
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
        filter_ = ReportFilter.wrap({
            'type': 'pre',
            'field': 'at_risk_field',
            'slug': 'at_risk_slug',
            'datatype': 'string',
            'pre_value': pre_value
        })
        filter_value = PreFilterValue(filter_, {'operand': pre_value})
        self.assertEqual(filter_value.to_sql_values(), {'at_risk_slug': 'yes'})

    def test_pre_filter_value_null(self):
        column = Mock()
        column.name = 'at_risk_field'
        column.is_.return_value = 'foo'
        table = Mock()
        table.c = [column]

        pre_value = None
        filter_ = ReportFilter.wrap({
            'type': 'pre',
            'field': 'at_risk_field',
            'slug': 'at_risk_slug',
            'datatype': 'string',
            'pre_value': pre_value
        })
        filter_value = PreFilterValue(filter_, {'operand': pre_value})
        self.assertEqual(filter_value.to_sql_values(), {})
        self.assertEqual(filter_value.to_sql_filter().build_expression(table), 'foo')

    def test_pre_filter_value_array(self):
        column = Mock()
        column.name = 'at_risk_field'
        column.in_.return_value = 'foo'
        table = Mock()
        table.c = [column]

        pre_value = ['yes', 'maybe']
        filter_ = ReportFilter.wrap({
            'type': 'pre',
            'field': 'at_risk_field',
            'slug': 'at_risk_slug',
            'datatype': 'array',
            'pre_value': pre_value
        })
        filter_value = PreFilterValue(filter_, {'operand': pre_value})
        self.assertEqual(filter_value.to_sql_values(), {'at_risk_slug_0': 'yes', 'at_risk_slug_1': 'maybe'})
        self.assertEqual(filter_value.to_sql_filter().build_expression(table), 'foo')

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
        filter_ = ReportFilter.wrap({
            'type': 'pre',
            'field': 'at_risk_field',
            'slug': 'at_risk_slug',
            'datatype': 'string',
            'pre_value': value['operand'],
            'pre_operator': value['operator'],
        })
        filter_value = PreFilterValue(filter_, value)
        with self.assertRaises(TypeError):
            filter_value.to_sql_filter()

    def test_pre_filter_between_operator(self):
        column = Mock()
        column.name = 'dob_field'
        column.between.return_value = 'foo'
        table = Mock()
        table.c = [column]

        value = {'operator': 'between', 'operand': ['2017-03-13', '2017-04-11']}
        filter_ = ReportFilter.wrap({
            'type': 'pre',
            'field': 'dob_field',
            'slug': 'dob_slug',
            'datatype': 'date',
            'pre_value': value['operand'],
            'pre_operator': value['operator'],
        })
        filter_value = PreFilterValue(filter_, value)
        self.assertEqual(filter_value.to_sql_values(), {'dob_slug_0': '2017-03-13', 'dob_slug_1': '2017-04-11'})
        self.assertEqual(filter_value.to_sql_filter().build_expression(table), 'foo')

    def test_pre_filter_dyn_operator(self):
        from corehq.apps.reports.daterange import get_daterange_start_end_dates

        column = Mock()
        column.name = 'dob_field'
        column.between.return_value = 'foo'
        table = Mock()
        table.c = [column]

        start_date, end_date = get_daterange_start_end_dates('lastmonth')

        value = {'operator': 'lastmonth', 'operand': [None]}
        filter_ = ReportFilter.wrap({
            'type': 'pre',
            'field': 'dob_field',
            'slug': 'dob_slug',
            'datatype': 'array',
            'pre_value': value['operand'],
            'pre_operator': value['operator'],
        })
        filter_value = PreFilterValue(filter_, value)
        self.assertEqual(filter_value.to_sql_values(), {
            'dob_slug_0': str(start_date),
            'dob_slug_1': str(end_date),
        })
        self.assertEqual(filter_value.to_sql_filter().build_expression(table), 'foo')


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
            u'apple',
            u'apple{s}banana'.format(s=CHOICE_DELIMITER),
            u'apple{s}banana{s}carrot'.format(s=CHOICE_DELIMITER)
        )
        choices = [
            Choice('apple', 'apple'),
            Choice('banana', 'banana'),
            Choice('carrot', 'carrot')
        ]
        for i, s in enumerate(test_strings):
            self.assertListEqual(choices[0:i + 1], filter.value(dynoslug=s))


class DateFilterOffsetTest(SimpleTestCase):
    def _computed_dates(self, actual_startdate, actual_enddate):
        filter = ReportFilter(
            compare_as_string=False,
            field=u'submission_date',
            slug=u'submitted_on',
            type=u'date',
            required=False
        )
        value = DateSpan(actual_startdate, actual_enddate)
        filter_value = DateFilterValue(filter, value)
        computed_values = filter_value.to_sql_values()
        startdate = computed_values['%s_startdate' % filter.slug]
        enddate = computed_values['%s_enddate' % filter.slug]
        return startdate, enddate

    def test_date_objects(self):
        start, end = date(2015, 1, 1), date(2015, 1, 2)
        computed_start, computed_end = self._computed_dates(start, end)
        self.assertEqual(computed_start, start)
        self.assertEqual(computed_end, end)

    def test_datetime_objects(self):
        # computed_enddate should be last minute of the enddate
        start, end = datetime(2015, 1, 1), datetime(2015, 1, 2)
        computed_start, computed_end = self._computed_dates(start, end)
        self.assertEqual(computed_start, start)
        self.assertNotEqual(computed_end, end)
        self.assertEqual((computed_end - end).days, 0)
