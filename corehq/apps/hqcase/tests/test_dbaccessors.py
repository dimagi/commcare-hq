from __future__ import absolute_import
from __future__ import unicode_literals
import uuid

from django.test import TestCase
from elasticsearch.exceptions import ConnectionError
from mock import patch

from casexml.apps.case.dbaccessors import get_open_case_ids_in_domain
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import create_real_cases_from_dummy_cases
from couchforms.models import XFormInstance
from pillowtop.es_utils import initialize_index_and_mapping
from testapps.test_pillowtop.utils import process_pillow_changes

from corehq.apps.hqcase.analytics import (
    get_number_of_cases_in_domain_of_type,
    get_number_of_cases_in_domain,
)
from corehq.apps.hqcase.dbaccessors import (
    get_all_case_owner_ids,
    get_cases_in_domain,
    get_case_ids_in_domain,
    get_case_ids_in_domain_by_owner,
)
from corehq.elastic import get_es_new, EsMeta
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup, create_and_save_a_case
from six.moves import range


class DBAccessorsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(DBAccessorsTest, cls).setUpClass()
        cls.domain = 'lalksdjflakjsdf'
        cases = [
            CommCareCase(domain=cls.domain, type='type1', name='Alice', user_id='XXX',
                         prop_a=True, prop_b=True),
            CommCareCase(domain=cls.domain, type='type2', name='Bob', user_id='XXX',
                         prop_a=True, prop_c=True),
            CommCareCase(domain=cls.domain, type='type1', name='Candice', user_id='ZZZ'),
            CommCareCase(domain=cls.domain, type='type1', name='Derek', user_id='XXX', closed=True),
            CommCareCase(domain='maleficent', type='type1', name='Mallory', user_id='YYY',
                         prop_y=True)
        ]
        cls.forms, cls.cases = create_real_cases_from_dummy_cases(cases)
        assert len(cls.cases) == len(cases)

    @classmethod
    def tearDownClass(cls):
        CommCareCase.get_db().bulk_delete(cls.cases)
        XFormInstance.get_db().bulk_delete(cls.forms)
        super(DBAccessorsTest, cls).tearDownClass()

    def test_get_number_of_cases_in_domain__type(self):
        self.assertEqual(
            get_number_of_cases_in_domain_of_type(self.domain, case_type='type1'),
            len([case for case in self.cases
                 if case.domain == self.domain and case.type == 'type1'])
        )

    def test_get_case_ids_in_domain(self):
        self.assertEqual(
            set(get_case_ids_in_domain(self.domain)),
            {case.get_id for case in self.cases if case.domain == self.domain}
        )

    def test_get_case_ids_in_domain__type(self):
        self.assertEqual(
            set(get_case_ids_in_domain(self.domain, type='type1')),
            {case.get_id for case in self.cases
             if case.domain == self.domain and case.type == 'type1'}
        )

    def assert_doc_list_equal(self, doc_list_1, doc_list_2, raw_json=False):
        if not raw_json:
            doc_list_1 = [doc.to_json() for doc in doc_list_1]
            doc_list_2 = [doc.to_json() for doc in doc_list_2]
        doc_list_1 = sorted(doc_list_1, key=lambda doc: doc['_id'])
        doc_list_2 = sorted(doc_list_2, key=lambda doc: doc['_id'])
        self.assertEqual(doc_list_1, doc_list_2)

    def test_get_cases_in_domain(self):
        self.assert_doc_list_equal(
            get_cases_in_domain(self.domain),
            [case for case in self.cases if case.domain == self.domain]
        )

    def test_get_cases_in_domain__type(self):
        self.assert_doc_list_equal(
            get_cases_in_domain(self.domain, type='type1'),
            [case for case in self.cases
             if case.domain == self.domain and case.type == 'type1'],
        )

    def test_get_open_case_ids_in_domain(self):
        # this is actually in the 'case' app, but testing here
        self.assertEqual(
            set(get_open_case_ids_in_domain(self.domain, 'type1')),
            {case.get_id for case in self.cases
             if case.domain == self.domain and case.type == 'type1'
                and not case.closed},
        )

    def test_get_open_case_ids_in_domain__owner_id(self):
        # this is actually in the 'case' app, but testing here
        self.assertEqual(
            set(get_open_case_ids_in_domain(self.domain, 'type1', owner_id='XXX')),
            {case.get_id for case in self.cases
             if case.domain == self.domain and case.type == 'type1'
                and not case.closed and case.user_id == 'XXX'},
        )
        self.assertEqual(
            set(get_open_case_ids_in_domain(self.domain, owner_id='XXX')),
            {case.get_id for case in self.cases
             if case.domain == self.domain
                and not case.closed and case.user_id == 'XXX'},
        )

    def test_get_case_ids_in_domain_by_owner(self):
        self.assertEqual(
            set(get_case_ids_in_domain_by_owner(self.domain, owner_id='XXX')),
            {case.get_id for case in self.cases
             if case.domain == self.domain and case.user_id == 'XXX'}
        )
        self.assertEqual(
            set(get_case_ids_in_domain_by_owner(
                self.domain, owner_id__in=['XXX'])),
            {case.get_id for case in self.cases
             if case.domain == self.domain and case.user_id == 'XXX'}
        )
        self.assertEqual(
            set(get_case_ids_in_domain_by_owner(self.domain, owner_id='XXX',
                                                closed=False)),
            {case.get_id for case in self.cases
             if case.domain == self.domain and case.user_id == 'XXX'
                and case.closed is False}
        )
        self.assertEqual(
            set(get_case_ids_in_domain_by_owner(self.domain, owner_id='XXX',
                                                closed=True)),
            {case.get_id for case in self.cases
             if case.domain == self.domain and case.user_id == 'XXX'
                and case.closed is True}
        )

    def test_get_all_case_owner_ids(self):
        self.assertEqual(
            get_all_case_owner_ids(self.domain),
            set(case.user_id for case in self.cases
                if case.domain == self.domain)
        )
        # sanity check!
        self.assertEqual(
            get_all_case_owner_ids(self.domain),
            {'XXX', 'ZZZ'},
        )


