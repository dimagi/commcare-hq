import uuid

from django.test import TestCase
from mock import patch

from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from corehq.apps.registry.tests.utils import create_registry_for_test, Invitation, Grant
from corehq.apps.userreports.models import (
    RegistryDataSourceConfiguration
)
from corehq.apps.userreports.pillow import (
    RegistryDataSourceTableManager, get_kafka_ucr_registry_pillow,
)
from corehq.apps.userreports.tests.utils import (
    get_sample_registry_data_source,
)
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.util.test_utils import create_and_save_a_case
from testapps.test_pillowtop.utils import process_pillow_changes


@patch('corehq.apps.userreports.pillow.all_domains_with_migrations_in_progress', return_value=set())
class RegistryDataSourceTableManagerTest(TestCase):
    domain = "user-reports"

    @classmethod
    def setUpTestData(cls):
        cls.registry_1 = create_registry_for_test('foo_bar', invitations=[
            Invitation(cls.domain), Invitation("granted-domain"),
        ], grants=[Grant("granted-domain", to_domains=[cls.domain])], name='test')

        cls.registry_2 = create_registry_for_test('bazz', invitations=[
            Invitation(cls.domain), Invitation("other-domain"),
        ], grants=[Grant("other-domain", to_domains=[cls.domain])], name='bazz')

    def tearDown(self):
        for config in RegistryDataSourceConfiguration.all():
            config.get_db().delete_doc(config.get_id)

    def test_bootstrap(self, ignored_mock):
        self._bootstrap_manager_with_data_source()

    def test_ignore_migrating_domains(self, mock_domains_with_migrations):
        mock_domains_with_migrations.return_value = {self.domain}
        data_source_1 = get_sample_registry_data_source(domain=self.domain, registry_slug=self.registry_1.slug)
        data_source_1.save()
        table_manager = RegistryDataSourceTableManager()
        table_manager.bootstrap([data_source_1])
        # the "user-reports" domain is excluded because it has a migration in progress
        self.assertEqual({"granted-domain"}, table_manager.relevant_domains)

    def test_update_modified_since_remove_deactivated(self, ignored_mock):
        data_source_1, table_manager = self._bootstrap_manager_with_data_source()
        data_source_1.is_deactivated = True

        table_manager._add_or_update_data_source(data_source_1)
        self.assertEqual(0, len(table_manager.relevant_domains))

    def test_update_modified_since_add_adapter_same_domain(self, ignored_mock):
        data_source_1, table_manager = self._bootstrap_manager_with_data_source()

        # test in same domain, same registry
        data_source_2 = get_sample_registry_data_source(domain=self.domain, registry_slug=self.registry_1.slug)
        data_source_2.save()
        table_manager._add_or_update_data_source(data_source_2)
        expected_domains = {self.domain, "granted-domain"}
        self.assertEqual(expected_domains, table_manager.relevant_domains)
        for domain in expected_domains:
            self.assertEqual(
                {data_source_1, data_source_2},
                {adapter.config for adapter in table_manager.get_adapters(domain)}
            )

    def test_update_modified_since_add_adapter_different_domain(self, ignored_mock):
        data_source_1, table_manager = self._bootstrap_manager_with_data_source()

        data_source_2 = get_sample_registry_data_source(domain=self.domain, registry_slug=self.registry_2.slug)
        data_source_2.save()
        table_manager._add_or_update_data_source(data_source_2)
        expected_domains = {self.domain, "granted-domain", "other-domain"}
        self.assertEqual(expected_domains, table_manager.relevant_domains)

        self.assertEqual(
            {data_source_2},
            {table_adapter.config for table_adapter in table_manager.get_adapters("other-domain")}
        )
        self.assertEqual(
            {data_source_1, data_source_2},
            {table_adapter.config for table_adapter in table_manager.get_adapters(self.domain)}
        )

    def test_update_modified_since_refresh_same_configs(self, ignored_mock):
        data_source_1, table_manager = self._bootstrap_manager_with_data_source()

        # add a new grant and check that it get's picked up
        grant = self.registry_1.grants.create(
            from_domain="new-domain",
            to_domains=[self.domain],
        )
        self.addCleanup(grant.delete)

        table_manager._add_or_update_data_source(data_source_1)
        expected_domains = {self.domain, "granted-domain", "new-domain"}
        self.assertEqual(expected_domains, table_manager.relevant_domains)
        for domain in expected_domains:
            self.assertEqual(
                {data_source_1},
                {table_adapter.config for table_adapter in table_manager.get_adapters(domain)}
            )

    def _bootstrap_manager_with_data_source(self):
        data_source_1 = get_sample_registry_data_source(domain=self.domain, registry_slug=self.registry_1.slug)
        data_source_1.save()
        table_manager = RegistryDataSourceTableManager()
        table_manager.bootstrap([data_source_1])

        # the data source domain + domains it has been granted access to
        expected_domains = {self.domain, "granted-domain"}
        self.assertEqual(expected_domains, table_manager.relevant_domains)
        for domain in expected_domains:
            self.assertEqual(
                {data_source_1},
                {adapter.config for adapter in table_manager.get_adapters(domain)}
            )

        return data_source_1, table_manager


