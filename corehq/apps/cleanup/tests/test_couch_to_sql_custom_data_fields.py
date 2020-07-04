from django.test import TestCase

from corehq.apps.custom_data_fields.management.commands.populate_custom_data_fields import Command
from corehq.apps.custom_data_fields.models import (
    CustomDataField,
    CustomDataFieldsDefinition,
    SQLCustomDataFieldsDefinition,
    SQLField,
)
from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types


class TestCouchToSQL(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db = CustomDataFieldsDefinition.get_db()

    def tearDown(self):
        SQLCustomDataFieldsDefinition.objects.all().delete()
        for doc in get_all_docs_with_doc_types(self.db, ['CustomDataFieldsDefinition']):
            CustomDataFieldsDefinition.wrap(doc).delete()
        super().tearDown()

    def test_diff(self):
        # Start with identical data
        def_args = {'domain': 'some-domain', 'field_type': 'ProductFields'}
        field1_args = {'slug': 'texture', 'is_required': True, 'label': 'Texture', 'choices': ['soft', 'spiky']}
        obj = SQLCustomDataFieldsDefinition(**def_args)
        obj.save()
        obj.set_fields([SQLField(**field1_args)])
        doc = CustomDataFieldsDefinition(
            fields=[CustomDataField(**field1_args)],
            **def_args,
        ).to_json()
        self.assertIsNone(Command.diff_couch_and_sql(doc, obj))

        # Difference in top-level attribute
        doc['domain'] = 'other-domain'
        self.assertEqual(
            Command.diff_couch_and_sql(doc, obj),
            "domain: couch value 'other-domain' != sql value 'some-domain'"
        )

        # Difference in numer of sub-models
        doc['domain'] = 'some-domain'
        field2_args = {'slug': 'temp', 'is_required': False, 'label': 'F', 'choices': ['32', '212']}
        doc['fields'] = [CustomDataField(**field1_args).to_json(), CustomDataField(**field2_args).to_json()]
        self.assertEqual(
            Command.diff_couch_and_sql(doc, obj),
            "fields: 2 in couch != 1 in sql"
        )

        # Different in sub-model attribute
        field2_args['label'] = 'C'
        obj.set_fields([SQLField(**field1_args), SQLField(**field2_args)])
        self.assertEqual(
            Command.diff_couch_and_sql(doc, obj),
            "label: couch value 'F' != sql value 'C'"
        )

        # Difference in sub-model ordering
        field2_args['label'] = 'F'
        obj.set_fields([SQLField(**field2_args), SQLField(**field1_args)])
        self.assertEqual(
            Command.diff_couch_and_sql(doc, obj).split("\n"), [
                "slug: couch value 'texture' != sql value 'temp'",
                "is_required: couch value 'True' != sql value 'False'",
                "label: couch value 'Texture' != sql value 'F'",
                "choices: couch value '['soft', 'spiky']' != sql value '['32', '212']'",
                "slug: couch value 'temp' != sql value 'texture'",
                "is_required: couch value 'False' != sql value 'True'",
                "label: couch value 'F' != sql value 'Texture'",
                "choices: couch value '['32', '212']' != sql value '['soft', 'spiky']'",
            ]
        )

        # Identical data
        obj.set_fields([SQLField(**field1_args), SQLField(**field2_args)])
        self.assertIsNone(Command.diff_couch_and_sql(doc, obj))
