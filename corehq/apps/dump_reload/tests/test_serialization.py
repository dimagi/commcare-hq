import json
from io import StringIO
from unittest.mock import patch

from django.core.serializers.python import Deserializer
from django.test import SimpleTestCase

from corehq.apps.dump_reload.sql.dump import SqlDataDumper
from corehq.form_processor.models.cases import CaseTransaction, CommCareCase
from corehq.form_processor.models.forms import XFormInstance, XFormOperation


class TestJSONFieldSerialization(SimpleTestCase):
    """
    See https://github.com/bradjasper/django-jsonfield/pull/173
    We just need to test that a model that uses jsonfield.JSONField is serialized correctly
    """

    def test(self):
        serialized_model_with_primary_key = {
            'model': 'accounting.BillingContactInfo', 'pk': 1, 'fields': {'email_list': '{}'}
        }
        serialized_model_with_natural_key = {
            'model': 'accounting.BillingContactInfo', 'fields': {'email_list': '{}'}
        }

        def _test_json_field_after_serialization(serialized):
            for obj in Deserializer([serialized]):
                self.assertIsInstance(obj.object.email_list, dict)

        _test_json_field_after_serialization(serialized_model_with_primary_key)
        _test_json_field_after_serialization(serialized_model_with_natural_key)


class TestForeignKeyFieldSerialization(SimpleTestCase):
    """
    We use natural foreign keys when dumping SQL data, but CommCareCase and XFormInstance have natural_key methods
    that intentionally return a string for the case_id or form_id, rather than a tuple as Django recommends for
    all natural_key methods. We made this decision to optimize loading deserialized data back into a database. If
    the natural_key method returns a tuple, it will use the get_by_natural_key method on the foreign key model's
    default object manager to fetch the foreign keyed object, resulting in a database lookup everytime we write
    a model that foreign keys to cases or forms in SqlDataLoader.
    """

    def test_serialized_foreign_key_field_referencing_User_returns_an_iterable(self):
        from django.contrib.auth.models import User

        from corehq.apps.users.models import SQLUserData
        user = User(username='testuser')
        user_data = SQLUserData(django_user=user, data={'test': 1})

        output_stream = StringIO()
        with patch('corehq.apps.dump_reload.sql.dump.get_objects_to_dump', return_value=[user_data]):
            SqlDataDumper('test', [], []).dump(output_stream)

        deserialized_model = json.loads(output_stream.getvalue())
        fk_field = deserialized_model['fields']['django_user']
        self.assertEqual(fk_field, ['testuser'])

    def test_serialized_foreign_key_field_referencing_CommCareCase_returns_a_str(self):
        cc_case = CommCareCase(domain='test', case_id='abc123')
        transaction = CaseTransaction(case=cc_case)

        output_stream = StringIO()
        with patch('corehq.apps.dump_reload.sql.dump.get_objects_to_dump', return_value=[transaction]):
            SqlDataDumper('test', [], []).dump(output_stream)

        deserialized_model = json.loads(output_stream.getvalue())
        fk_field = deserialized_model['fields']['case']
        self.assertEqual(fk_field, 'abc123')

    def test_serialized_foreign_key_field_referencing_XFormInstance_returns_a_str(self):
        xform = XFormInstance(domain='test', form_id='abc123')
        operation = XFormOperation(form=xform)

        output_stream = StringIO()
        with patch('corehq.apps.dump_reload.sql.dump.get_objects_to_dump', return_value=[operation]):
            SqlDataDumper('test', [], []).dump(output_stream)

        deserialized_model = json.loads(output_stream.getvalue())
        fk_field = deserialized_model['fields']['form']
        self.assertEqual(fk_field, 'abc123')
