import re

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from testil import assert_raises

from corehq.apps.registry.schema import REGISTRY_JSON_SCHEMA
from corehq.util.test_utils import generate_cases
from corehq.util.validation import JSONSchemaValidator


class RegistrySchemaValidationTests(SimpleTestCase):
    pass


@generate_cases([
    ([], None),
    ([{"case_type": "a"}, {"case_type": "b"}], None),
    ([{"case_type": 1}], re.compile("1 is not of type 'string'")),
    ([{}], re.compile("'case_type' is a required property")),
    ([{"case_name": "bob"}], re.compile("'case_type' is a required property")),
], RegistrySchemaValidationTests)
def test_schema_validation(self, data, error):
    with assert_raises(None if not error else ValidationError, msg=error):
        JSONSchemaValidator(REGISTRY_JSON_SCHEMA)(data)
