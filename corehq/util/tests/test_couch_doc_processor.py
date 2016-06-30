from couchdbkit import ResourceConflict, ResourceNotFound
from django.test import TestCase
from django.test.testcases import SimpleTestCase
from fakecouch import FakeCouchDb

from corehq.util.couch_doc_processor import ResumableDocsByTypeIterator, TooManyRetries, BaseDocProcessor, \
    CouchDocumentProcessor
from dimagi.ext.couchdbkit import Document
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
            for n in ["bar", "baz", "foo"]
            for i in range(3)]
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

    def get_iterator(self):
        return ResumableDocsByTypeIterator(self.db, self.doc_types, "test", 2)

    def test_iteration(self):
        self.assertEqual([doc["_id"] for doc in self.itr], self.sorted_keys)

    def test_resume_iteration(self):
        itr = iter(self.itr)
        self.assertEqual([next(itr)["_id"] for i in range(6)], self.sorted_keys[:6])
        # stop/resume iteration
        self.itr = self.get_iterator()
        self.assertEqual([doc["_id"] for doc in self.itr], self.sorted_keys[4:])

    def test_resume_iteration_after_complete_iteration(self):
        self.assertEqual([doc["_id"] for doc in self.itr], self.sorted_keys)
        # resume iteration
        self.itr = self.get_iterator()
        self.assertEqual([doc["_id"] for doc in self.itr], [])

    def test_iteration_with_retry(self):
        itr = iter(self.itr)
        doc = next(itr)
        self.itr.retry(doc)
        self.assertEqual(doc["_id"], "bar-0")
        self.assertEqual(["bar-0"] + [d["_id"] for d in itr],
                         self.sorted_keys + ["bar-0"])

    def test_iteration_complete_after_retry(self):
        itr = iter(self.itr)
        self.itr.retry(next(itr))
        list(itr)
        self.itr = self.get_iterator()
        self.assertEqual([doc["_id"] for doc in self.itr], [])

    def test_iteration_with_max_retry(self):
        itr = iter(self.itr)
        doc = next(itr)
        ids = [doc["_id"]]
        self.assertEqual(doc["_id"], "bar-0")
        self.itr.retry(doc)
        retries = 1
        for doc in itr:
            ids.append(doc["_id"])
            if doc["_id"] == "bar-0":
                if retries < 3:
                    self.itr.retry(doc)
                    retries += 1
                else:
                    break
        self.assertEqual(doc["_id"], "bar-0")
        with self.assertRaises(TooManyRetries):
            self.itr.retry(doc)
        self.assertEqual(ids, self.sorted_keys + ["bar-0", "bar-0", "bar-0"])
        self.assertEqual(list(itr), [])
        self.assertEqual(list(self.get_iterator()), [])

    def test_iteration_with_missing_retry_doc(self):
        itr = iter(self.itr)
        doc = next(itr)
        self.assertEqual(doc["_id"], "bar-0")
        self.itr.retry(doc)
        self.db.delete_doc(doc)
        try:
            self.assertEqual(["bar-0"] + [d["_id"] for d in itr],
                             self.sorted_keys)
        finally:
            self.create_doc("Bar", 0)

    def test_iteration_with_progress_info(self):
        itr = iter(self.itr)
        self.assertEqual([next(itr)["_id"] for i in range(6)], self.sorted_keys[:6])
        self.assertEqual(self.itr.progress_info, None)
        self.itr.progress_info = {"visited": 6}
        # stop/resume iteration
        self.itr = self.get_iterator()
        self.assertEqual(self.itr.progress_info, {"visited": 6})
        self.itr.progress_info = {"visited": "six"}
        # stop/resume iteration
        self.itr = self.get_iterator()
        self.assertEqual(self.itr.progress_info, {"visited": "six"})
        self.assertEqual([doc["_id"] for doc in self.itr], self.sorted_keys[4:])


class DemoProcessor(BaseDocProcessor):
    def __init__(self, slug, ignore_docs=None, skip_docs=None):
        super(DemoProcessor, self).__init__(slug)
        self.skip_docs = skip_docs
        self.ignore_docs = ignore_docs or []
        self.docs_processed = set()

    def should_process(self, doc):
        return doc['_id'] not in self.ignore_docs

    @property
    def unique_key(self):
        return self.slug + '-test'

    def process_doc(self, doc, couchdb):
        doc_id = doc['_id']
        if self.skip_docs and doc_id in self.skip_docs:
            return False
        self.docs_processed.add(doc_id)
        return True


class Bar(Document):
    pass


class TestCouchDocProcessor(SimpleTestCase):
    @staticmethod
    def _get_row(ident):
        doc_id = 'bar-{}'.format(ident)
        return {
            'id': doc_id,
            'key': ['Bar', doc_id], 'value': None, 'doc': {'_id': doc_id, 'doc_type': 'Bar'}
        }

    def setUp(self):
        views = {
            "all_docs/by_doc_type": [
                (
                    {"endkey": ["Bar", {}], "group_level": 1, "reduce": True, "startkey": ["Bar"]},
                    [{"key": "Bar", "value": 4}]
                ),
                (
                    {
                        'startkey': ['Bar'], 'endkey': ['Bar', {}], 'reduce': False,
                        'limit': 2, 'include_docs': True
                    },
                    [
                        self._get_row(0),
                        self._get_row(1),
                    ]
                ),
                (
                    {
                        'endkey': ['Bar', {}], 'skip': 1, 'startkey_docid': 'bar-1', 'reduce': False,
                        'startkey': ['Bar', 'bar-1'], 'limit': 2, 'include_docs': True
                    },
                    [
                        self._get_row(2),
                        self._get_row(3),
                    ]
                ),
        ]}
        docs = [self._get_row(ident)['doc'] for ident in range(4)]
        self.db = FakeCouchDb(views=views, docs={
            doc['_id']: doc for doc in docs
        })
        Bar.set_db(self.db)

    def tearDown(self):
        self.db.reset()

    def _test_processor(self, expected_processed, doc_idents, ignore_docs=None, skip_docs=None):
        doc_processor, processor = self._get_processor()
        if ignore_docs:
            doc_processor.ignore_docs = ignore_docs
        if skip_docs:
            doc_processor.skip_docs = skip_docs
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
        self._test_processor(2, range(2), skip_docs=['bar-2', 'bar-3'])
        self._test_processor(2, [2, 3])

    @staticmethod
    def _get_processor():
        doc_processor = DemoProcessor('test')
        processor = CouchDocumentProcessor(
            {'Bar': Bar},
            doc_processor,
            chunk_size=2,
        )
        return doc_processor, processor
