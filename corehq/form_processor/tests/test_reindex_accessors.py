from __future__ import absolute_import
import time
import uuid
from datetime import datetime
from unittest import SkipTest

from django.conf import settings
from django.db import connections
from django.test import TestCase

from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL, FormReindexAccessor, CaseReindexAccessor,
    LedgerAccessorSQL, LedgerReindexAccessor
)
from corehq.form_processor.models import LedgerValue, CommCareCaseSQL
from corehq.form_processor.tests.utils import FormProcessorTestUtils, create_form_for_test
from corehq.sql_db.config import partition_config


class BaseReindexAccessorTest(object):
    accessor_class = None

    @classmethod
    def class_setup_reindex(cls):
        cls.domain = uuid.uuid4().hex
        cls.other_domain = uuid.uuid4().hex
        # since this test depends on the global form list just wipe everything
        FormProcessorTestUtils.delete_all_sql_forms()
        FormProcessorTestUtils.delete_all_v2_ledgers()
        FormProcessorTestUtils.delete_all_sql_cases()

        cls.first_batch_domain = cls._get_doc_ids(cls._create_docs(cls.domain, 4))
        cls.first_batch_global = cls.first_batch_domain + cls._get_doc_ids(cls._create_docs(cls.other_domain, 4))
        cls.middle = datetime.utcnow()
        time.sleep(.02)
        cls.second_batch_domain = cls._get_doc_ids(cls._create_docs(cls.domain, 4))
        cls.second_batch_global = cls.second_batch_domain + cls._get_doc_ids(cls._create_docs(cls.other_domain, 4))
        time.sleep(.02)
        cls.end = datetime.utcnow()

        cls.all_doc_ids = cls.first_batch_global + cls.second_batch_global
        cls.all_doc_ids_domain = cls.first_batch_domain + cls.second_batch_domain

        cls._analyse()

    @classmethod
    def class_teardown_reindex(cls):
        FormProcessorTestUtils.delete_all_sql_forms()
        FormProcessorTestUtils.delete_all_v2_ledgers()
        FormProcessorTestUtils.delete_all_sql_cases()

    @classmethod
    def _get_doc_ids(cls, docs):
        raise NotImplementedError

    @classmethod
    def _create_docs(cls, domain, count):
        raise NotImplementedError

    def _get_docs(self, start, last_doc_pk=None, limit=500):
        return self.accessor_class().get_docs(None, start, last_doc_pk=last_doc_pk, limit=limit)

    def _get_docs_for_domain(self, domain, start, last_doc_pk=None, limit=500):
        return self.accessor_class(domain=domain).get_docs(None, start, last_doc_pk=last_doc_pk, limit=limit)

    def test_get_docs(self):
        docs = self._get_docs(None)
        self.assertEqual(len(self.all_doc_ids), len(docs))
        self.assertEqual(set(self._get_doc_ids(docs)),
                         set(self.all_doc_ids))

        docs = self._get_docs(self.middle)
        self.assertEqual(8, len(docs))
        self.assertEqual(set(self._get_doc_ids(docs)),
                         set(self.second_batch_global))

        self.assertEqual(0, len(self._get_docs(self.end)))

    def test_get_docs_for_domain(self):
        docs = self._get_docs_for_domain(self.domain, None)
        self.assertEqual(len(self.all_doc_ids_domain), len(docs))
        self.assertEqual(set(self._get_doc_ids(docs)),
                         set(self.all_doc_ids_domain))

        docs = self._get_docs_for_domain(self.domain, self.middle)
        self.assertEqual(len(self.second_batch_domain), len(docs))
        self.assertEqual(set(self._get_doc_ids(docs)),
                         set(self.second_batch_domain))

        self.assertEqual(0, len(self._get_docs_for_domain(self.domain, self.end)))


