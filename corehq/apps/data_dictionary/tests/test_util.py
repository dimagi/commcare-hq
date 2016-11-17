from django.test import TestCase
from mock import patch

from corehq.apps.data_dictionary.models import CaseType, CaseProperty
from corehq.apps.data_dictionary.util import generate_data_dictionary


class GenerateDictionaryTest(TestCase):
    domain = 'data-dictionary'

    def tearDown(self):
        CaseType.objects.filter(domain=self.domain).delete()

    @patch('corehq.apps.data_dictionary.util._get_all_case_properties')
    def test_no_types(self, mock):
        mock.return_value = {}
        generate_data_dictionary(self.domain)

        self.assertEqual(CaseType.objects.filter(domain=self.domain).count(), 0)
        self.assertEqual(CaseProperty.objects.filter(case_type__domain=self.domain).count(), 0)

    @patch('corehq.apps.data_dictionary.util._get_all_case_properties')
    def test_empty_type(self, mock):
        mock.return_value = {'': ['prop']}
        generate_data_dictionary(self.domain)

        self.assertEqual(CaseType.objects.filter(domain=self.domain).count(), 0)
        self.assertEqual(CaseProperty.objects.filter(case_type__domain=self.domain).count(), 0)

    @patch('corehq.apps.data_dictionary.util._get_all_case_properties')
    def test_no_properties(self, mock):
        mock.return_value = {'type': []}
        generate_data_dictionary(self.domain)

        self.assertEqual(CaseType.objects.filter(domain=self.domain).count(), 1)
        self.assertEqual(CaseProperty.objects.filter(case_type__domain=self.domain).count(), 0)

    @patch('corehq.apps.data_dictionary.util._get_all_case_properties')
    def test_one_type(self, mock):
        mock.return_value = {'type': ['property']}
        generate_data_dictionary(self.domain)

        self.assertEqual(CaseType.objects.filter(domain=self.domain).count(), 1)
        self.assertEqual(CaseProperty.objects.filter(case_type__domain=self.domain).count(), 1)

    @patch('corehq.apps.data_dictionary.util._get_all_case_properties')
    def test_two_types(self, mock):
        mock.return_value = {'type': ['property'], 'type2': ['property']}
        generate_data_dictionary(self.domain)

        self.assertEqual(CaseType.objects.filter(domain=self.domain).count(), 2)
        self.assertEqual(CaseProperty.objects.filter(case_type__domain=self.domain).count(), 2)

    @patch('corehq.apps.data_dictionary.util._get_all_case_properties')
    def test_two_properties(self, mock):
        mock.return_value = {'type': ['property', 'property2']}
        generate_data_dictionary(self.domain)

        self.assertEqual(CaseType.objects.filter(domain=self.domain).count(), 1)
        self.assertEqual(CaseProperty.objects.filter(case_type__domain=self.domain).count(), 2)
