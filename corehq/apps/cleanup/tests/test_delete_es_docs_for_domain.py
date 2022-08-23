from django.core.management import CommandError, call_command
from django.test import TestCase

from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import FormES
from corehq.apps.es.tests.utils import es_test
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.tests.utils import create_form_for_test
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


@es_test
class TestDeleteESDocsForDomain(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.active_domain = create_domain('test-domain', active=True)
        cls.addClassCleanup(cls.active_domain.delete)
        cls.deleted_domain_with_tombstone = create_domain('deleted-domain', active=True)
        cls.deleted_domain_with_tombstone.delete(leave_tombstone=True)
        cls.addClassCleanup(cls.deleted_domain_with_tombstone.delete)

    def setUp(self):
        super().setUp()
        self._setup_es()

    def test_es_docs_are_cleaned_up_for_tombstoned_domain(self):
        domain_name = self.deleted_domain_with_tombstone.name
        # create an  and sync with ES
        form = create_form_for_test(domain_name)
        send_to_elasticsearch('forms', transform_xform_for_elasticsearch(form.to_json()))
        self.es.indices.refresh(XFORM_INDEX_INFO.index)
        self.assertEqual(1, FormES().domain(domain_name).count())

        # run command
        call_command('delete_es_docs_for_domain', domain_name)

        # assert that docs are no longer in ES, but are still in SQL/couch
        self.es.indices.refresh(XFORM_INDEX_INFO.index)
        self.assertEqual(0, FormES().domain(domain_name).count())
        self.assertEqual(1, len(XFormInstance.objects.get_forms([form.form_id], domain_name)))

    def test_es_docs_are_cleaned_up_for_nonexistant_domain(self):
        # create an  and sync with ES
        form = create_form_for_test('obliterated-domain')
        send_to_elasticsearch('forms', transform_xform_for_elasticsearch(form.to_json()))
        self.es.indices.refresh(XFORM_INDEX_INFO.index)
        self.assertEqual(1, FormES().domain('obliterated-domain').count())

        # run command
        call_command('delete_es_docs_for_domain', 'obliterated-domain')

        # assert that docs are no longer in ES, but are still in SQL/couch
        self.es.indices.refresh(XFORM_INDEX_INFO.index)
        self.assertEqual(0, FormES().domain('obliterated-domain').count())
        self.assertEqual(1, len(XFormInstance.objects.get_forms([form.form_id], 'obliterated-domain')))

    def test_es_docs_for_other_domains_are_not_impacted(self):
        domain_name = self.active_domain.name
        # create an  and sync with ES
        form = create_form_for_test(domain_name)
        send_to_elasticsearch('forms', transform_xform_for_elasticsearch(form.to_json()))
        self.es.indices.refresh(XFORM_INDEX_INFO.index)
        self.assertEqual(1, FormES().domain(domain_name).count())

        # run command
        call_command('delete_es_docs_for_domain', 'obliterated-domain')

        # assert that docs are no longer in ES, but are still in SQL/couch
        self.es.indices.refresh(XFORM_INDEX_INFO.index)
        self.assertEqual(1, FormES().domain(domain_name).count())
        self.assertEqual(1, len(XFormInstance.objects.get_forms([form.form_id], domain_name)))

    def test_fails_on_active_domain(self):
        with self.assertRaises(CommandError):
            call_command('delete_es_docs_for_domain', self.active_domain.name)

    def _setup_es(self):
        self.es = get_es_new()
        es_indices = [XFORM_INDEX_INFO, CASE_INDEX_INFO, CASE_SEARCH_INDEX_INFO, APP_INDEX_INFO, GROUP_INDEX_INFO,
                      USER_INDEX_INFO]
        for index in es_indices:
            reset_es_index(index)
            initialize_index_and_mapping(self.es, index)
            self.addCleanup(ensure_index_deleted, index.index)
