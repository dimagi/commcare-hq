import uuid
from datetime import datetime

from django.test import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.registry.tests.utils import create_registry_for_test, Invitation
from corehq.apps.userreports.dbaccessors import (
    get_all_report_configs,
    get_number_of_report_configs_by_data_source,
    get_report_configs_for_domain, get_data_sources_modified_since,
)
from corehq.apps.userreports.models import ReportConfiguration, RegistryDataSourceConfiguration


class DBAccessorsTest(TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(DBAccessorsTest, cls).setUpClass()
        cls.data_source_id = 'd36c7c934cb84725899cca9a0ef96e3a'
        cls.domain_1 = Domain(name='userreport-dbaccessors')
        cls.domain_1.save()
        cls.domain_2 = Domain(name='mallory')
        cls.domain_2.save()
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

    @classmethod
    def tearDownClass(cls):
        ReportConfiguration.get_db().bulk_delete(cls.report_configs)
        cls.domain_1.delete()
        cls.domain_2.delete()
        super(DBAccessorsTest, cls).tearDownClass()

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



class RegistryUcrDbccessorsTest(TestCase):
    domain = 'registry-ucr-dbaccessors'

    @classmethod
    def setUpClass(cls):
        super(RegistryUcrDbccessorsTest, cls).setUpClass()

        cls.registry = create_registry_for_test(cls.domain, invitations=[
            Invitation('foo'), Invitation('bar'),
        ], name='foo_bar')

    @classmethod
    def tearDownClass(cls):
        for config in RegistryDataSourceConfiguration.all():
            config.delete()
        super(RegistryUcrDbccessorsTest, cls).tearDownClass()

    def test_get_data_sources_modified_since(self):
        start = datetime.utcnow()
        ds1 = self._create_datasource()
        middle = datetime.utcnow()
        ds2 = self._create_datasource()
        end = datetime.utcnow()

        self.assertEqual(
            [ds1.get_id, ds2.get_id],
            [ds.get_id for ds in get_data_sources_modified_since(start)]
        )
        self.assertEqual(
            [ds2.get_id],
            [ds.get_id for ds in get_data_sources_modified_since(middle)]
        )

        self.assertEqual([], get_data_sources_modified_since(end))

        ds1.save()
        self.assertEqual(
            [ds1.get_id],
            [ds.get_id for ds in get_data_sources_modified_since(end)]
        )

    def _create_datasource(self):
        config = RegistryDataSourceConfiguration(
            domain=self.domain, table_id=uuid.uuid4().hex,
            referenced_doc_type='CommCareCase', registry_slug=self.registry.slug
        )
        config.save()
        return config
