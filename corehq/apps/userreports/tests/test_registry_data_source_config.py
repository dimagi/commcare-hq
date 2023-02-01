import datetime
from unittest.mock import MagicMock, create_autospec, patch

from django.test import SimpleTestCase, TestCase

from jsonobject.exceptions import BadValueError

from corehq.apps.domain.shortcuts import create_user
from corehq.apps.registry.exceptions import RegistryAccessDenied
from corehq.apps.registry.helper import DataRegistryHelper
from corehq.apps.registry.tests.utils import (
    Invitation,
    create_registry_for_test,
)
from corehq.apps.userreports.models import RegistryDataSourceConfiguration
from corehq.apps.userreports.tests.utils import (
    get_sample_doc_and_indicators,
    get_sample_registry_data_source,
)
from corehq.sql_db.connections import UCR_ENGINE_ID


@patch('corehq.apps.userreports.models.AllowedUCRExpressionSettings.disallowed_ucr_expressions', MagicMock(return_value=[]))
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
            'commcare_project',
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
        for expected, actual in zip(expected_columns, cols):
            self.assertEqual(expected, actual.id)

    @patch('corehq.apps.userreports.specs.datetime')
    def test_indicators(self, datetime_mock):
        fake_time_now = datetime.datetime(2015, 4, 24, 12, 30, 8, 24886)
        datetime_mock.utcnow.return_value = fake_time_now
        # indicators
        sample_doc, expected_indicators = get_sample_doc_and_indicators(fake_time_now)
        expected_indicators["commcare_project"] = sample_doc["domain"]
        [results] = self.config.get_all_values(sample_doc)
        for result in results:
            self.assertEqual(expected_indicators[result.column.id], result.value)

    def test_configured_filter_validation(self):
        source = self.config.to_json()
        config = RegistryDataSourceConfiguration.wrap(source)
        config.validate()


class RegistryDataSourceConfigurationDbTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = create_user("admin", "123")
        cls.addClassCleanup(cls.user.delete, None, None)

        cls.owning_domain = 'foo_bar'
        cls.registry = create_registry_for_test(cls.user, cls.owning_domain, invitations=[
            Invitation('foo'), Invitation('bar'),
        ], name='foo_bar')

        for domain, table in [('foo', 'foo1'),
                              ('foo', 'foo2'),
                              ('bar', 'bar1')]:
            config = RegistryDataSourceConfiguration(
                domain=domain,
                table_id=table,
                referenced_doc_type='CommCareCase',
                registry_slug=cls.registry.slug)
            config.save()
            cls.addClassCleanup(config.delete)

    def test_by_domain_returns_relevant_report_configs(self):
        results = RegistryDataSourceConfiguration.by_domain('foo')
        self.assertEqual(len(results), 2)
        self.assertEqual({r.table_id for r in results}, {'foo1', 'foo2'})

    def test_by_domain_returns_empty(self):
        results = RegistryDataSourceConfiguration.by_domain('not-foo')
        self.assertEqual(results, [])

    def test_all_returns_expected_result(self):
        results = list(RegistryDataSourceConfiguration.all())
        self.assertEqual(len(results), 3)
        self.assertEqual({r.table_id for r in results},
                         {'foo1', 'foo2', 'bar1'})

    def test_registry_slug_is_required(self):
        with self.assertRaises(BadValueError):
            RegistryDataSourceConfiguration(
                domain='domain', table_id='table', referenced_doc_type='CommCareCase'
            ).save()

    def test_registry_global_validation(self):
        # global config in owning domain
        config = RegistryDataSourceConfiguration(
            domain=self.owning_domain, table_id='table', referenced_doc_type='CommCareCase',
            globally_accessible=True, registry_slug=self.registry.slug
        )
        config.save()
        self.addCleanup(config.delete)

        # global config in participating domain (not owner)
        with self.assertRaises(RegistryAccessDenied):
            RegistryDataSourceConfiguration(
                domain='foo', table_id='table',
                referenced_doc_type='CommCareCase',
                globally_accessible=True, registry_slug=self.registry.slug
            ).save()
