import time
import uuid
from datetime import datetime
from unittest import SkipTest

from django.conf import settings
from django.test import TestCase

from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL, FormReindexAccessor, CaseReindexAccessor,
    LedgerAccessorSQL, LedgerReindexAccessor
)
from corehq.form_processor.models import LedgerValue, CommCareCaseSQL
from corehq.form_processor.tests import FormProcessorTestUtils, PartitionConfig, create_form_for_test


class BaseReindexAccessorTest(object):
    accessor_class = None

    @classmethod
    def setUpClass(cls):
        super(BaseReindexAccessorTest, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        # since this test depends on the global form list just wipe everything
        FormProcessorTestUtils.delete_all_sql_forms()
        FormProcessorTestUtils.delete_all_v2_ledgers()
        FormProcessorTestUtils.delete_all_sql_cases()

        cls.first_batch = cls._get_doc_ids(cls._create_docs(4))
        cls.middle = datetime.utcnow()
        time.sleep(.02)
        cls.second_batch = cls._get_doc_ids(cls._create_docs(4))
        time.sleep(.02)
        cls.end = datetime.utcnow()

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_sql_forms()
        FormProcessorTestUtils.delete_all_v2_ledgers()
        FormProcessorTestUtils.delete_all_sql_cases()
        super(BaseReindexAccessorTest, cls).tearDownClass()

    @classmethod
    def _get_doc_ids(cls, docs):
        raise NotImplementedError

    @classmethod
    def _create_docs(cls, count):
        raise NotImplementedError

    def _get_docs(self, start, last_doc_pk=None, limit=500):
        return self.accessor_class().get_docs(None, start, last_doc_pk=last_doc_pk, limit=limit)

    def test_get_docs(self):
        docs = self._get_docs(None)
        self.assertEqual(8, len(docs))
        self.assertEqual(set(self._get_doc_ids(docs)),
                         set(self.first_batch + self.second_batch))

        docs = self._get_docs(self.middle)
        self.assertEqual(4, len(docs))
        self.assertEqual(set(self._get_doc_ids(docs)),
                         set(self.second_batch))

        self.assertEqual(0, len(self._get_docs(self.end)))



class BaseUnshardedAccessorMixin(object):
    @classmethod
    def setUpClass(cls):
        super(BaseUnshardedAccessorMixin, cls).setUpClass()
        if settings.USE_PARTITIONED_DATABASE:
            # https://github.com/nose-devs/nose/issues/946
            raise SkipTest('Only applicable if no sharding is setup')

    def test_limit(self):
        docs = self._get_docs(None, limit=2)
        self.assertEqual(2, len(docs))
        self.assertEqual(self._get_doc_ids(docs), self.first_batch[:2])

    def test_last_doc_pk(self):
        docs = self._get_docs(self.middle, limit=2)
        self.assertEqual(self._get_doc_ids(docs), self.second_batch[:2])

        last_doc = self.reindex_accessor().get_doc(self.second_batch[0])

        docs = self._get_docs(self.middle, last_doc_pk=last_doc.pk, limit=2)
        self.assertEqual(self._get_doc_ids(docs), self.second_batch[1:3 ])



class BaseShardedAccessorMixin(object):
    @classmethod
    def setUpClass(cls):
        super(BaseShardedAccessorMixin, cls).setUpClass()
        if not settings.USE_PARTITIONED_DATABASE:
            # https://github.com/nose-devs/nose/issues/946
            raise SkipTest('Only applicable if sharding is setup')
        cls.partion_config = PartitionConfig()
        assert len(cls.partion_config.get_form_processing_dbs()) > 1

    def _get_docs(self, start, last_doc_pk=None, limit=500):
        accessor = self.accessor_class()
        all_docs = []
        for from_db in self.partion_config.get_form_processing_dbs():
            print '---------', from_db, self.accessor_class
            all_docs.extend(accessor.get_docs(from_db, start))
        return all_docs


class BaseCaseReindexAccessorTest(BaseReindexAccessorTest):
    accessor_class = CaseReindexAccessor

    @classmethod
    def _create_docs(cls, count):
        case_ids = [uuid.uuid4().hex for i in range(count)]
        forms = [create_form_for_test(cls.domain, case_id=case_id) for case_id in case_ids]
        return CaseAccessorSQL.get_cases(case_ids, ordered=True)

    @classmethod
    def _get_doc_ids(cls, docs):
        return [doc.case_id for doc in docs]


class UnshardedCaseReindexAccessorTests(BaseUnshardedAccessorMixin, BaseCaseReindexAccessorTest, TestCase):
    pass


class ShardedCaseReindexAccessorTests(BaseShardedAccessorMixin, BaseCaseReindexAccessorTest, TestCase):
    pass


class BaseFormReindexAccessorTest(BaseReindexAccessorTest):
    accessor_class = FormReindexAccessor

    @classmethod
    def _create_docs(cls, count):
        return [create_form_for_test(cls.domain) for i in range(count)]

    @classmethod
    def _get_doc_ids(cls, docs):
        return [doc.form_id for doc in docs]


class UnshardedFormReindexAccessorTests(BaseUnshardedAccessorMixin, BaseFormReindexAccessorTest, TestCase):
    pass


class ShardedFormReindexAccessorTests(BaseShardedAccessorMixin, BaseFormReindexAccessorTest, TestCase):
    pass


class BaseLedgerReindexAccessorTest(BaseReindexAccessorTest):
    accessor_class = LedgerReindexAccessor

    @classmethod
    def _create_docs(cls, count):
        return [_create_ledger(cls.domain, 'product_a', 10) for i in range(count)]

    @classmethod
    def _get_doc_ids(cls, docs):
        return [doc.ledger_reference.as_id() for doc in docs]


class UnshardedLedgerReindexAccessorTests(BaseUnshardedAccessorMixin, BaseLedgerReindexAccessorTest, TestCase):
    pass


class ShardedLedgerReindexAccessorTests(BaseShardedAccessorMixin, BaseLedgerReindexAccessorTest, TestCase):
    pass


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
