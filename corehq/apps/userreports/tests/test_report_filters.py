from django.test import SimpleTestCase
from corehq.apps.reports_core.filters import DatespanFilter, ChoiceListFilter, \
    NumericFilter, DynamicChoiceListFilter
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.reports.factory import ReportFilterFactory
from corehq.apps.userreports.reports.filters import SHOW_ALL_CHOICE


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


class ChoiceListFilterTestCase(SimpleTestCase):
    CHOICES = [
        {
            "value": "NEGATIVE",
            "display": "Negative"
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

    def test_choice_list_filter_with_integers(self):
        choices = [
            {
                "value": 0,
                "display": "Negative"
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
            "display": "Diagnosis",
            "choices": choices,
            "show_all": False,
        })
        self.assertEqual(ChoiceListFilter, type(filter))
        self.assertEqual('diagnosis_slug', filter.name)
        self.assertEqual('Diagnosis', filter.label)
        self.assertEqual(2, len(filter.choices))
        for i, choice in enumerate(choices):
            self.assertEqual(filter.choices[i].value, choice['value'])
            self.assertEqual(filter.choices[i].display, choice['display'])


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
            (1, '1'),
            (1.2, '1.2'),
            ('hello', 'hello'),
        )
        for input, expected in tests:
            choice = filter.value(dynoslug=input)
            self.assertEqual(expected, choice.value)
            self.assertEqual(input, choice.display)

    def test_integer_datatype(self):
        self.filter_spec['datatype'] = 'integer'
        filter = ReportFilterFactory.from_spec(self.filter_spec)
        tests = (
            (1, 1),
            (1.2, 1),
            ('hello', None),
        )
        for input, expected in tests:
            choice = filter.value(dynoslug=input)
            self.assertEqual(expected, choice.value)
            self.assertEqual(input, choice.display)
