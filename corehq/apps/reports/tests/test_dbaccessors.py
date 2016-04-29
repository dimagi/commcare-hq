from django.test import TestCase
from django.test.utils import override_settings

from couchexport.models import SavedExportSchema

from corehq.apps.reports.dbaccessors import (
    get_all_hq_group_export_configs,
    hq_group_export_configs_by_domain,
    stale_get_exports_json,
    stale_get_export_count,
)
from corehq.apps.reports.models import HQGroupExportConfiguration
from corehq.dbaccessors.couchapps.all_docs import delete_all_docs_by_doc_type


class HQGroupExportConfigurationDbAccessorsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        HQGroupExportConfiguration(domain='domain1').save()
        HQGroupExportConfiguration(domain='domain2').save()
        HQGroupExportConfiguration(domain='domain2').save()

    @classmethod
    def tearDownClass(cls):
        delete_all_docs_by_doc_type(HQGroupExportConfiguration.get_db(), (HQGroupExportConfiguration.__name__,))

    def test_hq_group_export_configs_by_domain(self):
        self.assertEqual(len(hq_group_export_configs_by_domain('domain1')), 1)
        self.assertEqual(len(hq_group_export_configs_by_domain('domain2')), 2)

    def test_get_all_hq_group_export_configs(self):
        self.assertEqual(len(list(get_all_hq_group_export_configs())), 3)


@override_settings(COUCH_STALE_QUERY=None)
class SavedExportSchemaDBTest(TestCase):

    dependent_apps = ['couchexport', 'corehq.couchapps']

    @classmethod
    def setUpClass(cls):
        SavedExportSchema(domain='domain1', index=["domain1", "blah"]).save()
        SavedExportSchema(domain='domain1', index=["domain2", "blah"]).save()
        SavedExportSchema(domain='domain1', index=["domain2", "blah"]).save()

    @classmethod
    def tearDownClass(cls):
        delete_all_docs_by_doc_type(SavedExportSchema.get_db(), (SavedExportSchema.__name__,))

    def test_stale_get_exports_json(self):
        result = list(stale_get_exports_json('domain2'))
        self.assertEqual(len(result), 2)

    def test_stale_get_export_count(self):
        result = stale_get_export_count('domain2')
        self.assertEqual(result, 2)
