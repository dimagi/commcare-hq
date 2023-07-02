from django.test import SimpleTestCase
from corehq.apps.custom_data_fields.models import Field


class FieldTests(SimpleTestCase):
    def test_to_dict_serializes_all_fields(self):
        field = Field(
            slug='test-field',
            is_required=False,
            label='test-label',
            choices=['yes', 'no'],
            regex=None,
            regex_msg=None,
            upstream_id='12345'
        )

        self.assertEqual(field.to_dict(), {
            'slug': 'test-field',
            'is_required': False,
            'label': 'test-label',
            'choices': ['yes', 'no'],
            'regex': None,
            'regex_msg': None,
            'upstream_id': '12345'
        })
