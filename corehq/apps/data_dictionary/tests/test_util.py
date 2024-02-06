import uuid
from unittest.mock import patch

from django.test import TestCase
from django.utils.translation import gettext

from casexml.apps.case.mock import CaseBlock

from corehq.util.workbook_reading.datamodels import Cell

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.data_dictionary.tests.utils import setup_data_dictionary
from corehq.apps.data_dictionary.util import (
    generate_data_dictionary,
    get_values_hints_dict,
    get_column_headings,
    map_row_values_to_column_names,
    is_case_type_deprecated,
    get_data_dict_deprecated_case_types,
    is_case_type_or_prop_name_valid,
    delete_case_property,
    get_used_props_by_case_type,
)
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    es_test,
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


class DeleteCasePropertyTest(TestCase):
    domain = uuid.uuid4().hex

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_type = 'my-case-type'
        cls.case_prop_name = 'my-prop'
        cls.case_type_obj = CaseType(name=cls.case_type, domain=cls.domain)
        cls.case_type_obj.save()
        cls.case_prop_obj = CaseProperty(case_type=cls.case_type_obj, name=cls.case_prop_name)
        cls.case_prop_obj.save()

    @classmethod
    def tearDownClass(cls):
        cls.case_type_obj.delete()
        super().tearDownClass()

    def test_delete_case_property(self):
        error = delete_case_property(self.case_prop_name, self.case_type, self.domain)
        does_exist = CaseProperty.objects.filter(
            case_type__domain=self.domain,
            case_type__name=self.case_type,
            name=self.case_prop_name,
        ).exists()
        self.assertFalse(does_exist)
        self.assertEqual(error, None)


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

    def test_is_case_type_or_prop_name_valid(self):
        valid_names = [
            'foobar',
            'f00bar32',
            'foo-bar_32',
        ]
        invalid_names = [
            'foo bar',
            '32foobar',
            'foob@r',
            '_foobar',
        ]
        for valid_name in valid_names:
            self.assertTrue(is_case_type_or_prop_name_valid(valid_name))
        for invalid_name in invalid_names:
            self.assertFalse(is_case_type_or_prop_name_valid(invalid_name))


@es_test(requires=[case_search_adapter], setup_class=True)
class UsedPropsByCaseTypeTest(TestCase):

    domain = uuid.uuid4().hex

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_blocks = [
            cls._create_case_block(
                case_type='case-type',
                name='Case A',
                props={'prop': True},
            ),
            cls._create_case_block(
                case_type='case-type',
                name='Case B',
                props={'other-prop': True},
            ),
            cls._create_case_block(
                case_type='other-case-type',
                name='Case C',
                props={'prop': True, 'foobar': True},
            ),
            cls._create_case_block(
                case_type='no-props',
                name='Case D',
                props={},
            ),
        ]
        case_search_es_setup(cls.domain, cls.case_blocks)

    def _create_case_block(case_type, name, props):
        return CaseBlock(
            case_id=uuid.uuid4().hex,
            case_type=case_type,
            case_name=name,
            update=props,
        )

    def test_get_used_props_by_case_type(self):
        used_props_by_case_type = get_used_props_by_case_type(self.domain)
        self.assertEqual(len(used_props_by_case_type), 3)

        # No props were passed to this case type, so should only contain metadata
        # properties which we are not concerned about
        metadata_props = set(used_props_by_case_type['no-props'])

        props = set(used_props_by_case_type['case-type']) - metadata_props
        self.assertEqual({'prop', 'other-prop'}, props)
        props = set(used_props_by_case_type['other-case-type']) - metadata_props
        self.assertEqual({'prop', 'foobar'}, props)
