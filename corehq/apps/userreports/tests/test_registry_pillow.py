from django.test import TestCase
from mock import patch

from corehq.apps.registry.tests.utils import create_registry_for_test, Invitation, Grant
from corehq.apps.userreports.models import (
    RegistryDataSourceConfiguration,
)
from corehq.apps.userreports.pillow import (
    RegistryDataSourceTableManager,
)
from corehq.apps.userreports.tests.utils import (
    get_sample_registry_data_source,
)


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
