import uuid
from unittest.mock import patch

from django.test import TestCase
from django.utils.translation import gettext

from corehq.util.workbook_reading.datamodels import Cell

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.data_dictionary.tests.utils import setup_data_dictionary
from corehq.apps.data_dictionary.util import (
    generate_data_dictionary,
    get_values_hints_dict,
    get_column_headings,
    map_row_values_to_column_names,
    is_case_type_deprecated,
    get_data_dict_deprecated_case_types
)


@patch('corehq.apps.data_dictionary.util._get_all_case_properties')
class GenerateDictionaryTest(TestCase):
    domain = uuid.uuid4().hex

    def tearDown(self):
        CaseType.objects.filter(domain=self.domain).delete()

    def test_no_types(self, mock):
        mock.return_value = {}
        with self.assertNumQueries(1):
            generate_data_dictionary(self.domain)

        self.assertEqual(CaseType.objects.filter(domain=self.domain).count(), 0)
        self.assertEqual(CaseProperty.objects.filter(case_type__domain=self.domain).count(), 0)

    def test_empty_type(self, mock):
        mock.return_value = {'': ['prop']}
        with self.assertNumQueries(2):
            generate_data_dictionary(self.domain)

        self.assertEqual(CaseType.objects.filter(domain=self.domain).count(), 0)
        self.assertEqual(CaseProperty.objects.filter(case_type__domain=self.domain).count(), 0)

    def test_no_properties(self, mock):
        mock.return_value = {'type': []}
        with self.assertNumQueries(3):
            generate_data_dictionary(self.domain)

        self.assertEqual(CaseType.objects.filter(domain=self.domain).count(), 1)
        self.assertEqual(CaseProperty.objects.filter(case_type__domain=self.domain).count(), 0)

    def test_one_type(self, mock):
        mock.return_value = {'type': ['property']}
        with self.assertNumQueries(4):
            generate_data_dictionary(self.domain)

        self.assertEqual(CaseType.objects.filter(domain=self.domain).count(), 1)
        self.assertEqual(CaseProperty.objects.filter(case_type__domain=self.domain).count(), 1)

    def test_two_types(self, mock):
        mock.return_value = {'type': ['property'], 'type2': ['property']}
        with self.assertNumQueries(5):
            generate_data_dictionary(self.domain)

        self.assertEqual(CaseType.objects.filter(domain=self.domain).count(), 2)
        self.assertEqual(CaseProperty.objects.filter(case_type__domain=self.domain).count(), 2)

    def test_two_properties(self, mock):
        mock.return_value = {'type': ['property', 'property2']}
        with self.assertNumQueries(4):
            generate_data_dictionary(self.domain)

        self.assertEqual(CaseType.objects.filter(domain=self.domain).count(), 1)
        self.assertEqual(CaseProperty.objects.filter(case_type__domain=self.domain).count(), 2)

    def test_already_existing_property(self, mock):
        mock.return_value = {'type': ['property']}
        case_type = CaseType(domain=self.domain, name='type')
        case_type.save()
        CaseProperty(case_type=case_type, name='property').save()

        self.assertEqual(CaseType.objects.filter(domain=self.domain).count(), 1)
        self.assertEqual(CaseProperty.objects.filter(case_type__domain=self.domain).count(), 1)

        with self.assertNumQueries(3):
            generate_data_dictionary(self.domain)

        self.assertEqual(CaseType.objects.filter(domain=self.domain).count(), 1)
        self.assertEqual(CaseProperty.objects.filter(case_type__domain=self.domain).count(), 1)

    def test_parent_property(self, mock):
        mock.return_value = {'type': ['property', 'parent/property']}
        with self.assertNumQueries(4):
            generate_data_dictionary(self.domain)

        self.assertEqual(CaseType.objects.filter(domain=self.domain).count(), 1)
        self.assertEqual(CaseProperty.objects.filter(case_type__domain=self.domain).count(), 1)


