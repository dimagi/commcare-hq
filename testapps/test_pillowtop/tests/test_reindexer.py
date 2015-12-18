import uuid
from django.core.management import call_command
from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.es import UserES, CaseES, FormES
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.tests.utils import TestFormMetadata
from corehq.util.context_managers import drop_connected_signals
from corehq.util.test_utils import make_es_ready_form


class PillowtopReindexerTest(TestCase):

    domain = 'reindex-test-domain'

    def test_user_reindexer(self):
        username = 'reindex-test-username'
        CommCareUser.create(self.domain, username, 'secret')
        call_command('ptop_fast_reindex_users', noinput=True, bulk=True)
        results = UserES().run()
        self.assertEqual(1, results.total)
        user_doc = results.hits[0]
        self.assertEqual(self.domain, user_doc['domain'])
        self.assertEqual(username, user_doc['username'])
        self.assertEqual('CommCareUser', user_doc['doc_type'])

    def test_case_reindexer(self):
        case_name = 'reindexer-test-case-{}'.format(uuid.uuid4().hex)
        with drop_connected_signals(case_post_save):
            CommCareCase(domain=self.domain, name=case_name).save()
        call_command('ptop_fast_reindex_cases', noinput=True, bulk=True)
        results = CaseES().run()
        self.assertEqual(1, results.total)
        case_doc = results.hits[0]
        self.assertEqual(self.domain, case_doc['domain'])
        self.assertEqual(case_name, case_doc['name'])
        self.assertEqual('CommCareCase', case_doc['doc_type'])

    def test_xform_reindexer(self):
        metadata = TestFormMetadata(domain=self.domain)
        form = make_es_ready_form(metadata).wrapped_form
        form.save()
        call_command('ptop_fast_reindex_xforms', noinput=True, bulk=True)
        results = FormES().run()
        self.assertEqual(1, results.total)
        form_doc = results.hits[0]
        self.assertEqual(self.domain, form_doc['domain'])
        self.assertEqual(metadata.xmlns, form_doc['xmlns'])
        self.assertEqual('XFormInstance', form_doc['doc_type'])
