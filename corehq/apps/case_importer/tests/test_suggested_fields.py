from collections import defaultdict
from django.test import SimpleTestCase

from unittest import mock

from corehq.apps.case_importer.suggested_fields import (
    FieldSpec,
    get_suggested_case_fields,
    get_non_discoverable_system_properties,
)
from corehq.util.test_utils import DocTestMixin


class SuggestedFieldTest(SimpleTestCase, DocTestMixin):
    @mock.patch('corehq.apps.case_importer.suggested_fields.get_deprecated_fields')
    @mock.patch('corehq.apps.case_importer.suggested_fields.get_values_hints_dict')
    @mock.patch('corehq.apps.case_importer.suggested_fields.get_all_case_properties_for_case_type')
    @mock.patch('corehq.apps.case_importer.suggested_fields.get_special_fields')
    def _test(self, get_special_fields, get_case_properties_for_case_type,
              get_values_hints_dict, get_deprecated_fields,
              special_fields, case_properties, excluded_fields, expected_result):
        get_special_fields.return_value = special_fields
        get_case_properties_for_case_type.return_value = case_properties
        get_values_hints_dict.return_value = defaultdict(list)
        get_deprecated_fields.return_value = set()
        self.assert_doc_lists_equal(
            get_suggested_case_fields('my-domain', 'my_case_type', exclude=excluded_fields),
            expected_result
        )

    def test_excludes_from_both(self):
        self._test(
            special_fields=[
                FieldSpec(field='external_id', description='External ID'),
            ],
            case_properties=['external_id'],
            excluded_fields=['external_id'],
            expected_result=[
            ]
        )

    def test_special_wins_out(self):
        self._test(
            special_fields=[
                FieldSpec(field='external_id', description='External ID'),
            ],
            case_properties=['external_id'],
            excluded_fields=['case_id'],
            expected_result=[
                FieldSpec(field='external_id', description='External ID')
            ]
        )

    def test_basic_inclusion_and_sorting(self):
        self._test(
            special_fields=[
                FieldSpec(field='external_id', description='External ID'),
                FieldSpec(field='owner_name', description='Owner Name'),
                FieldSpec(field='name', description='Name', show_in_menu=True),
            ],
            case_properties=['age', 'date', 'weight'],
            excluded_fields=['case_id'],
            expected_result=[
                FieldSpec(field='age', show_in_menu=True),
                FieldSpec(field='date', show_in_menu=True),
                FieldSpec(field='external_id', description='External ID'),
                FieldSpec(field='name', description='Name', show_in_menu=True),
                FieldSpec(field='owner_name', description='Owner Name'),
                FieldSpec(field='weight', show_in_menu=True),
            ]
        )


class TestSystemProperties(SimpleTestCase):

    def test_get_non_discoverable_system_properties(self):
        self.assertEqual(get_non_discoverable_system_properties(), [
            'number',
            'caseid',
            'case_type',
            'closed',
            'closed_by_user_id',
            'closed_by_username',
            'closed_date',
            'last_modified_by_user_id',
            'last_modified_by_user_username',
            'last_modified_date',
            'opened_by_user_id',
            'opened_by_username',
            'opened_date',
            'server_last_modified_date',
            'state',
            'case_link',
        ])
