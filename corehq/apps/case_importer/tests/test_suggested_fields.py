from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
import mock
from corehq.apps.case_importer.suggested_fields import get_suggested_case_fields, \
    FieldSpec
from corehq.util.test_utils import DocTestMixin


class SuggestedFieldTest(SimpleTestCase, DocTestMixin):
    @mock.patch('corehq.apps.case_importer.suggested_fields.get_case_properties_for_case_type')
    @mock.patch('corehq.apps.case_importer.suggested_fields.get_special_fields')
    def _test(self, get_special_fields, get_case_properties_for_case_type,
              special_fields, case_properties, excluded_fields, expected_result):
        get_special_fields.return_value = special_fields
        get_case_properties_for_case_type.return_value = case_properties
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
