from __future__ import absolute_import, unicode_literals

from django.test import SimpleTestCase

from corehq.apps.userreports.models import Validation
from corehq.apps.userreports.tests.utils import get_sample_data_source, get_sample_doc_and_indicators


class DataSourceConfigurationTest(SimpleTestCase):

    def setUp(self):
        self.config = get_sample_data_source()
        self.config.validations = [
            Validation.wrap({
                "name": "is_starred_valid",
                "error_message": "is_starred has unexpected value",
                "expression": {
                    "type": "boolean_expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": "is_starred"
                    },
                    "operator": "in",
                    "property_value": ["yes", "no"]
                }
            })
        ]

    def test_is_starred_validation(self):
        sample_doc, expected_indicators = get_sample_doc_and_indicators()

        self.assertIsNone(self.config.validate_document(sample_doc))

        sample_doc['is_starred'] = 'what is a star?'

        with self.assertRaisesRegexp(Exception, "is_starred has unexpected value"):
            self.config.validate_document(sample_doc)
