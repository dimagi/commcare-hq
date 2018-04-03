# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.serializers.python import Deserializer
from django.test import SimpleTestCase


class TestJSONFieldSerialization(SimpleTestCase):
    """See https://github.com/bradjasper/django-jsonfield/pull/173"""

    def test(self):
        serialized_model_with_primary_key = {
            'model': 'form_processor.XFormInstanceSQL', 'pk': 1, 'fields': {'auth_context': '{}'}
        }
        serialized_model_with_natural_key = {
            'model': 'form_processor.XFormInstanceSQL', 'fields': {'auth_context': '{}'}
        }

        def _test_json_field_after_serialization(serialized):
            for obj in Deserializer([serialized]):
                self.assertIsInstance(obj.object.auth_context, dict)

        _test_json_field_after_serialization(serialized_model_with_primary_key)
        _test_json_field_after_serialization(serialized_model_with_natural_key)
