import uuid
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils.translation import gettext

from casexml.apps.case.mock import CaseBlock

from corehq.apps.data_dictionary.models import CaseProperty, CaseType, CasePropertyGroup
from corehq.apps.data_dictionary.tests.utils import setup_data_dictionary
from corehq.apps.data_dictionary.util import (
    delete_case_property,
    fields_to_validate,
    generate_data_dictionary,
    get_case_property_count,
    get_case_property_deprecated_dict,
    get_case_property_description_dict,
    get_case_property_group_name_for_properties,
    get_case_property_label_dict,
    get_column_headings,
    get_data_dict_deprecated_case_types,
    get_values_hints_dict,
    is_case_type_deprecated,
    is_case_type_or_prop_name_valid,
    is_case_type_unused,
    is_case_property_unused,
    map_row_values_to_column_names,
    update_url_query_params,
)
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import case_search_es_setup, es_test
from corehq.util.workbook_reading.datamodels import Cell


@patch('corehq.apps.data_dictionary.util._get_properties_by_case_type')
class GenerateDictionaryTest(TestCase):
    domain = uuid.uuid4().hex

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
        cls.case_type_obj = CaseType.objects.create(name=cls.case_type_name, domain=cls.domain)
        cls.dep_case_type_obj = CaseType.objects.create(
            name=cls.deprecated_case_type_name,
            domain=cls.domain,
            is_deprecated=True
        )
        cls.case_type_group = CasePropertyGroup.objects.create(
            case_type=cls.case_type_obj,
            name='TestGroup'
        )
        cls.case_type_deprecated_group = CasePropertyGroup.objects.create(
            case_type=cls.case_type_obj,
            name='DeprecatedTestGroup',
            deprecated=True,
        )
        CaseProperty.objects.create(
            name='case_prop_1',
            case_type=cls.case_type_obj,
            description='foo',
            group=cls.case_type_group,
        )
        CaseProperty.objects.create(
            name='case_prop_2',
            case_type=cls.case_type_obj,
            deprecated=True,
            label='Prop'
        )
        CaseProperty.objects.create(
            name='case_prop_3',
            case_type=cls.dep_case_type_obj,
            deprecated=True,
            description='bar',
        )

        cls.invalid_col = 'barr'
        cls.invalid_header_row = [Cell('Foo'), Cell(cls.invalid_col), Cell('Test Column'), Cell(None)]
        cls.valid_header_row = [Cell('Foo'), Cell('Bar'), Cell('Test Column')]
        cls.row = [Cell('a'), Cell('b')]
        cls.valid_values = {
            'foo': 'col_1',
            'bar': 'col_2',
            'test column': 'col_3',
        }

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
        sheet_name = 'foobar'
        column_headings, _ = get_column_headings(self.valid_header_row, self.valid_values, sheet_name)
        row_vals, errors = map_row_values_to_column_names(
            self.row, column_headings, sheet_name, default_val='empty'
        )
        expected_output = {
            'col_1': 'a',
            'col_2': 'b',
            'col_3': 'empty',
        }
        self.assertEqual(len(errors), 0)
        for key, val in expected_output.items():
            self.assertEqual(row_vals[key], val)

    def test_map_row_values_to_column_names_errors(self):
        sheet_name = 'foobar'
        column_headings, _ = get_column_headings(self.valid_header_row, self.valid_values, sheet_name)
        row_vals, errors = map_row_values_to_column_names(self.row, column_headings[0:1], sheet_name=sheet_name)
        self.assertEqual(errors[0], f'Column 2 in "{sheet_name}" sheet is missing a header')

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

    def test_get_case_property_description_dict(self):
        desc_dict = get_case_property_description_dict(self.domain)
        expected_response = {
            'caseType': {
                'case_prop_1': 'foo',
                'case_prop_2': '',
            },
            'depCaseType': {
                'case_prop_3': 'bar',
            }
        }
        self.assertEqual(desc_dict, expected_response)

    def test_get_case_property_label_dict(self):
        label_dict = get_case_property_label_dict(self.domain)
        expected_response = {
            'caseType': {
                'case_prop_1': '',
                'case_prop_2': 'Prop',
            },
            'depCaseType': {
                'case_prop_3': '',
            }
        }
        self.assertEqual(label_dict, expected_response)

    def test_get_case_property_deprecated_dict(self):
        dep_dict = get_case_property_deprecated_dict(self.domain)
        expected_response = {
            'caseType': [
                'case_prop_2',
            ],
            'depCaseType': [
                'case_prop_3',
            ]
        }
        self.assertEqual(dep_dict, expected_response)

    def test_get_case_property_group_name_for_properties(self):
        # Deprecated case prop
        CaseProperty.objects.create(
            name='deprecated_case_prop',
            case_type=self.case_type_obj,
            label='Deprecated Case Prop',
            deprecated=True,
            group=self.case_type_group,
        )
        # Deprecated group's case prop
        CaseProperty.objects.create(
            name='deprecated_group_case_prop_1',
            case_type=self.case_type_obj,
            label='Deprecated group prop',
            group=self.case_type_deprecated_group,
        )

        case_group_name_for_property = get_case_property_group_name_for_properties(self.domain,
                                                                                   self.case_type_name)
        self.assertEqual(
            case_group_name_for_property,
            {'case_prop_1': 'TestGroup'}
        )


