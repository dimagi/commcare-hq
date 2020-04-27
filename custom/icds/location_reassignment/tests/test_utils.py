from collections import namedtuple
from unittest import TestCase

from mock import patch

from custom.icds.location_reassignment.const import (
    MOVE_OPERATION,
    SPLIT_OPERATION,
)
from custom.icds.location_reassignment.utils import deprecate_locations

Location = namedtuple("Location", ["location_id", "site_code", "metadata"])


class TestDeprecateLocation(TestCase):
    domain = "test"
    @classmethod
    def setUpClass(cls):
        cls.old_locations = [Location(location_id="123456", site_code='12', metadata={})]
        cls.new_locations = [Location(location_id="123457", site_code='13', metadata={}),
                             Location(location_id="123458", site_code='14', metadata={})]

    @patch('custom.icds.location_reassignment.utils.deactivate_users_at_location')
    @patch('custom.icds.location_reassignment.models.Transition.perform')
    def test_valid_operation(self, mock_perform, mock_deactivate_users):
        self.assertEqual(deprecate_locations(
            self.domain, self.old_locations, self.new_locations, SPLIT_OPERATION), [])
        self.assertEqual(mock_perform.call_count, 1)
        mock_deactivate_users.called_once_with("123456")
        self.assertEqual(mock_deactivate_users.call_count, 1)

    def test_invalid_operation(self):
        self.assertEqual(deprecate_locations(self.domain, self.old_locations, self.new_locations, MOVE_OPERATION),
                         ['Move operation: Got 2 new location.'])
