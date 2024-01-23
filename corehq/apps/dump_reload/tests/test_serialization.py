from django.core.serializers.python import Deserializer
from django.test import SimpleTestCase


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
