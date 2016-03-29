import uuid

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from elasticsearch.exceptions import ConnectionError
from mock import MagicMock, patch

from corehq.apps.es import CaseSearchES, ESQuery, FormES, UserES
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import FormProcessorTestUtils, \
    run_with_all_backends
from corehq.form_processor.utils import TestFormMetadata
from corehq.pillows.case import CasePillow
from corehq.pillows.case_search import CaseSearchPillow
from corehq.pillows.mappings.case_mapping import CASE_INDEX
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX
from corehq.pillows.mappings.user_mapping import USER_INDEX
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX
from corehq.pillows.xform import XFormPillow
from corehq.util.elastic import delete_es_index, ensure_index_deleted
from corehq.util.test_utils import get_form_ready_to_save, trap_extra_setup
from testapps.test_pillowtop.utils import make_a_case

DOMAIN = 'reindex-test-domain'


class PillowtopReindexerTest(TestCase):
    domain = DOMAIN

    @classmethod
    def setUpClass(cls):
        with trap_extra_setup(ConnectionError):
            CasePillow()  # verify connection to elasticsearch

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

        ensure_index_deleted(CASE_INDEX)  # new reindexer doesn't force delete the index so do it in the test
        index_id = 'sql-case' if settings.TESTS_SHOULD_USE_SQL_BACKEND else 'case'
        call_command('ptop_reindexer_v2', index_id)
        CasePillow().get_es_new().indices.refresh(CASE_INDEX)  # as well as refresh the index

        self._assert_case_is_in_es(case)

    def test_xform_reindexer(self):
        FormProcessorTestUtils.delete_all_xforms()
        form = _create_and_save_a_form()

        call_command('ptop_fast_reindex_xforms', noinput=True, bulk=True)

        self._assert_form_is_in_es(form)
        form.delete()

    @run_with_all_backends
    def test_new_xform_reindexer(self):
        FormProcessorTestUtils.delete_all_xforms()
        form = _create_and_save_a_form()

        ensure_index_deleted(XFORM_INDEX)
        index_id = 'sql-form' if settings.TESTS_SHOULD_USE_SQL_BACKEND else 'form'

        call_command('ptop_reindexer_v2', index_id)
        XFormPillow().get_es_new().indices.refresh(XFORM_INDEX)

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


def _create_and_save_a_form():
    metadata = TestFormMetadata(domain=DOMAIN)
    form = get_form_ready_to_save(metadata)
    FormProcessorInterface(domain=DOMAIN).save_processed_models([form])
    return form


def _create_and_save_a_case():
    case_name = 'reindexer-test-case-{}'.format(uuid.uuid4().hex)
    case_id = uuid.uuid4().hex
    return make_a_case(DOMAIN, case_id, case_name)
