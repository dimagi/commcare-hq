import uuid
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.es import UserES, CaseES, FormES, ESQuery, DomainES
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.utils import TestFormMetadata
from corehq.form_processor.tests.utils import FormProcessorTestUtils, run_with_all_backends
from corehq.pillows.case import CasePillow
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX
from corehq.pillows.mappings.user_mapping import USER_INDEX
from corehq.util.elastic import delete_es_index, ensure_index_deleted
from corehq.util.test_utils import get_form_ready_to_save, trap_extra_setup, create_and_save_a_form, \
    create_and_save_a_case
from elasticsearch.exceptions import ConnectionError


DOMAIN = 'reindex-test-domain'


class PillowtopReindexerTest(TestCase):
    domain = DOMAIN

    @classmethod
    def setUpClass(cls):
        with trap_extra_setup(ConnectionError):
            CasePillow()  # verify connection to elasticsearch

    def test_domain_reindexer(self):
        for command, kwargs in [
            ('ptop_fast_reindex_domains', {'noinput': True, 'bulk': True}),
            ('ptop_reindexer_v2', {'index': 'domain', 'cleanup': True, 'noinput': True})
        ]:
            delete_all_domains()
            name = 'reindex-test-domain'
            create_domain(name)
            call_command(command, **kwargs)
            results = DomainES().run()
            self.assertEqual(1, results.total)
            domain_doc = results.hits[0]
            self.assertEqual(name, domain_doc['name'])
            self.assertEqual('Domain', domain_doc['doc_type'])
            delete_es_index(DOMAIN_INDEX)

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
        case = _create_and_save_a_case()
        call_command('ptop_fast_reindex_cases', noinput=True, bulk=True)
        self._assert_case_is_in_es(case)

    @run_with_all_backends
    def test_new_case_reindexer(self):
        FormProcessorTestUtils.delete_all_cases()
        case = _create_and_save_a_case()

        index_id = 'sql-case' if settings.TESTS_SHOULD_USE_SQL_BACKEND else 'case'
        call_command('ptop_reindexer_v2', index_id, cleanup=True, noinput=True)

        self._assert_case_is_in_es(case)

    def test_xform_reindexer(self):
        FormProcessorTestUtils.delete_all_xforms()
        form = create_and_save_a_form(DOMAIN)

        call_command('ptop_fast_reindex_xforms', noinput=True, bulk=True)

        self._assert_form_is_in_es(form)
        form.delete()

    @run_with_all_backends
    def test_new_xform_reindexer(self):
        FormProcessorTestUtils.delete_all_xforms()
        form = create_and_save_a_form(DOMAIN)

        index_id = 'sql-form' if settings.TESTS_SHOULD_USE_SQL_BACKEND else 'form'
        call_command('ptop_reindexer_v2', index_id, cleanup=True, noinput=True)

        self._assert_form_is_in_es(form)

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

    def _assert_case_is_in_es(self, case):
        results = CaseES().run()
        self.assertEqual(1, results.total)
        case_doc = results.hits[0]
        self.assertEqual(case.case_id, case_doc['_id'])
        self.assertEqual(self.domain, case_doc['domain'])
        self.assertEqual(case.name, case_doc['name'])
        self.assertEqual('CommCareCase', case_doc['doc_type'])

    def _assert_form_is_in_es(self, form):
        results = FormES().run()
        self.assertEqual(1, results.total)
        form_doc = results.hits[0]
        self.assertEqual(self.domain, form_doc['domain'])
        self.assertEqual(form.xmlns, form_doc['xmlns'])
        self.assertEqual('XFormInstance', form_doc['doc_type'])


def _create_and_save_a_case():
    case_name = 'reindexer-test-case-{}'.format(uuid.uuid4().hex)
    case_id = uuid.uuid4().hex
    return create_and_save_a_case(DOMAIN, case_id, case_name)
