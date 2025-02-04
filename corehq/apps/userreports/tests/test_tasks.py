from datetime import datetime
from unittest.mock import Mock, call, patch

from django.test import SimpleTestCase, TestCase

from corehq.apps.userreports.tasks import (
    rebuild_indicators,
    rebuild_indicators_in_place,
    resume_building_indicators,
    time_in_range,
)
from corehq.apps.userreports.tests.test_view import ConfigurableReportTestMixin
from corehq.apps.userreports.util import get_ucr_datasource_config_by_id

TEST_SETTINGS = {
    '*': [(0, 4), (12, 23)],
    7: [(0, 23)]
}


class TimeInRange(SimpleTestCase):

    def test_sunday_all_day(self):
        for hour in range(24):
            time = datetime(2018, 1, 21, hour)
            self.assertTrue(time_in_range(time, TEST_SETTINGS))

    def test_monday(self):
        for hour in range(0, 4):
            time = datetime(2018, 1, 22, hour)
            self.assertTrue(time_in_range(time, TEST_SETTINGS))

        for hour in range(5, 12):
            time = datetime(2018, 1, 22, hour)
            self.assertFalse(time_in_range(time, TEST_SETTINGS))

        for hour in range(12, 23):
            time = datetime(2018, 1, 22, hour)
            self.assertTrue(time_in_range(time, TEST_SETTINGS))


class BaseTestRebuildIndicators(ConfigurableReportTestMixin, TestCase):
    @classmethod
    def tearDownClass(cls):
        cls._delete_everything()
        super().tearDownClass()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data_source_config = cls._sample_data_source_config()
        cls.data_source_config.save()


class TestRebuildIndicators(BaseTestRebuildIndicators):
    @patch('corehq.apps.userreports.tasks._report_ucr_rebuild_metrics')
    @patch('corehq.apps.userreports.tasks._iteratively_build_table')
    @patch('corehq.apps.userreports.tasks._get_rows_count_from_existing_table')
    @patch('corehq.apps.userreports.tasks.get_indicator_adapter')
    def test_rebuild_indicators(self, mock_get_indicator_adapter, mock_get_rows_count_from_existing_table,
                                mock_iteratively_build_table, mock_report_ucr_rebuild_metrics):
        mocked_adapter = Mock()
        mock_get_indicator_adapter.return_value = mocked_adapter
        self.data_source_config.meta.build.awaiting = True
        self.data_source_config.meta.build.initiated = None
        self.data_source_config.meta.build.finished = True
        self.data_source_config.meta.build.rebuilt_asynchronously = True
        self.data_source_config.save()

        data_source_config = get_ucr_datasource_config_by_id(self.data_source_config.get_id)
        self.assertTrue(data_source_config.meta.build.awaiting)
        self.assertIsNone(data_source_config.meta.build.initiated)
        self.assertTrue(data_source_config.meta.build.finished)
        self.assertTrue(data_source_config.meta.build.rebuilt_asynchronously)

        rebuild_indicators(self.data_source_config.get_id, source="test_rebuild_indicators")

        # test calls
        mock_get_indicator_adapter.assert_called_once()
        mock_get_rows_count_from_existing_table.assert_called_once()
        mocked_adapter.assert_has_calls([
            call.rebuild_table(initiated_by=None, source="test_rebuild_indicators", skip_log=False, diffs=None)
        ])
        mock_iteratively_build_table.assert_called_once()
        mock_report_ucr_rebuild_metrics.assert_called_once()

        # test data source config updates
        data_source_config = get_ucr_datasource_config_by_id(self.data_source_config.get_id)
        self.assertFalse(data_source_config.meta.build.awaiting)
        self.assertIsNotNone(data_source_config.meta.build.initiated)
        self.assertFalse(data_source_config.meta.build.finished)
        self.assertFalse(data_source_config.meta.build.rebuilt_asynchronously)


class TestRebuildIndicatorsInPlace(BaseTestRebuildIndicators):
    @patch('corehq.apps.userreports.tasks._report_ucr_rebuild_metrics')
    @patch('corehq.apps.userreports.tasks._iteratively_build_table')
    @patch('corehq.apps.userreports.tasks._get_rows_count_from_existing_table')
    @patch('corehq.apps.userreports.tasks.get_indicator_adapter')
    def test_rebuild_indicators_in_place(self, mock_get_indicator_adapter, mock_get_rows_count_from_existing_table,
                                         mock_iteratively_build_table, mock_report_ucr_rebuild_metrics):
        mocked_adapter = Mock()
        mock_get_indicator_adapter.return_value = mocked_adapter
        self.data_source_config.meta.build.awaiting = True
        self.data_source_config.meta.build.initiated_in_place = None
        self.data_source_config.meta.build.finished_in_place = True
        self.data_source_config.meta.build.rebuilt_asynchronously = True
        self.data_source_config.save()

        data_source_config = get_ucr_datasource_config_by_id(self.data_source_config.get_id)
        self.assertTrue(data_source_config.meta.build.awaiting)
        self.assertIsNone(data_source_config.meta.build.initiated_in_place)
        self.assertTrue(data_source_config.meta.build.finished_in_place)
        self.assertTrue(data_source_config.meta.build.rebuilt_asynchronously)

        rebuild_indicators_in_place(self.data_source_config.get_id, source="test_rebuild_indicators_in_place")

        # test calls
        mock_get_indicator_adapter.assert_called_once()
        mock_get_rows_count_from_existing_table.assert_called_once()
        mocked_adapter.assert_has_calls([
            call.build_table(initiated_by=None, source="test_rebuild_indicators_in_place")
        ])
        mock_iteratively_build_table.assert_called_once()
        mock_report_ucr_rebuild_metrics.assert_called_once()

        # test data source config updates
        data_source_config = get_ucr_datasource_config_by_id(self.data_source_config.get_id)
        self.assertFalse(data_source_config.meta.build.awaiting)
        self.assertIsNotNone(data_source_config.meta.build.initiated_in_place)
        self.assertFalse(data_source_config.meta.build.finished_in_place)
        self.assertFalse(data_source_config.meta.build.rebuilt_asynchronously)


class TestResumeBuildingIndicators(BaseTestRebuildIndicators):
    @patch('corehq.apps.userreports.tasks._iteratively_build_table')
    @patch('corehq.apps.userreports.tasks.get_indicator_adapter')
    def test_resume_building_indicators(self, mock_get_indicator_adapter, mock_iteratively_build_table):
        mocked_adapter = Mock()
        mock_get_indicator_adapter.return_value = mocked_adapter
        self.data_source_config.meta.build.awaiting = True
        self.data_source_config.save()

        data_source_config = get_ucr_datasource_config_by_id(self.data_source_config.get_id)
        self.assertTrue(data_source_config.meta.build.awaiting)

        resume_building_indicators(self.data_source_config.get_id)

        # test calls
        mock_get_indicator_adapter.assert_called_once()
        mocked_adapter.assert_has_calls([
            call.log_table_build(initiated_by=None, source='resume_building_indicators')
        ])
        mock_iteratively_build_table.assert_called_once()

        # test data source config updates
        data_source_config = get_ucr_datasource_config_by_id(self.data_source_config.get_id)
        self.assertFalse(data_source_config.meta.build.awaiting)