class BaseUnshardedAccessorMixin(object):
    @classmethod
    def class_setup(cls):
        if settings.USE_PARTITIONED_DATABASE:
            # https://github.com/nose-devs/nose/issues/946
            raise SkipTest('Only applicable if no sharding is setup')

    @classmethod
    def _analyse(cls):
        db_cursor = connections['default'].cursor()
        with db_cursor as cursor:
            cursor.execute('ANALYSE')  # the doc count query relies on this

    def test_limit(self):
        docs = self._get_docs(None, limit=2)
        self.assertEqual(2, len(docs))
        self.assertEqual(self._get_doc_ids(docs), self.first_batch_global[:2])

    def test_last_doc_pk(self):
        docs = self._get_docs(self.middle, limit=2)
        self.assertEqual(self._get_doc_ids(docs), self.second_batch_global[:2])

        last_doc = self.accessor_class().get_doc(self.second_batch_global[0])
        docs = self._get_docs(self._get_last_modified_date(last_doc), last_doc_pk=last_doc.pk, limit=2)
        self.assertEqual(self._get_doc_ids(docs), self.second_batch_global[1:3])

    def test_get_doc_count(self):
        self.assertEqual(16, self.accessor_class().get_doc_count('default'))

    def test_get_doc_count_domain(self):
        self.assertEqual(8, self.accessor_class(domain=self.domain).get_doc_count('default'))


class BaseShardedAccessorMixin(object):
    @classmethod
    def class_setup(cls):
        if not settings.USE_PARTITIONED_DATABASE:
            # https://github.com/nose-devs/nose/issues/946
            raise SkipTest('Only applicable if sharding is setup')
        assert len(partition_config.get_form_processing_dbs()) > 1

    @classmethod
    def _analyse(cls):
        for db_alias in partition_config.get_form_processing_dbs():
            db_cursor = connections[db_alias].cursor()
            with db_cursor as cursor:
                cursor.execute('ANALYSE')  # the doc count query relies on this

    def _get_docs(self, start, last_doc_pk=None, limit=500):
        accessor = self.accessor_class()
        return self._get_docs_from_accessor(accessor, start, last_doc_pk, limit)

    def _get_docs_from_accessor(self, accessor, start, last_doc_pk=None, limit=500):
        all_docs = []
        for from_db in partition_config.get_form_processing_dbs():
            all_docs.extend(accessor.get_docs(from_db, start))
        return all_docs

    def _get_docs_for_domain(self, domain, start, last_doc_pk=None, limit=500):
        accessor = self.accessor_class(domain=domain)
        return self._get_docs_from_accessor(accessor, start, last_doc_pk, limit)

    def test_get_doc_count(self):
        doc_count = sum(
            self.accessor_class().get_doc_count(from_db)
            for from_db in partition_config.get_form_processing_dbs()
        )
        self.assertEqual(len(self.all_doc_ids), doc_count)


class BaseCaseReindexAccessorTest(BaseReindexAccessorTest):
    accessor_class = CaseReindexAccessor

    @classmethod
    def _create_docs(cls, domain, count):
        case_ids = [uuid.uuid4().hex for i in range(count)]
        [create_form_for_test(domain, case_id=case_id) for case_id in case_ids]
        return CaseAccessorSQL.get_cases(case_ids, ordered=True)

    @classmethod
    def _get_doc_ids(cls, docs):
        return [doc.case_id for doc in docs]

    @classmethod
    def _get_last_modified_date(cls, doc):
        return doc.server_modified_on


class UnshardedCaseReindexAccessorTests(BaseUnshardedAccessorMixin, BaseCaseReindexAccessorTest, TestCase):
    @classmethod
    def setUpClass(cls):
        super(UnshardedCaseReindexAccessorTests, cls).class_setup()
        super(UnshardedCaseReindexAccessorTests, cls).setUpClass()
        super(UnshardedCaseReindexAccessorTests, cls).class_setup_reindex()

    @classmethod
    def tearDownClass(cls):
        super(UnshardedCaseReindexAccessorTests, cls).class_teardown_reindex()
        super(UnshardedCaseReindexAccessorTests, cls).tearDownClass()


