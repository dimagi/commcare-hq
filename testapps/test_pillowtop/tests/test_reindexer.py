import uuid
from django.core.management import call_command
from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.es import UserES, CaseES, FormES, ESQuery
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.utils import TestFormMetadata
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.mappings.user_mapping import USER_INDEX
from corehq.util.context_managers import drop_connected_signals
from corehq.util.elastic import delete_es_index, ensure_index_deleted
from corehq.util.test_utils import get_form_ready_to_save


class PillowtopReindexerTest(TestCase):

    domain = 'reindex-test-domain'

    def test_user_reindexer(self):
        delete_all_users()
        username = 'reindex-test-username'
        CommCareUser.create(self.domain, username, 'secret')
        call_command('ptop_fast_reindex_users', noinput=True, bulk=True)
        results = UserES().run()
        self.assertEqual(1, results.total)
        user_doc = results.hits[0]
        self.assertEqual(self.domain, user_doc['domain'])
        self.assertEqual(username, user_doc['username'])
        self.assertEqual('CommCareUser', user_doc['doc_type'])
        delete_es_index(USER_INDEX)

    def test_case_reindexer(self):
        FormProcessorTestUtils.delete_all_cases()
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

    def test_xform_reindexers(self):
        FormProcessorTestUtils.delete_all_xforms()
        metadata = TestFormMetadata(domain=self.domain)
        form = get_form_ready_to_save(metadata)
        FormProcessorInterface(domain=self.domain).save_processed_models([form])
        call_command('ptop_fast_reindex_xforms', noinput=True, bulk=True)
        results = FormES().run()
        self.assertEqual(1, results.total)
        form_doc = results.hits[0]
        self.assertEqual(self.domain, form_doc['domain'])
        self.assertEqual(metadata.xmlns, form_doc['xmlns'])
        self.assertEqual('XFormInstance', form_doc['doc_type'])
        form.delete()

    def test_unknown_user_reindexer(self):
        FormProcessorTestUtils.delete_all_xforms()
        user_id = 'test-unknown-user'
        metadata = TestFormMetadata(domain=self.domain, user_id='test-unknown-user')
        form = get_form_ready_to_save(metadata)
        FormProcessorInterface(domain=self.domain).save_processed_models([form])
        ensure_index_deleted(USER_INDEX)
        call_command('ptop_fast_reindex_unknownusers', noinput=True, bulk=True)
        # the default query doesn't include unknown users so should have no results
        self.assertEqual(0, UserES().run().total)
        user_es = UserES()
        # hack: clear the default filters which hide unknown users
        # todo: find a better way to do this.
        user_es._default_filters = ESQuery.default_filters
        results = user_es.run()
        self.assertEqual(1, results.total)
        user_doc = results.hits[0]
        self.assertEqual(self.domain, user_doc['domain'])
        self.assertEqual(user_id, user_doc['_id'])
        self.assertEqual('UnknownUser', user_doc['doc_type'])
        form.delete()
        delete_es_index(USER_INDEX)
