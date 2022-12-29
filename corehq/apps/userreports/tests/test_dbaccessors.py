import uuid
from datetime import datetime

from django.test import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_user
from corehq.apps.registry.tests.utils import (
    Invitation,
    create_registry_for_test,
)
from corehq.apps.userreports.dbaccessors import (
    get_all_registry_data_source_ids,
    get_all_report_configs,
    get_number_of_report_configs_by_data_source,
    get_registry_data_sources_modified_since,
    get_report_configs_for_domain,
)
from corehq.apps.userreports.models import (
    RegistryDataSourceConfiguration,
    ReportConfiguration,
)


class DBAccessorsTest(TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data_source_id = 'd36c7c934cb84725899cca9a0ef96e3a'
        cls.domain_1 = Domain(name='userreport-dbaccessors')
        cls.domain_1.save()
        cls.addClassCleanup(cls.domain_1.delete)
        cls.domain_2 = Domain(name='mallory')
        cls.domain_2.save()
        cls.addClassCleanup(cls.domain_2.delete)
        cls.report_configs = [
            ReportConfiguration(domain=cls.domain_1.name,
                                config_id=cls.data_source_id, title='A'),
            ReportConfiguration(domain=cls.domain_1.name,
                                config_id=cls.data_source_id, title='B'),
            ReportConfiguration(domain=cls.domain_1.name,
                                config_id='asabsdjf', title='C'),
            ReportConfiguration(domain=cls.domain_2.name,
                                config_id=cls.data_source_id, title='X'),
        ]
        ReportConfiguration.get_db().bulk_save(cls.report_configs)
        cls.addClassCleanup(ReportConfiguration.get_db().bulk_delete,
                            cls.report_configs)

    def test_get_number_of_report_configs_by_data_source(self):
        self.assertEqual(
            get_number_of_report_configs_by_data_source(
                self.domain_1.name, self.data_source_id),
            len([report_config for report_config in self.report_configs
                 if report_config.domain == self.domain_1.name
                 and report_config.config_id == self.data_source_id])
        )

    def test_get_all_report_configs(self):
        self.assertItemsEqual(
            [o.to_json() for o in get_all_report_configs()],
            [o.to_json() for o in self.report_configs]
        )

    def test_get_report_configs_for_domain(self):
        self.assertEqual(
            [o.to_json() for o in get_report_configs_for_domain(self.domain_1.name)],
            [report_config.to_json() for report_config
             in sorted(self.report_configs, key=lambda report: report.title)
             if report_config.domain == self.domain_1.name]
        )


class RegistryUcrDbAccessorsTest(TestCase):
    domain = 'registry-ucr-dbaccessors'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = create_user("admin", "123")
        cls.addClassCleanup(cls.user.delete, None, None)

        cls.registry = create_registry_for_test(cls.user, cls.domain, invitations=[
            Invitation('foo'), Invitation('bar'),
        ], name='foo_bar')

    def test_get_all_registry_data_source_ids(self):
        expected = [self._create_datasource().get_id for i in range(2)]
        actual = get_all_registry_data_source_ids()
        self.assertEqual(expected, actual)

    def test_get_all_registry_data_source_ids_active(self):
        data_sources = [
            self._create_datasource(active=True),
            self._create_datasource(active=False)
        ]
        self.assertEqual(
            [ds.get_id for ds in data_sources if not ds.is_deactivated],
            get_all_registry_data_source_ids(is_active=True)
        )
        self.assertEqual(
            [ds.get_id for ds in data_sources if ds.is_deactivated],
            get_all_registry_data_source_ids(is_active=False)
        )

    def test_get_all_registry_data_source_ids_global(self):
        data_sources = [
            self._create_datasource(globally_accessible=True),
            self._create_datasource(globally_accessible=False)
        ]
        self.assertEqual(
            [ds.get_id for ds in data_sources if ds.globally_accessible],
            get_all_registry_data_source_ids(globally_accessible=True)
        )
        self.assertEqual(
            [ds.get_id for ds in data_sources if not ds.globally_accessible],
            get_all_registry_data_source_ids(globally_accessible=False)
        )

    def test_get_registry_data_sources_modified_since(self):
        start = datetime.utcnow()
        ds1 = self._create_datasource()
        middle = datetime.utcnow()
        ds2 = self._create_datasource()
        end = datetime.utcnow()

        self.assertEqual(
            [ds1.get_id, ds2.get_id],
            [ds.get_id for ds in get_registry_data_sources_modified_since(start)]
        )
        self.assertEqual(
            [ds2.get_id],
            [ds.get_id for ds in get_registry_data_sources_modified_since(middle)]
        )

        self.assertEqual([], get_registry_data_sources_modified_since(end))

        ds1.is_deactivated = True  # results should include deactivated data sources
        ds1.save()
        self.assertEqual(
            [ds1.get_id],
            [ds.get_id for ds in get_registry_data_sources_modified_since(end)]
        )

    def _create_datasource(self, active=True, globally_accessible=False):
        config = RegistryDataSourceConfiguration(
            domain=self.domain, table_id=uuid.uuid4().hex,
            referenced_doc_type='CommCareCase', registry_slug=self.registry.slug,
            is_deactivated=(not active), globally_accessible=globally_accessible
        )
        config.save()
        self.addCleanup(config.delete)
        return config
