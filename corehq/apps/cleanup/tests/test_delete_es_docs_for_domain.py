from django.core.management import CommandError, call_command
from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import FormES
from corehq.apps.es.apps import app_adapter
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.cases import case_adapter
from corehq.apps.es.client import manager
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.groups import group_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.tests.utils import create_form_for_test


@es_test(
    requires=[
        form_adapter, case_adapter, group_adapter,
        user_adapter, case_search_adapter, app_adapter
    ],
    setup_class=True
)
class TestDeleteESDocsForDomain(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.active_domain = create_domain('test-domain', active=True)
        cls.addClassCleanup(cls.active_domain.delete)
        cls.deleted_domain_with_tombstone = create_domain('deleted-domain', active=True)
        cls.deleted_domain_with_tombstone.delete(leave_tombstone=True)
        cls.addClassCleanup(cls.deleted_domain_with_tombstone.delete)

    def test_es_docs_are_cleaned_up_for_tombstoned_domain(self):
        domain_name = self.deleted_domain_with_tombstone.name
        # create an  and sync with ES
        form = create_form_for_test(domain_name)
        form_adapter.index(form, refresh=True)
        self.assertEqual(1, FormES().domain(domain_name).count())

        # run command
        call_command('delete_es_docs_for_domain', domain_name)

        # assert that docs are no longer in ES, but are still in SQL/couch
        manager.index_refresh(form_adapter.index_name)
        self.assertEqual(0, FormES().domain(domain_name).count())
        self.assertEqual(1, len(XFormInstance.objects.get_forms([form.form_id], domain_name)))

    def test_es_docs_are_cleaned_up_for_nonexistant_domain(self):
        # create an  and sync with ES
        form = create_form_for_test('obliterated-domain')
        form_adapter.index(
            form,
            refresh=True
        )
        self.assertEqual(1, FormES().domain('obliterated-domain').count())

        # run command
        call_command('delete_es_docs_for_domain', 'obliterated-domain')

        # assert that docs are no longer in ES, but are still in SQL/couch
        manager.index_refresh(form_adapter.index_name)
        self.assertEqual(0, FormES().domain('obliterated-domain').count())
        self.assertEqual(1, len(XFormInstance.objects.get_forms([form.form_id], 'obliterated-domain')))

    def test_es_docs_for_other_domains_are_not_impacted(self):
        domain_name = self.active_domain.name
        # create an  and sync with ES
        form = create_form_for_test(domain_name)
        form_adapter.index(
            form,
            refresh=True
        )
        self.assertEqual(1, FormES().domain(domain_name).count())

        # run command
        call_command('delete_es_docs_for_domain', 'obliterated-domain')

        # assert that docs are no longer in ES, but are still in SQL/couch
        manager.index_refresh(form_adapter.index_name)
        self.assertEqual(1, FormES().domain(domain_name).count())
        self.assertEqual(1, len(XFormInstance.objects.get_forms([form.form_id], domain_name)))

    def test_fails_on_active_domain(self):
        with self.assertRaises(CommandError):
            call_command('delete_es_docs_for_domain', self.active_domain.name)