class ShardedCaseReindexAccessorTests(BaseShardedAccessorMixin, BaseCaseReindexAccessorTest, TestCase):
    @classmethod
    def setUpClass(cls):
        super(ShardedCaseReindexAccessorTests, cls).class_setup()
        super(ShardedCaseReindexAccessorTests, cls).setUpClass()
        super(ShardedCaseReindexAccessorTests, cls).class_setup_reindex()

    @classmethod
    def tearDownClass(cls):
        super(ShardedCaseReindexAccessorTests, cls).class_teardown_reindex()
        super(ShardedCaseReindexAccessorTests, cls).tearDownClass()


class BaseFormReindexAccessorTest(BaseReindexAccessorTest):
    accessor_class = FormReindexAccessor

    @classmethod
    def _create_docs(cls, domain, count):
        return [create_form_for_test(domain) for i in range(count)]

    @classmethod
    def _get_doc_ids(cls, docs):
        return [doc.form_id for doc in docs]

    @classmethod
    def _get_last_modified_date(cls, doc):
        return doc.received_on


class UnshardedFormReindexAccessorTests(BaseUnshardedAccessorMixin, BaseFormReindexAccessorTest, TestCase):

    @classmethod
    def setUpClass(cls):
        super(UnshardedFormReindexAccessorTests, cls).class_setup()
        super(UnshardedFormReindexAccessorTests, cls).setUpClass()
        super(UnshardedFormReindexAccessorTests, cls).class_setup_reindex()

    @classmethod
    def tearDownClass(cls):
        super(UnshardedFormReindexAccessorTests, cls).class_teardown_reindex()
        super(UnshardedFormReindexAccessorTests, cls).tearDownClass()

class ShardedFormReindexAccessorTests(BaseShardedAccessorMixin, BaseFormReindexAccessorTest, TestCase):

    @classmethod
    def setUpClass(cls):
        super(ShardedFormReindexAccessorTests, cls).class_setup()
        super(ShardedFormReindexAccessorTests, cls).setUpClass()
        super(ShardedFormReindexAccessorTests, cls).class_setup_reindex()

    @classmethod
    def tearDownClass(cls):
        super(ShardedFormReindexAccessorTests, cls).class_teardown_reindex()
        super(ShardedFormReindexAccessorTests, cls).tearDownClass()


class BaseLedgerReindexAccessorTest(BaseReindexAccessorTest):
    accessor_class = LedgerReindexAccessor

    @classmethod
    def _create_docs(cls, domain, count):
        return [_create_ledger(domain, 'product_a', 10) for i in range(count)]

    @classmethod
    def _get_doc_ids(cls, docs):
        return [doc.ledger_reference.as_id() for doc in docs]

    @classmethod
    def _get_last_modified_date(cls, doc):
        return doc.last_modified


class UnshardedLedgerReindexAccessorTests(BaseUnshardedAccessorMixin, BaseLedgerReindexAccessorTest, TestCase):

    @classmethod
    def setUpClass(cls):
        super(UnshardedLedgerReindexAccessorTests, cls).class_setup()
        super(UnshardedLedgerReindexAccessorTests, cls).setUpClass()
        super(UnshardedLedgerReindexAccessorTests, cls).class_setup_reindex()

    @classmethod
    def tearDownClass(cls):
        super(UnshardedLedgerReindexAccessorTests, cls).class_teardown_reindex()
        super(UnshardedLedgerReindexAccessorTests, cls).tearDownClass()


class ShardedLedgerReindexAccessorTests(BaseShardedAccessorMixin, BaseLedgerReindexAccessorTest, TestCase):

    @classmethod
    def setUpClass(cls):
        super(ShardedLedgerReindexAccessorTests, cls).class_setup()
        super(ShardedLedgerReindexAccessorTests, cls).setUpClass()
        super(ShardedLedgerReindexAccessorTests, cls).class_setup_reindex()

    @classmethod
    def tearDownClass(cls):
        super(ShardedLedgerReindexAccessorTests, cls).class_teardown_reindex()
        super(ShardedLedgerReindexAccessorTests, cls).tearDownClass()


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
