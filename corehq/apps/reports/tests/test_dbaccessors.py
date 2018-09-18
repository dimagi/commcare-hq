from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase

from corehq.apps.reports.dbaccessors import hq_group_export_configs_by_domain
from corehq.apps.reports.models import HQGroupExportConfiguration
from corehq.dbaccessors.couchapps.all_docs import delete_all_docs_by_doc_type, get_doc_ids_by_class


class HQGroupExportConfigurationDbAccessorsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(HQGroupExportConfigurationDbAccessorsTest, cls).setUpClass()
        HQGroupExportConfiguration(domain='domain1').save()
        HQGroupExportConfiguration(domain='domain2').save()
        HQGroupExportConfiguration(domain='domain2').save()

    @classmethod
    def tearDownClass(cls):
        delete_all_docs_by_doc_type(HQGroupExportConfiguration.get_db(), (HQGroupExportConfiguration.__name__,))
        super(HQGroupExportConfigurationDbAccessorsTest, cls).tearDownClass()

    def test_hq_group_export_configs_by_domain(self):
        self.assertEqual(len(hq_group_export_configs_by_domain('domain1')), 1)
        self.assertEqual(len(hq_group_export_configs_by_domain('domain2')), 2)

    def test_get_all_hq_group_export_configs(self):
        self.assertEqual(len(get_doc_ids_by_class(HQGroupExportConfiguration)), 3)
