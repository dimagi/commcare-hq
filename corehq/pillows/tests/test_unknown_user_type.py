from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase

from corehq.pillows.tasks import fix_user_types
from corehq.pillows.utils import (
    UNKNOWN_USER_TYPE,
    get_user_type,
    get_user_type_deep_cache_for_unknown_users,
)


class TestUnknownUserType(TestCase):

    def setUp(self):
        self.user_id = uuid4().hex
        self.addCleanup(get_user_type.clear, self.user_id)
        self.addCleanup(get_user_type_deep_cache_for_unknown_users.clear, self.user_id)

    def test_unknown_result_is_remembered_as_unknown(self):
        assert get_user_type(self.user_id) == UNKNOWN_USER_TYPE
        assert get_user_type_deep_cache_for_unknown_users(self.user_id) == UNKNOWN_USER_TYPE

    @patch('corehq.pillows.tasks.resave_es_forms_with_unknown_user_type')
    def test_fix_user_types_skips_users_still_unknown(self, resave):
        get_user_type(self.user_id)
        with patch('corehq.pillows.tasks._get_unknown_user_type_user_ids', return_value=[self.user_id]):
            fix_user_types()
        resave.delay.assert_not_called()
