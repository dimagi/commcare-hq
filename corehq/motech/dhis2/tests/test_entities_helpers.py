import doctest

from django.test import SimpleTestCase

from corehq.motech.dhis2.entities_helpers import validate_tracked_entity
from corehq.motech.exceptions import ConfigurationError


class ValidateTrackedEntityTests(SimpleTestCase):

    def test_valid(self):
        """
        validate_tracked_entity() should not raise ConfigurationError
        """
        tracked_entity = {
            "orgUnit": "abc123",
            "trackedEntityType": "def456",
        }
        validate_tracked_entity(tracked_entity)

    def test_extra_key(self):
        tracked_entity = {
            "orgUnit": "abc123",
            "trackedEntityType": "def456",
            "hasWensleydale": False
        }
        with self.assertRaises(ConfigurationError):
            validate_tracked_entity(tracked_entity)

    def test_missing_key(self):
        tracked_entity = {
            "trackedEntityType": "def456",
        }
        with self.assertRaises(ConfigurationError):
            validate_tracked_entity(tracked_entity)

    def test_bad_data_type(self):
        tracked_entity = {
            "orgUnit": 0xabc123,
            "trackedEntityType": 0xdef456
        }
        with self.assertRaises(ConfigurationError):
            validate_tracked_entity(tracked_entity)


def test_doctests():
    from corehq.motech.dhis2 import entities_helpers

    results = doctest.testmod(entities_helpers)
    assert results.failed == 0
