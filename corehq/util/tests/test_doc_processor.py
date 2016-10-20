import uuid

from couchdbkit import ResourceConflict, ResourceNotFound
from django.test import TestCase
from django.test.testcases import SimpleTestCase
from django.test.utils import override_settings
from fakecouch import FakeCouchDb

from casexml.apps.case.mock import CaseFactory
from corehq.form_processor.backends.sql.dbaccessors import (
    FormReindexAccessor, ReindexAccessor, CaseReindexAccessor, LedgerReindexAccessor
)
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.form_processor.utils import TestFormMetadata
from corehq.form_processor.utils.xform import get_simple_wrapped_form
from corehq.util.doc_processor.couch import resumable_docs_by_type_iterator, CouchDocumentProvider
from corehq.util.doc_processor.interface import (
    BaseDocProcessor, DocumentProcessorController, BulkDocProcessor, BulkProcessingFailed
)
from corehq.util.doc_processor.sql import resumable_sql_model_iterator
from corehq.util.pagination import TooManyRetries
from dimagi.ext.couchdbkit import Document
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import get_db


class TestResumableDocsByTypeIterator(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.docs = []
        for i in range(3):
            cls.create_doc("Foo", i)
            cls.create_doc("Bar", i)
            cls.create_doc("Baz", i)
        cls.doc_types = ["Foo", "Bar", "Baz"]

    @classmethod
    def tearDownClass(cls):
        for doc_id in set(d["_id"] for d in cls.docs):
            try:
                cls.db.delete_doc(doc_id)
            except ResourceNotFound:
                pass

    def setUp(self):
        self.domain = "TEST"
        self.sorted_keys = ["{}-{}".format(n, i)
            for n in ["foo", "bar", "baz"]
            for i in range(3)]
        self.iteration_key = uuid.uuid4().hex
        self.itr = self.get_iterator()

    def tearDown(self):
        self.itr.discard_state()

    @classmethod
    def create_doc(cls, doc_type, ident):
        doc = {
            "_id": "{}-{}".format(doc_type.lower(), ident),
            "doc_type": doc_type,
        }
        cls.docs.append(doc)
        try:
            cls.db.save_doc(doc)
        except ResourceConflict:
            pass
        return doc

    def get_iterator(self, chunk_size=2):
        return resumable_docs_by_type_iterator(self.db, self.doc_types, self.iteration_key, chunk_size)

    def test_iteration(self):
        self.assertEqual([doc["_id"] for doc in self.itr], self.sorted_keys)

    def test_resume_iteration(self):
        itr = iter(self.itr)
        self.assertEqual([next(itr)["_id"] for i in range(6)], self.sorted_keys[:6])
        # stop/resume iteration
        self.itr = self.get_iterator()
        self.assertEqual([doc["_id"] for doc in self.itr], self.sorted_keys[5:])

    def test_resume_iteration_with_new_chunk_size(self):
        def data_function(*args, **kw):
            chunk = real_data_function(*args, **kw)
            chunks.append(len(chunk))
            return chunk
        chunks = []
        real_data_function = self.itr.data_function
        self.itr.data_function = data_function
        itr = iter(self.itr)
        self.assertEqual([next(itr)["_id"] for i in range(6)], self.sorted_keys[:6])
        self.assertEqual(chunks, [2, 1, 0, 2, 1])  # max chunk: 2
        # stop/resume iteration
        self.itr = self.get_iterator(chunk_size=3)
        chunks = []
        real_data_function = self.itr.data_function
        self.itr.data_function = data_function
        self.assertEqual([doc["_id"] for doc in self.itr], self.sorted_keys[5:])
        self.assertEqual(chunks, [1, 0, 3, 0])  # max chunk: 3

    def test_iteration_with_retry(self):
        itr = iter(self.itr)
        doc = next(itr)
        self.itr.retry(doc['_id'])
        self.assertEqual(doc["_id"], "foo-0")
        self.assertEqual(["foo-0"] + [d["_id"] for d in itr],
                         self.sorted_keys + ["foo-0"])


class SimulateDeleteReindexAccessor(ReindexAccessor):
    def __init__(self, wrapped_accessor, deleted_doc_ids=None):
        """
        :type wrapped_accessor: ReindexAccessor
        """
        self.deleted_doc_ids = deleted_doc_ids or []
        self.wrapped_accessor = wrapped_accessor

    @property
    def model_class(self):
        return self.wrapped_accessor.model_class

    @property
    def startkey_attribute_name(self):
        return self.wrapped_accessor.startkey_attribute_name

    def get_docs(self, from_db, startkey, last_doc_pk=None, limit=500):
        return self.wrapped_accessor.get_docs(from_db, startkey, last_doc_pk, limit)

    def get_doc(self, doc_id):
        if doc_id in self.deleted_doc_ids:
            return None
        return self.wrapped_accessor.get_doc(doc_id)

    def doc_to_json(self, doc):
        return self.wrapped_accessor.doc_to_json(doc)


class BaseResumableSqlModelIteratorTest(object):

    @property
    def reindex_accessor(self):
        raise NotImplementedError

    @classmethod
    def create_docs(cls, domain, count):
        raise NotImplementedError

    @classmethod
    def base_setUpClass(cls):
        cls.domain = uuid.uuid4().hex
        with override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True):
            FormProcessorTestUtils.delete_all_cases_forms_ledgers()
            cls.all_doc_ids = cls.create_docs(cls.domain, 9)
            cls.first_doc_id = cls.all_doc_ids[0]

    @classmethod
    def base_tearDownClass(cls):
        with override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True):
            FormProcessorTestUtils.delete_all_cases_forms_ledgers()

    def base_setUp(self):
        self.iteration_key = uuid.uuid4().hex
        self.itr = self.get_iterator()

    def base_tearDown(self):
        self.itr.discard_state()

    def get_iterator(self, deleted_doc_ids=None, chunk_size=2):
        reindex_accessor = SimulateDeleteReindexAccessor(self.reindex_accessor, deleted_doc_ids)
        return resumable_sql_model_iterator(self.iteration_key, reindex_accessor, chunk_size)

    def test_iteration(self):
        self.assertEqual([doc["_id"] for doc in self.itr], self.all_doc_ids)

    def test_resume_iteration(self):
        itr = iter(self.itr)
        self.assertEqual([next(itr)["_id"] for i in range(6)], self.all_doc_ids[:6])
        # stop/resume iteration
        self.itr = self.get_iterator()
        self.assertEqual([doc["_id"] for doc in self.itr], self.all_doc_ids[4:])

    def test_resume_iteration_with_new_chunk_size(self):
        def data_function(*args, **kw):
            chunk = real_data_function(*args, **kw)
            chunks.append(len(chunk))
            return chunk
        chunks = []
        real_data_function = self.itr.data_function
        self.itr.data_function = data_function
        itr = iter(self.itr)
        self.assertEqual([next(itr)["_id"] for i in range(6)], self.all_doc_ids[:6])
        self.assertEqual(chunks, [2, 2, 2])  # max chunk: 2
        # stop/resume iteration
        self.itr = self.get_iterator(chunk_size=3)
        chunks = []
        real_data_function = self.itr.data_function
        self.itr.data_function = data_function
        self.assertEqual([doc["_id"] for doc in self.itr], self.all_doc_ids[4:])
        self.assertEqual(chunks, [3, 2, 0])  # max chunk: 3

    def test_iteration_with_retry(self):
        itr = iter(self.itr)
        doc = next(itr)
        self.itr.retry(doc['_id'])
        self.assertEqual(doc["_id"], self.first_doc_id)
        self.assertEqual([self.first_doc_id] + [d["_id"] for d in itr],
                         self.all_doc_ids + [self.first_doc_id])


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class XFormResumableSqlModelIteratorTest(BaseResumableSqlModelIteratorTest, TestCase):
    @property
    def reindex_accessor(self):
        return FormReindexAccessor()

    @classmethod
    def create_docs(cls, domain, count):
        meta = TestFormMetadata(domain=domain)
        form_ids = ["f-{}".format(i) for i in range(count)]
        for form_id in form_ids:
            get_simple_wrapped_form(form_id, metadata=meta)

        return form_ids

    @classmethod
    def setUpClass(cls):
        super(XFormResumableSqlModelIteratorTest, cls).setUpClass()
        super(XFormResumableSqlModelIteratorTest, cls).base_setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(XFormResumableSqlModelIteratorTest, cls).base_tearDownClass()
        super(XFormResumableSqlModelIteratorTest, cls).tearDownClass()

    def setUp(self):
        super(XFormResumableSqlModelIteratorTest, self).setUp()
        super(XFormResumableSqlModelIteratorTest, self).base_setUp()

    def tearDown(self):
        super(XFormResumableSqlModelIteratorTest, self).base_tearDown()
        super(XFormResumableSqlModelIteratorTest, self).tearDown()


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class CaseResumableSqlModelIteratorTest(BaseResumableSqlModelIteratorTest, TestCase):
    @property
    def reindex_accessor(self):
        return CaseReindexAccessor()

    @classmethod
    def create_docs(cls, domain, count):
        factory = CaseFactory(cls.domain)
        return [factory.create_case().case_id for i in range(count)]

    @classmethod
    def setUpClass(cls):
        super(CaseResumableSqlModelIteratorTest, cls).setUpClass()
        super(CaseResumableSqlModelIteratorTest, cls).base_setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(CaseResumableSqlModelIteratorTest, cls).base_tearDownClass()
        super(CaseResumableSqlModelIteratorTest, cls).tearDownClass()

    def setUp(self):
        super(CaseResumableSqlModelIteratorTest, self).setUp()
        super(CaseResumableSqlModelIteratorTest, self).base_setUp()

    def tearDown(self):
        super(CaseResumableSqlModelIteratorTest, self).base_tearDown()
        super(CaseResumableSqlModelIteratorTest, self).tearDown()


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class LedgerResumableSqlModelIteratorTest(BaseResumableSqlModelIteratorTest, TestCase):
    @property
    def reindex_accessor(self):
        return LedgerReindexAccessor()

    @classmethod
    def create_docs(cls, domain, count):
        from corehq.apps.commtrack.tests.util import get_single_balance_block
        from corehq.apps.hqcase.utils import submit_case_blocks
        from corehq.apps.commtrack.helpers import make_product
        from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference

        cls.product = make_product(cls.domain, 'A Product', 'prodcode_a')

        factory = CaseFactory(cls.domain)
        case_ids = [factory.create_case().case_id for i in range(count)]

        for case_id in case_ids:
            submit_case_blocks([
                get_single_balance_block(case_id, cls.product._id, 10)
            ], domain)

        return [
            UniqueLedgerReference(case_id, 'stock', cls.product._id).as_id()
            for case_id in case_ids
        ]

    @classmethod
    def setUpClass(cls):
        super(LedgerResumableSqlModelIteratorTest, cls).setUpClass()
        super(LedgerResumableSqlModelIteratorTest, cls).base_setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.product.delete()
        super(LedgerResumableSqlModelIteratorTest, cls).base_tearDownClass()
        super(LedgerResumableSqlModelIteratorTest, cls).tearDownClass()

    def setUp(self):
        super(LedgerResumableSqlModelIteratorTest, self).setUp()
        super(LedgerResumableSqlModelIteratorTest, self).base_setUp()

    def tearDown(self):
        super(LedgerResumableSqlModelIteratorTest, self).base_tearDown()
        super(LedgerResumableSqlModelIteratorTest, self).tearDown()