class MiscUtilTest(TestCase):
    domain = uuid.uuid4().hex

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_type_name = 'caseType'
        cls.deprecated_case_type_name = 'depCaseType'
        cls.case_type_obj = CaseType(name=cls.case_type_name, domain=cls.domain)
        cls.case_type_obj.save()
        cls.dep_case_type_obj = CaseType(
            name=cls.deprecated_case_type_name,
            domain=cls.domain,
            is_deprecated=True
        )
        cls.dep_case_type_obj.save()

        cls.invalid_col = 'barr'
        cls.invalid_header_row = [Cell('Foo'), Cell(cls.invalid_col), Cell('Test Column'), Cell(None)]
        cls.valid_header_row = [Cell('Foo'), Cell('Bar'), Cell('Test Column')]
        cls.row = [Cell('a'), Cell('b')]
        cls.valid_values = {
            'foo': 'col_1',
            'bar': 'col_2',
            'test column': 'col_3',
        }

    def tearDown(self):
        CaseType.objects.filter(domain=self.domain).delete()

    def test_no_data_dict_info(self):
        case_type_name = 'bare'
        setup_data_dictionary(self.domain, case_type_name)
        self.assertEqual({}, get_values_hints_dict(self.domain, case_type_name))

    def test_date_hint(self):
        case_type_name = 'case1'
        date_prop_name = 'intake_date'
        setup_data_dictionary(self.domain, case_type_name, [(date_prop_name, 'date')])
        values_hints = get_values_hints_dict(self.domain, case_type_name)
        self.assertEqual(len(values_hints), 1)
        self.assertTrue(date_prop_name in values_hints)
        self.assertEqual(values_hints[date_prop_name], [gettext('YYYY-MM-DD')])

    def test_select_hints(self):
        case_type_name = 'case1'
        select_prop1 = 'status'
        select_prop2 = 'active'
        av_dict = {
            select_prop1: ['foster', 'pending', 'adopted'],
            select_prop2: ['true', 'false'],
        }
        prop_list = [(prop, 'select') for prop in [select_prop1, select_prop2]]
        setup_data_dictionary(self.domain, case_type_name, prop_list, av_dict)
        values_hints = get_values_hints_dict(self.domain, case_type_name)
        self.assertEqual(len(values_hints), 2)
        for prop_name, _ in prop_list:
            self.assertTrue(prop_name in values_hints)
            self.assertEqual(sorted(values_hints[prop_name]), sorted(av_dict[prop_name]))

    def test_get_column_headings(self):
        case_type = 'case'
        expected_errors = [
            f"Invalid column \"{self.invalid_col}\" in \"{case_type}\" sheet. "
            "Valid column names are: Foo, Bar, Test Column",
            f"Column 4 in \"{case_type}\" sheet has an empty header",
            f"Missing \"Case Property\" column header in \"{case_type}\" sheet",
        ]
        column_headings, errors = get_column_headings(
            self.invalid_header_row, self.valid_values, case_type, case_prop_name='Prop')
        self.assertEqual(column_headings, ['col_1', 'col_3'])
        self.assertEqual(errors, expected_errors)

    def test_map_row_values_to_column_names(self):
        column_headings, _ = get_column_headings(self.valid_header_row, self.valid_values)
        row_vals = map_row_values_to_column_names(self.row, column_headings, default_val='empty')
        expected_output = {
            'col_1': 'a',
            'col_2': 'b',
            'col_3': 'empty',
        }
        for key, val in expected_output.items():
            self.assertEqual(row_vals[key], val)

    def test_is_case_type_deprecated(self):
        is_deprecated = is_case_type_deprecated(self.domain, self.deprecated_case_type_name)
        self.assertTrue(is_deprecated)
        is_deprecated = is_case_type_deprecated(self.domain, '1234')
        self.assertFalse(is_deprecated)

    def test_get_data_dict_deprecated_case_types(self):
        deprecated_case_types = get_data_dict_deprecated_case_types(self.domain)
        self.assertEqual(len(deprecated_case_types), 1)
        self.assertEqual(deprecated_case_types, {self.deprecated_case_type_name})
