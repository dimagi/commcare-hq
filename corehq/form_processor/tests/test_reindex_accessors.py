from __future__ import absolute_import

from __future__ import unicode_literals
import time
import uuid
from datetime import datetime
from unittest import SkipTest

from django.conf import settings
from django.db import connections
from django.test import TestCase

from corehq.apps.change_feed.data_sources import get_document_store_for_doc_type
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL, FormReindexAccessor, CaseReindexAccessor,
    LedgerAccessorSQL, LedgerReindexAccessor
)
from corehq.form_processor.models import LedgerValue, CommCareCaseSQL
from corehq.form_processor.tests.utils import FormProcessorTestUtils, create_form_for_test, use_sql_backend
from six.moves import range


class BaseReindexAccessorTest(object):
    accessor_class = None
    doc_type = None

    @classmethod
    def setUpClass(cls):
        if settings.USE_PARTITIONED_DATABASE:
            # https://github.com/nose-devs/nose/issues/946
            raise SkipTest('Only applicable if no sharding is setup')
        super(BaseReindexAccessorTest, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        cls.other_domain = uuid.uuid4().hex
        # since this test depends on the global form list just wipe everything
        FormProcessorTestUtils.delete_all_sql_forms()
        FormProcessorTestUtils.delete_all_v2_ledgers()
        FormProcessorTestUtils.delete_all_sql_cases()

    @classmethod
    def setup_reindexers(cls):
        cls.first_batch_domain = cls._get_doc_ids(cls._create_docs(cls.domain, 4))
        batch = cls._create_docs(cls.other_domain, 4)
        cls.first_batch_global = cls.first_batch_domain + cls._get_doc_ids(batch)
        cls.middle_id = batch[-1].pk
        time.sleep(.02)
        cls.second_batch_domain = cls._get_doc_ids(cls._create_docs(cls.domain, 4))
        batch = cls._create_docs(cls.other_domain, 4)
        cls.second_batch_global = cls.second_batch_domain + cls._get_doc_ids(batch)
        time.sleep(.02)
        cls.end_id = batch[-1].pk

        cls.all_doc_ids = cls.first_batch_global + cls.second_batch_global
        cls.all_doc_ids_domain = cls.first_batch_domain + cls.second_batch_domain

        cls._analyse()

    @classmethod
    def _analyse(cls):
        db_cursor = connections['default'].cursor()
        with db_cursor as cursor:
            cursor.execute('ANALYSE')  # the doc count query relies on this

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_sql_forms()
        FormProcessorTestUtils.delete_all_v2_ledgers()
        FormProcessorTestUtils.delete_all_sql_cases()
        super(BaseReindexAccessorTest, cls).tearDownClass()

    def _get_docs(self, last_doc_pk=None, limit=500):
        return self.accessor_class().get_docs(None, last_doc_pk=last_doc_pk, limit=limit)

    def _get_docs_for_domain(self, domain, last_doc_pk=None, limit=500):
        return self.accessor_class(domain=domain).get_docs(None, last_doc_pk=last_doc_pk, limit=limit)

    def test_get_docs(self):
        docs = self._get_docs()
        self.assertEqual(len(self.all_doc_ids), len(docs))
        self.assertEqual(set(self._get_doc_ids(docs)),
                         set(self.all_doc_ids))

        docs = self._get_docs(self.middle_id)
        self.assertEqual(8, len(docs))
        self.assertEqual(set(self._get_doc_ids(docs)),
                         set(self.second_batch_global))

        self.assertEqual(0, len(self._get_docs(self.end_id)))

    def test_get_docs_for_domain(self):
        docs = self._get_docs_for_domain(self.domain, None)
        self.assertEqual(len(self.all_doc_ids_domain), len(docs))
        self.assertEqual(set(self._get_doc_ids(docs)),
                         set(self.all_doc_ids_domain))

        docs = self._get_docs_for_domain(self.domain, self.middle_id)
        self.assertEqual(len(self.second_batch_domain), len(docs))
        self.assertEqual(set(self._get_doc_ids(docs)),
                         set(self.second_batch_domain))

        self.assertEqual(0, len(self._get_docs_for_domain(self.domain, self.end_id)))

    def test_ids_only(self):
        doc_ids = [row.doc_id for row in self.accessor_class().get_doc_ids(None)]
        self.assertListEqual(doc_ids, self.all_doc_ids)

    def test_limit(self):
        docs = self._get_docs(limit=2)
        self.assertEqual(2, len(docs))
        self.assertEqual(self._get_doc_ids(docs), self.first_batch_global[:2])

    def test_last_doc_pk(self):
        docs = self._get_docs(self.middle_id, limit=2)
        self.assertEqual(self._get_doc_ids(docs), self.second_batch_global[:2])

        last_doc = self.accessor_class().get_doc(self.second_batch_global[0])
        docs = self._get_docs(last_doc_pk=last_doc.pk, limit=2)
        self.assertEqual(self._get_doc_ids(docs), self.second_batch_global[1:3])

    def test_get_doc_count(self):
        self.assertEqual(16, self.accessor_class().get_approximate_doc_count('default'))

    def test_get_doc_count_domain(self):
        self.assertEqual(8, self.accessor_class(domain=self.domain).get_approximate_doc_count('default'))

    def test_doc_store(self):
        doc_store = get_document_store_for_doc_type(self.domain, self.doc_type)
        self.assertSetEqual(set(self.all_doc_ids_domain), set(doc_store.iter_document_ids()))


@use_sql_backend
class UnshardedCaseReindexAccessorTests(BaseReindexAccessorTest, TestCase):
    accessor_class = CaseReindexAccessor
    doc_type = 'CommCareCase'

    @classmethod
    def setUpClass(cls):
        super(UnshardedCaseReindexAccessorTests, cls).setUpClass()
        cls.setup_reindexers()

    @classmethod
    def _create_docs(cls, domain, count):
        case_ids = [uuid.uuid4().hex for i in range(count)]
        [create_form_for_test(domain, case_id=case_id) for case_id in case_ids]
        return CaseAccessorSQL.get_cases(case_ids, ordered=True)

    @classmethod
    def _get_doc_ids(cls, docs):
        return [doc.case_id for doc in docs]


@use_sql_backend
class UnshardedFormReindexAccessorTests(BaseReindexAccessorTest, TestCase):
    accessor_class = FormReindexAccessor
    doc_type = 'XFormInstance'

    @classmethod
    def setUpClass(cls):
        super(UnshardedFormReindexAccessorTests, cls).setUpClass()
        cls.setup_reindexers()

    @classmethod
    def _create_docs(cls, domain, count):
        return [create_form_for_test(domain) for i in range(count)]

    @classmethod
    def _get_doc_ids(cls, docs):
        return [doc.form_id for doc in docs]


@use_sql_backend
class UnshardedLedgerReindexAccessorTests(BaseReindexAccessorTest, TestCase):
    accessor_class = LedgerReindexAccessor
    doc_type = 'ledger'

    @classmethod
    def setUpClass(cls):
        super(UnshardedLedgerReindexAccessorTests, cls).setUpClass()
        cls.setup_reindexers()

    @classmethod
    def _create_docs(cls, domain, count):
        return [_create_ledger(domain, 'product_a', 10) for i in range(count)]

    @classmethod
    def _get_doc_ids(cls, docs):
        return [doc.ledger_reference.as_id() for doc in docs]


def _create_ledger(domain, entry_id, balance, case_id=None, section_id='stock'):
    user_id = 'user1'
    utcnow = datetime.utcnow()

    case_id = case_id or uuid.uuid4().hex
    case = CommCareCaseSQL(
        case_id=case_id,
        domain=domain,
        type='',
        owner_id=user_id,
        opened_on=utcnow,
        modified_on=utcnow,
        modified_by=user_id,
        server_modified_on=utcnow,
    )

    CaseAccessorSQL.save_case(case)

    ledger = LedgerValue(
        domain=domain,
        case_id=case_id,
        section_id=section_id,
        entry_id=entry_id,
        balance=balance,
        last_modified=utcnow
    )

    LedgerAccessorSQL.save_ledger_values([ledger])
    return ledger
