from django.test import SimpleTestCase
from corehq.apps.reports_core.filters import DatespanFilter, ChoiceListFilter
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
