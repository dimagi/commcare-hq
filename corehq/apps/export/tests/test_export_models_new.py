from django.test import TestCase
from unittest.mock import patch
from nose.plugins.attrib import attr
from corehq.apps.es.tests.utils import es_test

import pytz

from corehq.pillows.mappings.xform_mapping import XFORM_ALIAS
from corehq.pillows.mappings.case_mapping import CASE_ES_ALIAS
from corehq.apps.es.client import ElasticManageAdapter
from corehq.apps.es.cases import ElasticCase
from corehq.apps.es.forms import ElasticForm
from corehq.util.es.elasticsearch import TransportError

from corehq.apps.export.models.new import CaseExportInstance, FormExportInstance


@attr('slow')
@es_test
class FormExportInstanceTests(TestCase):
    def setUp(self):
        super().setUp()

        self.manager = ElasticManageAdapter()
        self.forms = ElasticForm()

        self._purge_indices()
        self.manager.index_create(self.forms.index_name)
        self.manager.index_put_mapping(self.forms.index_name, self.forms.type, self.forms.mapping)
        self.manager.index_put_alias(self.forms.index_name, XFORM_ALIAS)

    def tearDown(self):
        self._purge_indices()
        super().tearDown()

    def _purge_indices(self):
        try:
            self.manager.index_delete(self.forms.index_name)
        except TransportError:
            pass

    def _make_doc(self, id='1'):
        return {
            'doc_type': 'XFormInstance',
            'domain': 'test-domain',
            'app_id': 'test-app',
            'xmlns': 'http://openrosa.org/formdesigner/9337A937-4002-434E-9C66-835BFB117EBE',
            '_id': id,
            'user_type': 'mobile'
        }

    @patch('corehq.apps.export.models.new.get_timezone_for_domain', return_value=pytz.UTC)
    def test_get_count_returns_total_row_count(self, mock_get_timezone):
        doc1 = self._make_doc(id='1')
        doc2 = self._make_doc(id='2')
        self.forms.index(doc1)
        self.forms.index(doc2)
        self.manager.index_refresh(self.forms.index_name)

        export = FormExportInstance(domain='test-domain', app_id='test-app',
            xmlns='http://openrosa.org/formdesigner/9337A937-4002-434E-9C66-835BFB117EBE')

        self.assertEqual(export.get_count(), 2)


@attr('slow')
@es_test
class CaseExportInstanceTests(TestCase):
    def setUp(self):
        super().setUp()

        self.manager = ElasticManageAdapter()
        self.cases = ElasticCase()
        self._purge_indices()
        self.manager.index_create(self.cases.index_name)
        self.manager.index_put_mapping(self.cases.index_name, self.cases.type, self.cases.mapping)
        self.manager.index_put_alias(self.cases.index_name, CASE_ES_ALIAS)

        filter_patcher = patch.object(CaseExportInstance, 'get_filters', lambda self: [])
        filter_patcher.start()
        self.addCleanup(filter_patcher.stop)

    def _make_doc(self, id='1'):
        return {
            'doc_type': 'CommCareCase',
            'domain': 'test-domain',
            'type': 'test-type',
            '_id': id
        }

    def tearDown(self):
        self._purge_indices()
        super().tearDown()

    def _purge_indices(self):
        try:
            self.manager.index_delete(self.cases.index_name)
        except TransportError:
            pass

    def test_get_count_returns_total_row_count(self):
        doc1 = self._make_doc(id='1')
        doc2 = self._make_doc(id='2')
        self.cases.index(doc1)
        self.cases.index(doc2)
        self.manager.index_refresh(self.cases.index_name)

        export = CaseExportInstance(domain='test-domain', case_type='test-type')
        self.assertEqual(export.get_count(), 2)
