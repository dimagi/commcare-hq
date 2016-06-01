from django.test import TestCase

from couchdbkit import ResourceConflict, ResourceNotFound
from corehq.util.couch_helpers import ResumableDocsByTypeIterator, TooManyRetries
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
