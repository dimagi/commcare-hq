import uuid

from django.test import TestCase

from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from corehq.apps.domain.shortcuts import create_user
from corehq.apps.registry.tests.utils import create_registry_for_test, Invitation, Grant
from corehq.apps.userreports.data_source_providers import RegistryDataSourceProvider
from corehq.apps.userreports.pillow import (
    RegistryDataSourceTableManager, get_kafka_ucr_registry_pillow,
)
from corehq.apps.userreports.tests.utils import (
    cleanup_ucr,
    get_sample_registry_data_source,
)
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.form_processor.tests.utils import sharded
from corehq.util.test_utils import create_and_save_a_case
from testapps.test_pillowtop.utils import process_pillow_changes


class RegistryDataSourceTableManagerTest(TestCase):
    domain = "user-reports"

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user("admin", "123")

        cls.registry_1 = create_registry_for_test(cls.user, 'foo_bar', invitations=[
            Invitation(cls.domain), Invitation("granted-domain"),
        ], grants=[Grant("granted-domain", to_domains=[cls.domain])], name='test')

        cls.registry_2 = create_registry_for_test(cls.user, 'bazz', invitations=[
            Invitation(cls.domain), Invitation("other-domain"),
        ], grants=[Grant("other-domain", to_domains=[cls.domain])], name='bazz')

    def test_bootstrap(self):
        self._bootstrap_manager_with_data_source()

    def test_update_modified_since_remove_deactivated(self):
        data_source_1, table_manager = self._bootstrap_manager_with_data_source()
        data_source_1 = type(data_source_1).get(data_source_1._id)  # HACK prevent ResourceConflict on save
        data_source_1.is_deactivated = True
        data_source_1.save()

        table_manager.refresh_cache()

        for domain in [self.domain, "granted-domain"]:
            assert table_manager.get_adapters(domain) == []

    def test_update_modified_since_add_adapter_same_domain(self):
        data_source_1, table_manager = self._bootstrap_manager_with_data_source()

        # test in same domain, same registry
        data_source_2 = get_sample_registry_data_source(domain=self.domain, registry_slug=self.registry_1.slug)
        data_source_2.save()
        self.addCleanup(cleanup_ucr, data_source_2)
        table_manager.refresh_cache()

        expected_domains = {self.domain, "granted-domain"}
        for domain in expected_domains:
            self.assertEqual(
                {data_source_1._id, data_source_2._id},
                {adapter.config_id for adapter in table_manager.get_adapters(domain)}
            )

    def test_update_modified_since_add_adapter_different_domain(self):
        data_source_1, table_manager = self._bootstrap_manager_with_data_source()

        data_source_2 = get_sample_registry_data_source(domain=self.domain, registry_slug=self.registry_2.slug)
        data_source_2.save()
        self.addCleanup(cleanup_ucr, data_source_2)
        table_manager.refresh_cache()

        self.assertEqual(
            {data_source_2._id},
            {table_adapter.config_id for table_adapter in table_manager.get_adapters("other-domain")}
        )
        self.assertEqual(
            {data_source_1._id, data_source_2._id},
            {table_adapter.config_id for table_adapter in table_manager.get_adapters(self.domain)}
        )

    def test_update_modified_since_refresh_same_configs(self):
        data_source_1, table_manager = self._bootstrap_manager_with_data_source()

        # add a new grant and check that it get's picked up
        self.registry_1.invitations.create(domain="new-domain").accept(self.user)
        grant = self.registry_1.grants.create(
            from_domain="new-domain",
            to_domains=[self.domain],
        )
        self.addCleanup(grant.delete)

        expected_domains = {self.domain, "granted-domain", "new-domain"}
        for domain in expected_domains:
            self.assertEqual(
                {data_source_1._id},
                {table_adapter.config_id for table_adapter in table_manager.get_adapters(domain)},
                domain,
            )

    def _bootstrap_manager_with_data_source(self):
        data_source_1 = get_sample_registry_data_source(domain=self.domain, registry_slug=self.registry_1.slug)
        data_source_1.save()
        self.addCleanup(cleanup_ucr, data_source_1)
        table_manager = RegistryDataSourceTableManager()

        # the data source domain + domains it has been granted access to
        for domain in [self.domain, "granted-domain"]:
            adapters = table_manager.get_adapters(domain)
            assert [data_source_1._id] == [a.config_id for a in adapters]

        return data_source_1, table_manager


@sharded
class RegistryUcrPillowTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user = create_user("admin", "123")

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
            cls.user,
            cls.registry_owner_domain,
            invitations=invitations,
            grants=grants,
        )

        # UCR in domain1 should get data from itself and from domain2
        cls.config = get_sample_registry_data_source(
            domain=cls.participator_1, registry_slug=cls.registry_1.slug
        )
        cls.config.save()
        cls.addClassCleanup(cls.config.delete)
        cls.adapter = get_indicator_adapter(cls.config)
        cls.adapter.build_table()
        cls.addClassCleanup(cls.adapter.drop_table)
        cls.pillow = get_kafka_ucr_registry_pillow(processor_chunk_size=100)

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
            row.doc_id: row.commcare_project
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

        pillow = get_kafka_ucr_registry_pillow(processor_chunk_size=100)

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
            row.doc_id: row.commcare_project
            for row in adapter.get_query_object()
        }
        self.assertDictEqual(actual, expected)


class RegistryDataSourceProviderTest(TestCase):
    domain = "user-reports"

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user("admin", "123")

        cls.registry_1 = create_registry_for_test(cls.user, 'foo_bar', invitations=[
            Invitation(cls.domain), Invitation("granted-domain"),
        ], grants=[Grant("granted-domain", to_domains=[cls.domain])], name='test')

        cls.registry_2 = create_registry_for_test(cls.user, 'bazz', invitations=[
            Invitation(cls.domain), Invitation("other-domain"),
        ], grants=[Grant("other-domain", to_domains=[cls.domain])], name='bazz')

        cls.data_source_1 = get_sample_registry_data_source(domain=cls.domain, registry_slug=cls.registry_1.slug)
        cls.data_source_1.save()
        cls.addClassCleanup(cleanup_ucr, cls.data_source_1)

        cls.data_source_2 = get_sample_registry_data_source(domain=cls.domain, registry_slug=cls.registry_2.slug)
        cls.data_source_2.save()
        cls.addClassCleanup(cleanup_ucr, cls.data_source_2)

    def test_get_by_owning_domain(self):
        provider = RegistryDataSourceProvider()
        data_sources = provider.get_all_data_sources(self.domain)
        assert {ds._id for ds in data_sources} == {
            self.data_source_1._id,
            self.data_source_2._id,
        }

    def test_get_by_granted_domain(self):
        provider = RegistryDataSourceProvider()
        data_sources = provider.get_all_data_sources('granted-domain')
        assert {ds._id for ds in data_sources} == {self.data_source_1._id}
