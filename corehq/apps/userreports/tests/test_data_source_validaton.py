from __future__ import absolute_import, unicode_literals

from django.test import SimpleTestCase

from corehq.apps.userreports.exceptions import ValidationError
from corehq.apps.userreports.models import Validation
from corehq.apps.userreports.tests.utils import get_sample_data_source, get_sample_doc_and_indicators


class DataSourceValidationTest(SimpleTestCase):

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

        with self.assertRaisesRegex(ValidationError, "is_starred has unexpected value"):
            self.config.validate_document(sample_doc)

    def test_multiple_validations(self):
        self.config.validations = self.config.validations + [
            Validation.wrap({
                "name": "a_second_validation",
                "error_message": "another starred validation",
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
        sample_doc, expected_indicators = get_sample_doc_and_indicators()

        self.assertIsNone(self.config.validate_document(sample_doc))

        sample_doc['is_starred'] = 'what is a star?'

        try:
            self.config.validate_document(sample_doc)
        except ValidationError as e:
            self.assertEquals(len(e.errors), 2)
        else:
            self.fail("There were no validation errors returned")
