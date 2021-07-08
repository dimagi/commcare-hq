import datetime
import time
from unittest.mock import create_autospec, Mock, patch

from django.test import SimpleTestCase, TestCase
from jsonobject.exceptions import BadValueError

from corehq.apps.registry.helper import DataRegistryHelper
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.models import RegistryDataSourceConfiguration, RegistryDataSourceConfiguration
from corehq.apps.userreports.tests.utils import (
    get_sample_doc_and_indicators, get_sample_registry_data_source,
)
from corehq.sql_db.connections import UCR_ENGINE_ID


class RegistryDataSourceConfigurationTest(SimpleTestCase):

    def setUp(self):
        self.config = get_sample_registry_data_source()
        mock_helper = create_autospec(
            DataRegistryHelper, spec_set=True, instance=True,
            visible_domains={"user-reports", "granted-domain"},
            participating_domains={"user-reports", "granted-domain", "other-domain"}
        )
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

    def test_filters_doc_type(self):
        self._test_filters('doc_type', ["CommCareCase"], ["NotCommCareCase"])

    def test_filters_case_type(self):
        self._test_filters('type', ["ticket"], ["not-ticket"])

    def test_filters_domain(self):
        print(self.config.data_domains)
        self._test_filters('domain', ["user-reports", "granted-domain"], ["other-domain"])

    def test_filters_domain_global(self):
        self.config.globally_accessible = True
        self._test_filters('domain', ["user-reports", "granted-domain", "other-domain"], ["not-participating"])

    def _test_filters(self, test_field, matching_values, not_matching_values):
        """Test helper to test filtering on a specific field"""

        base_doc = {"doc_type": "CommCareCase", "domain": 'user-reports', "type": 'ticket'}
        self.assertTrue(self.config.filter(base_doc), "Test setup error. Base doc does not match the filters")

        for matching_value in matching_values:
            matching = {**base_doc, **{test_field: matching_value}}
            self.assertTrue(self.config.filter(matching), matching_value)

        for not_matching_value in not_matching_values:
            not_matching = {**base_doc, **{test_field: not_matching_value}}
            self.assertFalse(self.config.filter(not_matching), not_matching_value)
            self.assertEqual([], self.config.get_all_values(not_matching), not_matching_value)

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

    def test_configured_filter_validation(self):
        source = self.config.to_json()
        config = RegistryDataSourceConfiguration.wrap(source)
        config.validate()
