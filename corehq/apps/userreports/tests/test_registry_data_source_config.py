import datetime
import time
from unittest.mock import create_autospec, Mock, patch

from django.test import SimpleTestCase, TestCase
from jsonobject.exceptions import BadValueError

from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.models import DataSourceConfiguration, RegistryDataSourceConfiguration
from corehq.apps.userreports.tests.utils import (
    get_sample_doc_and_indicators, get_sample_registry_data_source,
)
from corehq.sql_db.connections import UCR_ENGINE_ID


class RegistryDataSourceConfigurationTest(SimpleTestCase):

    def setUp(self):
        self.config = get_sample_registry_data_source()
        mock_helper = Mock(visible_domains={"user-reports", "granted-domain"})
        self.patcher = patch("corehq.apps.userreports.models.DataRegistryHelper", return_value=mock_helper)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_metadata(self):
        # metadata
        self.assertEqual('user-reports', self.config.domain)
        self.assertEqual('CommCareCase', self.config.referenced_doc_type)
        self.assertEqual('CommBugz', self.config.display_name)
        self.assertEqual('sample', self.config.table_id)
        self.assertEqual(UCR_ENGINE_ID, self.config.engine_id)

    def test_filters(self):
        not_matching = [
            {"doc_type": "NotCommCareCase", "domain": 'user-reports', "type": 'ticket'},
            {"doc_type": "CommCareCase", "domain": 'not-user-reports', "type": 'ticket'},
            {"doc_type": "CommCareCase", "domain": 'user-reports', "type": 'not-ticket'},
        ]
        for document in not_matching:
            self.assertFalse(self.config.filter(document))
            self.assertEqual([], self.config.get_all_values(document))

        matching = [
            {"doc_type": "CommCareCase", "domain": 'user-reports', "type": 'ticket'},
            {"doc_type": "CommCareCase", "domain": 'granted-domain', "type": 'ticket'},
        ]
        for document in matching:
            self.assertTrue(self.config.filter(document))

    def test_columns(self):
        expected_columns = [
            'doc_id',
            'inserted_at',
            'domain',
            'date',
            'owner',
            'count',
            'category_bug', 'category_feature', 'category_app', 'category_schedule',
            'tags_easy-win', 'tags_potential-dupe', 'tags_roadmap', 'tags_public',
            'is_starred',
            'estimate',
            'priority'
        ]
        cols = self.config.get_columns()
        self.assertEqual(len(expected_columns), len(cols))
        for i, col in enumerate(expected_columns):
            col_back = cols[i]
            self.assertEqual(col, col_back.id)

    @patch('corehq.apps.userreports.specs.datetime')
    def test_indicators(self, datetime_mock):
        fake_time_now = datetime.datetime(2015, 4, 24, 12, 30, 8, 24886)
        datetime_mock.utcnow.return_value = fake_time_now
        # indicators
        sample_doc, expected_indicators = get_sample_doc_and_indicators(fake_time_now)
        expected_indicators["domain"] = sample_doc["domain"]
        [results] = self.config.get_all_values(sample_doc)
        for result in results:
            self.assertEqual(expected_indicators[result.column.id], result.value)