class DemoProcessor(BaseDocProcessor):
    def __init__(self, ignore_docs=None, skip_docs=None):
        self.skip_docs = skip_docs
        self.ignore_docs = ignore_docs or []
        self.docs_processed = set()

    def should_process(self, doc):
        return doc['_id'] not in self.ignore_docs

    def process_doc(self, doc):
        doc_id = doc['_id']
        if self.skip_docs and doc_id in self.skip_docs:
            return False
        self.docs_processed.add(doc_id)
        return True


class Bar(Document):
    pass


class BaseCouchDocProcessorTest(SimpleTestCase):
    processor_class = None

    @staticmethod
    def _get_row(ident, doc_type="Bar"):
        doc_id_prefix = '{}-'.format(doc_type.lower())
        doc_id = '{}{}'.format(doc_id_prefix, ident)
        return {
            'id': doc_id,
            'key': [doc_type, doc_id], 'value': None, 'doc': {'_id': doc_id, 'doc_type': doc_type}
        }

    def _get_view_results(self, total, chuck_size, doc_type="Bar"):
        doc_id_prefix = '{}-'.format(doc_type.lower())
        results = [(
            {"endkey": [doc_type, {}], "group_level": 1, "reduce": True, "startkey": [doc_type]},
            [{"key": doc_type, "value": total}]
        )]
        for chunk in chunked(range(total), chuck_size):
            chunk_rows = [self._get_row(ident, doc_type=doc_type) for ident in chunk]
            if chunk[0] == 0:
                results.append((
                    {
                        'startkey': [doc_type], 'endkey': [doc_type, {}], 'reduce': False,
                        'limit': chuck_size, 'include_docs': True
                    },
                    chunk_rows
                ))
            else:
                previous = '{}{}'.format(doc_id_prefix, chunk[0] - 1)
                results.append((
                    {
                        'endkey': [doc_type, {}], 'skip': 1, 'startkey_docid': previous, 'reduce': False,
                        'startkey': [doc_type, previous], 'limit': chuck_size, 'include_docs': True
                    },
                    chunk_rows
                ))

        return results

    def setUp(self):
        views = {
            "all_docs/by_doc_type": self._get_view_results(4, chuck_size=2)
        }
        docs = [self._get_row(ident)['doc'] for ident in range(4)]
        self.db = FakeCouchDb(views=views, docs={
            doc['_id']: doc for doc in docs
        })
        Bar.set_db(self.db)
        self.processor_slug = uuid.uuid4().hex

    def tearDown(self):
        self.db.reset()

    def _get_processor(self, chunk_size=2, ignore_docs=None, skip_docs=None, reset=False, doc_types=None):
        doc_types = doc_types or [Bar]
        doc_processor = DemoProcessor()
        doc_provider = CouchDocumentProvider(self.processor_slug, doc_types)
        processor = self.processor_class(
            doc_provider,
            doc_processor,
            chunk_size=chunk_size,
            reset=reset
        )
        processor.document_iterator.couch_db = self.db
        if ignore_docs:
            doc_processor.ignore_docs = ignore_docs
        if skip_docs:
            doc_processor.skip_docs = skip_docs
        return doc_processor, processor


