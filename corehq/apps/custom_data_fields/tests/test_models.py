from django.test import SimpleTestCase, TestCase
from corehq.apps.custom_data_fields.models import Field, CustomDataFieldsDefinition, SYSTEM_PREFIX


class FieldTests(SimpleTestCase):
    def test_to_dict_serializes_all_fields(self):
        field = Field(
            slug='test-field',
            is_required=False,
            required_for=["web_user", "commcare_user"],
            label='test-label',
            choices=['yes', 'no'],
            regex=None,
            regex_msg=None,
            upstream_id='12345'
        )

        self.assertEqual(field.to_dict(), {
            'slug': 'test-field',
            'is_required': False,
            'required_for': ['web_user', 'commcare_user'],
            'label': 'test-label',
            'choices': ['yes', 'no'],
            'regex': None,
            'regex_msg': None,
            'upstream_id': '12345'
        })


class CustomDataFieldsDefinitionTests(TestCase):
    def setUp(self):
        self.definition = CustomDataFieldsDefinition.objects.create(field_type='test_type', domain='test_domain')
        self.fields = [
            Field.objects.create(
                definition=self.definition,
                slug='regular_field',
                is_required=False
            ),
            Field.objects.create(
                definition=self.definition,
                slug='required_field',
                is_required=True
            ),
            Field.objects.create(
                definition=self.definition,
                slug='web_user_required',
                is_required=True,
                required_for=["web_user"]
            ),
            Field.objects.create(
                definition=self.definition,
                slug=f'{SYSTEM_PREFIX}_system_field',
                is_required=False
            ),
        ]
        self.definition.set_field_order([f.id for f in self.fields])

    def test_get_all_fields(self):
        self.assertEqual(len(self.definition.get_fields()), 4)

    def test_get_required_fields(self):
        required_only_config = CustomDataFieldsDefinition.FieldFilterConfig(required_only=True)
        filtered_fields = self.definition.get_fields(field_filter_config=required_only_config)
        self.assertEqual(len(filtered_fields), 2)
        self.assertEqual(filtered_fields[0].slug, 'required_field')
        self.assertEqual(filtered_fields[1].slug, 'web_user_required')

    def test_get_non_system_fields(self):
        filtered_fields = self.definition.get_fields(include_system=False)
        self.assertEqual(len(filtered_fields), 3)
        self.assertNotIn(f'{SYSTEM_PREFIX}_system_field', [f.slug for f in filtered_fields])

    def test_get_required_non_system_fields(self):
        required_only_config = CustomDataFieldsDefinition.FieldFilterConfig(required_only=True)
        filtered_fields = self.definition.get_fields(field_filter_config=required_only_config,
                                                    include_system=False)
        self.assertEqual(len(filtered_fields), 2)
        self.assertEqual(filtered_fields[0].slug, 'required_field')
        self.assertEqual(filtered_fields[1].slug, 'web_user_required')

    def test_get_fields_with_custom_required_check(self):
        def custom_check(field):
            return field.is_required and "web_user" in field.required_for
        custom_required_only_config = CustomDataFieldsDefinition.FieldFilterConfig(
            required_only=True,
            is_required_check_func=custom_check
        )
        filtered_fields = self.definition.get_fields(field_filter_config=custom_required_only_config)
        self.assertEqual(len(filtered_fields), 1)
        self.assertEqual(filtered_fields[0].slug, 'web_user_required')