@use_sql_backend
class RegistryUcrPillowTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.registry_owner_domain = "registry-owner"
        cls.participator_1 = "domain1"
        cls.participator_2 = "domain2"
        cls.participator_3 = "domain3"
        cls.participants = (cls.participator_1, cls.participator_2, cls.participator_3)
        invitations = [Invitation(domain) for domain in cls.participants]
        grants = [
            Grant(from_domain=cls.participator_1, to_domains=[cls.participator_2, cls.participator_3]),
            Grant(from_domain=cls.participator_2, to_domains=[cls.participator_1]),
        ]
        cls.registry_1 = create_registry_for_test(
            cls.registry_owner_domain,
            invitations=invitations,
            grants=grants,
        )

        # UCR in domain1 should get data from itself and from domain2
        cls.config = get_sample_registry_data_source(
            domain=cls.participator_1, registry_slug=cls.registry_1.slug
        )
        cls.config.save()
        cls.adapter = get_indicator_adapter(cls.config)
        cls.adapter.build_table()
        cls.pillow = get_kafka_ucr_registry_pillow(ucr_configs=[cls.config], processor_chunk_size=100)

    @classmethod
    def tearDownClass(cls):
        cls.config.delete()
        cls.adapter.drop_table()
        super().tearDownClass()

    def tearDown(self):
        self.adapter.clear_table()
        delete_all_cases()
        delete_all_xforms()

    def test_registry_ucr(self):
        expected = {}
        with process_pillow_changes(self.pillow):
            for domain in self.participants:
                case = create_and_save_a_case(
                    domain, uuid.uuid4().hex, f"name-{domain}",
                    case_type="ticket", case_properties={
                        "category": "bug",
                        "tags": "easy-win public",
                        "is_starred": "yes",
                        "estimate": "2.3",
                        "priority": "4",
                    })
                if domain != self.participator_3:
                    # 3 does not grant either of the others access
                    expected[case.case_id] = domain

        self.assertEqual(2, self.adapter.get_query_object().count())
        actual = {
            row.doc_id: row.domain
            for row in self.adapter.get_query_object()
        }
        self.assertDictEqual(actual, expected)

    def test_global_registry_ucr(self):
        """Globally accessible UCR get's data from all participating domains regardless
        of grants.
        """
        config = get_sample_registry_data_source(
            domain=self.registry_owner_domain, registry_slug=self.registry_1.slug,
            globally_accessible=True
        )
        config.save()
        self.addCleanup(config.delete)

        adapter = get_indicator_adapter(config)
        adapter.build_table()
        self.addCleanup(adapter.drop_table)

        pillow = get_kafka_ucr_registry_pillow(ucr_configs=[config], processor_chunk_size=100)

        expected = {}
        with process_pillow_changes(pillow):
            for domain in self.participants:
                case = create_and_save_a_case(
                    domain, uuid.uuid4().hex, f"name-{domain}",
                    case_type="ticket", case_properties={
                        "category": "bug",
                        "tags": "easy-win public",
                        "is_starred": "yes",
                        "estimate": "2.3",
                        "priority": "4",
                    })
                expected[case.case_id] = domain

        self.assertEqual(3, adapter.get_query_object().count())
        actual = {
            row.doc_id: row.domain
            for row in adapter.get_query_object()
        }
        self.assertDictEqual(actual, expected)
