import uuid
from mock import MagicMock, patch

from django.test import SimpleTestCase
from django.core.cache import cache

from corehq.apps.reports.filters.devicelog import DeviceLogUsersFilter


class DeviceLogFilterTest(SimpleTestCase):
    domain = 'device-log-domain'

    def setUp(self):
        self.device_filter = DeviceLogUsersFilter(
            MagicMock(),
            self.domain,
        )
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_device_log_users_get_filters(self):
        self.device_filter.domain = uuid.uuid4().hex
        with patch(
                'corehq.apps.reports.filters.devicelog.fast_distinct_in_domain',
                return_value=['a', 'b']) as mocked_call:
            values = self.device_filter.get_filters(None)
            self.assertTrue(mocked_call.called)
            self.assertEqual(values, [{'name': 'a', 'show': True}, {'name': 'b', 'show': True}])

            values = self.device_filter.get_filters(None)

            self.assertEqual(values, [{'name': 'a', 'show': True}, {'name': 'b', 'show': True}])
            self.assertEqual(mocked_call.call_count, 1, 'Second call should hit cache')

    def test_device_log_users_get_filters_cache_bust(self):
        self.device_filter.domain = uuid.uuid4().hex
        with patch(
                'corehq.apps.reports.filters.devicelog.fast_distinct_in_domain',
                return_value=['a', 'b']) as mocked_call:
            values = self.device_filter.get_filters(None)
            self.assertTrue(mocked_call.called)
            self.assertEqual(values, [{'name': 'a', 'show': True}, {'name': 'b', 'show': True}])

            self.device_filter.domain = self.domain + '-new'  # Bust cache by changing domain
            self.device_filter.get_filters(None)
            self.assertEqual(mocked_call.call_count, 2)

            self.device_filter.field = uuid.uuid4().hex  # Bust cache by changing field
            self.device_filter.get_filters(None)
            self.assertEqual(mocked_call.call_count, 3)

            self.device_filter.get_filters(uuid.uuid4().hex)  # Bust cache by changing selected
            self.assertEqual(mocked_call.call_count, 4)