@es_test(requires=[case_search_adapter], setup_class=True)
class TestUnusedCaseTypeAndProperty(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-unused-types-and-props'
        cls.case_blocks = [
            cls._create_case_block(
                case_type='case-type',
                name='Case A',
                props={'prop': True, 'empty-prop': '', 'null-prop': None},
            ),
        ]
        case_search_es_setup(cls.domain, cls.case_blocks)

    @classmethod
    def _create_case_block(cls, case_type, name, props):
        return CaseBlock(
            case_id=uuid.uuid4().hex,
            case_type=case_type,
            case_name=name,
            update=props,
        )

    def test_unused_case_type_returns_true(self):
        self.assertTrue(is_case_type_unused(self.domain, 'random-case-type'))

    def test_used_case_type_returns_false(self):
        self.assertFalse(is_case_type_unused(self.domain, 'case-type'))

    def test_unused_case_property_returns_true(self):
        self.assertTrue(is_case_property_unused(self.domain, 'case-type', 'random-prop'))

    def test_used_case_property_returns_false(self):
        self.assertFalse(is_case_property_unused(self.domain, 'case-type', 'prop'))

    def test_empty_case_property_returns_true(self):
        self.assertTrue(is_case_property_unused(self.domain, 'case-type', 'empty-prop'))

    def test_null_case_property_returns_true(self):
        self.assertTrue(is_case_property_unused(self.domain, 'case-type', 'null-prop'))


class TestUpdateUrlQueryParams(SimpleTestCase):
    url = "http://example.com"

    def test_add_params(self):
        result = update_url_query_params(self.url, {"fruit": "orange", "biscuits": "oreo"})
        self.assertEqual(result, f"{self.url}?fruit=orange&biscuits=oreo")

    def test_update_params(self):
        result = update_url_query_params(f"{self.url}?fruit=apple", {"fruit": "orange", "biscuits": "oreo"})
        self.assertEqual(result, f"{self.url}?fruit=orange&biscuits=oreo")

    def test_no_params(self):
        result = update_url_query_params(self.url, {})
        self.assertEqual(result, self.url)


class TestGetCasePropertyCount(TestCase):

    domain = 'test-count'

    def test_returns_accurate_count(self):
        """Count is directly reflective of linked CaseProperty objects"""
        case_type = CaseType.objects.create(name='count', domain=self.domain)
        for i in range(5):
            CaseProperty.objects.create(name=f'count-{i}', case_type=case_type)
        assert get_case_property_count(self.domain, case_type.name) == 5

    def test_exludes_deprecated_properties(self):
        case_type = CaseType.objects.create(name='count', domain=self.domain)
        for i in range(5):
            CaseProperty.objects.create(name=f'count-{i}', case_type=case_type)
        for i in range(2):
            CaseProperty.objects.create(name=f'count-dep-{i}', case_type=case_type, deprecated=True)
        assert get_case_property_count(self.domain, case_type.name) == 5


class TestFieldsToValidate(TestCase):
    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_type = CaseType.objects.create(
            name='test-case-type',
            domain=cls.domain,
        )
        cls.date_prop = CaseProperty(
            name='date_property',
            case_type=cls.case_type,
            data_type=CaseProperty.DataType.DATE,
        )
        cls.select_prop = CaseProperty(
            name='select_property',
            case_type=cls.case_type,
            data_type=CaseProperty.DataType.SELECT,
        )
        CaseProperty.objects.bulk_create([
            cls.date_prop,
            cls.select_prop,
            CaseProperty(
                name='plain_property',
                case_type=cls.case_type,
                data_type=CaseProperty.DataType.PLAIN,
            ),
            CaseProperty(
                name='number_property',
                case_type=cls.case_type,
                data_type=CaseProperty.DataType.NUMBER,
            ),
            CaseProperty(
                name='barcode_property',
                case_type=cls.case_type,
                data_type=CaseProperty.DataType.BARCODE,
            ),
            CaseProperty(
                name='gps_property',
                case_type=cls.case_type,
                data_type=CaseProperty.DataType.GPS,
            ),
            CaseProperty(
                name='phone_property',
                case_type=cls.case_type,
                data_type=CaseProperty.DataType.PHONE_NUMBER,
            ),
            CaseProperty(
                name='password_property',
                case_type=cls.case_type,
                data_type=CaseProperty.DataType.PASSWORD,
            ),
            CaseProperty(
                name='undefined_property',
                case_type=cls.case_type,
                data_type=CaseProperty.DataType.UNDEFINED,
            ),
        ])

    def test_fields_to_validate_returns_only_date_and_select_properties(self):
        result = fields_to_validate(self.domain, self.case_type.name)
        expected_names = {'date_property', 'select_property'}
        assert set(result.keys()) == expected_names
        assert result['date_property'] == self.date_prop
        assert result['select_property'] == self.select_prop
