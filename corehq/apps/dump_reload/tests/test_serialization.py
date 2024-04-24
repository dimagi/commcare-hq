import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.serializers.python import Deserializer
from django.test import SimpleTestCase

from corehq.apps.dump_reload.sql.dump import SqlDataDumper
from corehq.apps.users.models import SQLUserData
from corehq.apps.users.models_role import Permission, RolePermission, UserRole
from corehq.form_processor.models.cases import CaseTransaction, CommCareCase
from corehq.form_processor.models.forms import XFormInstance, XFormOperation
from corehq.apps.registry.models import DataRegistry, RegistryGrant


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

    def test_natural_foreign_key_returns_iterable_when_serialized(self):
        user = User(username='testuser')
        user_data = SQLUserData(django_user=user, data={'test': 1})

        output_stream = StringIO()
        with patch('corehq.apps.dump_reload.sql.dump.get_objects_to_dump', return_value=[user_data]):
            SqlDataDumper('test', [], []).dump(output_stream)

        deserialized_model = json.loads(output_stream.getvalue())
        fk_field = deserialized_model['fields']['django_user']
        self.assertEqual(fk_field, ['testuser'])

    def test_foreign_key_on_model_without_natural_key_returns_primary_key_when_serialized(self):
        data_registry = DataRegistry(pk=500, domain='test', name='test-registry')
        registry_grant = RegistryGrant(pk=10, registry=data_registry, from_domain='test', to_domains=['to-test'])

        output_stream = StringIO()
        with patch('corehq.apps.dump_reload.sql.dump.get_objects_to_dump', return_value=[registry_grant]):
            SqlDataDumper('test', [], []).dump(output_stream)

        deserialized_model = json.loads(output_stream.getvalue())
        pk_field = deserialized_model['pk']
        self.assertEqual(pk_field, 10)
        registry_field = deserialized_model['fields']['registry']
        self.assertEqual(registry_field, 500)

    def test_natural_foreign_key_for_Permission_returns_tuple_when_serialized(self):
        role = UserRole(pk=10, domain='test', name='test-role')
        permission = Permission(pk=500, value='test')
        role_permission = RolePermission(role=role, permission_fk=permission)

        output_stream = StringIO()
        with patch('corehq.apps.dump_reload.sql.dump.get_objects_to_dump', return_value=[role_permission]):
            SqlDataDumper('test', [], []).dump(output_stream)

        deserialized_model = json.loads(output_stream.getvalue())
        role_field = deserialized_model['fields']['role']
        self.assertEqual(role_field, 10)
        permission_field = deserialized_model['fields']['permission_fk']
        self.assertEqual(permission_field, ['test'])

    def test_natural_foreign_key_for_CommCareCase_returns_str_when_serialized(self):
        cc_case = CommCareCase(domain='test', case_id='abc123')
        transaction = CaseTransaction(case=cc_case)

        output_stream = StringIO()
        with patch('corehq.apps.dump_reload.sql.dump.get_objects_to_dump', return_value=[transaction]):
            SqlDataDumper('test', [], []).dump(output_stream)

        deserialized_model = json.loads(output_stream.getvalue())
        fk_field = deserialized_model['fields']['case']
        self.assertEqual(fk_field, 'abc123')

    def test_natural_foreign_key_for_XFormInstance_returns_str_when_serialized(self):
        xform = XFormInstance(domain='test', form_id='abc123')
        operation = XFormOperation(form=xform)

        output_stream = StringIO()
        with patch('corehq.apps.dump_reload.sql.dump.get_objects_to_dump', return_value=[operation]):
            SqlDataDumper('test', [], []).dump(output_stream)

        deserialized_model = json.loads(output_stream.getvalue())
        fk_field = deserialized_model['fields']['form']
        self.assertEqual(fk_field, 'abc123')
