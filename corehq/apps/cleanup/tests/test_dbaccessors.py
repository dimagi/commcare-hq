from django.test import TestCase

from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.cleanup.dbaccessors import (
    find_es_docs_for_deleted_domains,
    find_sql_cases_for_deleted_domains,
    find_sql_forms_for_deleted_domains,
    find_ucr_tables_for_deleted_domains,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import FormES
from corehq.apps.es.tests.utils import es_test
from corehq.apps.userreports.app_manager.helpers import clean_table_name
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.tests.utils import create_case, create_form_for_test
from corehq.pillows.mappings import (
    APP_INDEX_INFO,
    CASE_INDEX_INFO,
    CASE_SEARCH_INDEX_INFO,
    GROUP_INDEX_INFO,
    USER_INDEX_INFO,
    XFORM_INDEX_INFO,
)
from corehq.pillows.xform import transform_xform_for_elasticsearch
from corehq.util.elastic import ensure_index_deleted, reset_es_index


class TestFindSQLFormsForDeletedDomains(TestCase):

    def test_deleted_domain_with_form_data_is_flagged(self):
        create_form_for_test(self.deleted_domain.name)
        counts_by_domain = find_sql_forms_for_deleted_domains()
        self.assertEqual(counts_by_domain[self.deleted_domain.name], 1)

    def test_missing_domain_with_form_data_is_not_flagged(self):
        create_form_for_test('missing-domain')
        counts_by_domain = find_sql_forms_for_deleted_domains()
        self.assertTrue('missing-domain' not in counts_by_domain)

    def test_active_domain_with_form_data_is_not_flagged(self):
        create_form_for_test(self.active_domain.name)
        counts_by_domain = find_sql_forms_for_deleted_domains()
        self.assertTrue(self.active_domain.name not in counts_by_domain)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.active_domain = create_domain('active-domain')
        cls.deleted_domain = create_domain('deleted-domain')
        cls.deleted_domain.delete(leave_tombstone=True)
        cls.addClassCleanup(cls.active_domain.delete)
        cls.addClassCleanup(cls.deleted_domain.delete)


class TestFindSQLCasesForDeletedDomains(TestCase):

    def test_deleted_domain_with_case_data_is_flagged(self):
        create_case(self.deleted_domain.name, save=True)
        counts_by_domain = find_sql_cases_for_deleted_domains()
        self.assertEqual(counts_by_domain[self.deleted_domain.name], 1)

    def test_missing_domain_with_case_data_is_not_flagged(self):
        create_case('missing-domain', save=True)
        counts_by_domain = find_sql_cases_for_deleted_domains()
        self.assertTrue('missing-domain' not in counts_by_domain)

    def test_active_domain_with_case_data_is_not_flagged(self):
        create_case(self.active_domain.name, save=True)
        counts_by_domain = find_sql_cases_for_deleted_domains()
        self.assertTrue(self.active_domain.name not in counts_by_domain)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.active_domain = create_domain('active-domain')
        cls.deleted_domain = create_domain('deleted-domain')
        cls.deleted_domain.delete(leave_tombstone=True)
        cls.addClassCleanup(cls.active_domain.delete)
        cls.addClassCleanup(cls.deleted_domain.delete)


@es_test
class TestFindESDocsForDeletedDomains(TestCase):

    def test_deleted_domain_with_es_data_is_flagged(self):
        form = create_form_for_test(self.deleted_domain.name)
        send_to_elasticsearch('forms', transform_xform_for_elasticsearch(form.to_json()))
        self.es.indices.refresh(XFORM_INDEX_INFO.index)

        counts_by_domain = find_es_docs_for_deleted_domains()

        es_doc_counts = counts_by_domain[self.deleted_domain.name]
        self.assertTrue(es_doc_counts[FormES.index], 1)

    def test_missing_domain_with_es_data_is_not_flagged(self):
        form = create_form_for_test('missing-domain')
        send_to_elasticsearch('forms', transform_xform_for_elasticsearch(form.to_json()))
        self.es.indices.refresh(XFORM_INDEX_INFO.index)

        counts_by_domain = find_es_docs_for_deleted_domains()

        self.assertTrue('missing-domain' not in counts_by_domain)

    def test_active_domain_with_es_data_is_not_flagged(self):
        form = create_form_for_test(self.active_domain.name)
        send_to_elasticsearch('forms', transform_xform_for_elasticsearch(form.to_json()))
        self.es.indices.refresh(XFORM_INDEX_INFO.index)

        counts_by_domain = find_es_docs_for_deleted_domains()

        self.assertTrue(self.active_domain.name not in counts_by_domain)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.active_domain = create_domain('active-domain')
        cls.deleted_domain = create_domain('deleted-domain')
        cls.deleted_domain.delete(leave_tombstone=True)
        cls.addClassCleanup(cls.active_domain.delete)
        cls.addClassCleanup(cls.deleted_domain.delete)

    def setUp(self):
        super().setUp()
        self._setup_es()

    def _setup_es(self):
        self.es = get_es_new()
        es_indices = [XFORM_INDEX_INFO, CASE_INDEX_INFO, CASE_SEARCH_INDEX_INFO, APP_INDEX_INFO, GROUP_INDEX_INFO,
                      USER_INDEX_INFO]
        for index in es_indices:
            reset_es_index(index)
            initialize_index_and_mapping(self.es, index)
            self.addCleanup(ensure_index_deleted, index.index)


class TestFindUCRTablesForDeletedDomains(TestCase):

    def test_deleted_domain_with_ucr_tables_is_flagged(self):
        config = self._create_data_source_config(self.deleted_domain.name)
        adapter = get_indicator_adapter(config, raise_errors=True)
        adapter.build_table()

        counts_by_domain = find_ucr_tables_for_deleted_domains()

        self.assertTrue(counts_by_domain[self.deleted_domain.name], [config.table_id])

    def test_missing_domain_with_ucr_tables_is_not_flagged(self):
        config = self._create_data_source_config('missing-domain')
        adapter = get_indicator_adapter(config, raise_errors=True)
        adapter.build_table()

        counts_by_domain = find_ucr_tables_for_deleted_domains()

        self.assertTrue('missing-domain' not in counts_by_domain)

    def test_active_domain_with_ucr_tables_is_not_flagged(self):
        config = self._create_data_source_config(self.active_domain.name)
        adapter = get_indicator_adapter(config, raise_errors=True)
        adapter.build_table()

        counts_by_domain = find_ucr_tables_for_deleted_domains()

        self.assertTrue(self.active_domain.name not in counts_by_domain)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.active_domain = create_domain('active-domain')
        cls.deleted_domain = create_domain('deleted-domain')
        cls.deleted_domain.delete(leave_tombstone=True)
        cls.addClassCleanup(cls.active_domain.delete)
        cls.addClassCleanup(cls.deleted_domain.delete)

    @staticmethod
    def _create_data_source_config(domain):
        return DataSourceConfiguration(
            domain=domain,
            display_name='foo',
            referenced_doc_type='CommCareCase',
            table_id=clean_table_name('domain', 'test-table'),
            configured_indicators=[{
                "type": "expression",
                "expression": {
                    "type": "property_name",
                    "property_name": 'name'
                },
                "column_id": 'name',
                "display_name": 'name',
                "datatype": "string"
            }],
        )