TEST_ES_META = {
    CASE_INDEX_INFO.index: EsMeta(CASE_INDEX_INFO.index, CASE_INDEX_INFO.type)
}


class ESAccessorsTest(TestCase):
    domain = 'hqadmin-es-accessor'

    def setUp(self):
        super(ESAccessorsTest, self).setUp()
        with trap_extra_setup(ConnectionError):
            self.elasticsearch = get_es_new()
            initialize_index_and_mapping(self.elasticsearch, CASE_INDEX_INFO)
            initialize_index_and_mapping(self.elasticsearch, DOMAIN_INDEX_INFO)

    def tearDown(self):
        ensure_index_deleted(CASE_INDEX_INFO.index)
        ensure_index_deleted(DOMAIN_INDEX_INFO.index)
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        super(ESAccessorsTest, self).tearDown()

    @patch('corehq.apps.hqcase.analytics.CaseES.index', CASE_INDEX_INFO.index)
    @patch('corehq.apps.es.es_query.ES_META', TEST_ES_META)
    @patch('corehq.elastic.ES_META', TEST_ES_META)
    def test_get_number_of_cases_in_domain(self):
        cases = [self._create_case_and_sync_to_es() for _ in range(4)]
        self.assertEqual(
            get_number_of_cases_in_domain(self.domain),
            len(cases)
        )

    def _create_case_and_sync_to_es(self):
        case_id = uuid.uuid4().hex
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)
        with process_pillow_changes('case-pillow', {'skip_ucr': True}):
            with process_pillow_changes('DefaultChangeFeedPillow'):
                create_and_save_a_case(self.domain, case_id, case_name)
        self.elasticsearch.indices.refresh(CASE_INDEX_INFO.index)
        return case_id, case_name