class TestCouchDocProcessor(BaseCouchDocProcessorTest):
    processor_class = DocumentProcessorController

    def _test_processor(self, expected_processed, doc_idents, ignore_docs=None, skip_docs=None):
        doc_processor, processor = self._get_processor(ignore_docs=ignore_docs, skip_docs=skip_docs)
        processed, skipped = processor.run()
        self.assertEqual(processed, expected_processed)
        self.assertEqual(skipped, len(skip_docs) if skip_docs else 0)
        self.assertEqual(
            {'bar-{}'.format(ident) for ident in doc_idents},
            doc_processor.docs_processed
        )

    def test_single_run_no_filtering(self):
        self._test_processor(4, range(4))

    def test_filtering(self):
        self._test_processor(3, [0, 2, 3], ['bar-1'])

    def test_multiple_runs_no_skip(self):
        self._test_processor(4, range(4))
        self._test_processor(0, [])

    def test_multiple_runs_with_skip(self):
        with self.assertRaises(TooManyRetries):
            self._test_processor(3, range(3), skip_docs=['bar-3'])

        self._test_processor(1, [3])


class TestBulkDocProcessor(BaseCouchDocProcessorTest):
    processor_class = BulkDocProcessor

    def setUp(self):
        super(TestBulkDocProcessor, self).setUp()
        # view call after restarting doesn't have the 'skip' arg
        self.db.update_view(
            "all_docs/by_doc_type",
            [(
                {
                    'endkey': ['Bar', {}], 'startkey_docid': 'bar-1', 'reduce': False,
                    'startkey': ['Bar', 'bar-1'], 'limit': 2, 'include_docs': True
                },
                [
                    self._get_row(2),
                    self._get_row(3),
                ]
            )]
        )

    def test_batch_gets_retried(self):
        doc_processor, processor = self._get_processor(skip_docs=['bar-2'])
        with self.assertRaises(BulkProcessingFailed):
            processor.run()

        self.assertEqual(doc_processor.docs_processed, {'bar-0', 'bar-1'})

        doc_processor, processor = self._get_processor()
        processed, skipped = processor.run()
        self.assertEqual(processed, 2)
        self.assertEqual(skipped, 0)
        self.assertEqual(doc_processor.docs_processed, {'bar-2', 'bar-3'})

    def test_batch_gets_retried_with_filtering(self):
        self.db.add_view("all_docs/by_doc_type", self._get_view_results(4, 3))

        doc_processor, processor = self._get_processor(chunk_size=3, ignore_docs=['bar-0'], skip_docs=['bar-2'])

        with self.assertRaises(BulkProcessingFailed):
            processor.run()

        self.assertEqual(doc_processor.docs_processed, {'bar-1'})

        doc_processor, processor = self._get_processor(chunk_size=3, ignore_docs=['bar-0'])
        processed, skipped = processor.run()
        self.assertEqual(processed, 3)
        self.assertEqual(skipped, 0)
        self.assertEqual(doc_processor.docs_processed, {'bar-1', 'bar-2', 'bar-3'})

    def test_filtering(self):
        doc_processor, processor = self._get_processor(ignore_docs=['bar-1'])
        processed, skipped = processor.run()
        self.assertEqual(processed, 3)
        self.assertEqual(skipped, 0)
        self.assertEqual(doc_processor.docs_processed, {'bar-0', 'bar-2', 'bar-3'})

    def test_remainder_gets_processed(self):
        self.db.add_view("all_docs/by_doc_type", self._get_view_results(4, 3))
        doc_processor, processor = self._get_processor(chunk_size=3)
        processed, skipped = processor.run()
        self.assertEqual(processed, 4)
        self.assertEqual(skipped, 0)
        self.assertEqual(
            {'bar-{}'.format(ident) for ident in range(4)},
            doc_processor.docs_processed
        )

    def test_reset(self):
        doc_processor, processor = self._get_processor()
        processed, skipped = processor.run()
        self.assertEqual(processed, 4)
        self.assertEqual(skipped, 0)
        self.assertEqual(
            {'bar-{}'.format(ident) for ident in range(4)},
            doc_processor.docs_processed
        )

        doc_processor, processor = self._get_processor(reset=True)
        processed, skipped = processor.run()
        self.assertEqual(processed, 4)
        self.assertEqual(skipped, 0)
        self.assertEqual(
            {'bar-{}'.format(ident) for ident in range(4)},
            doc_processor.docs_processed
        )

    def test_multiple_doc_types(self):
        chunk_size = 3
        self.db.add_view("all_docs/by_doc_type", self._get_view_results(4, chunk_size, doc_type="Foo"))
        self.db.update_view("all_docs/by_doc_type", self._get_view_results(4, chunk_size, doc_type="Bar"))

        doc_types = [Bar, ('Foo', Bar)]
        doc_processor, processor = self._get_processor(chunk_size=chunk_size, doc_types=doc_types)
        processor, skipped = processor.run()
        self.assertEqual(processor, 8)
        self.assertEqual(skipped, 0)
        self.assertEqual(
            {'bar-{}'.format(ident) for ident in range(4)} | {'foo-{}'.format(ident) for ident in range(4)},
            doc_processor.docs_processed
        )
