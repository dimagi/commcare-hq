from Queue import Queue
import threading
from couchdbkit import Database
from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from corehq.util.couch_helpers import OverrideDB, _override_db
from django.conf import settings


class OverrideDBTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.other_db_1 = Database(settings.COUCH_DATABASE + '_foo-test', create=True)
        cls.other_db_2 = Database(settings.COUCH_DATABASE + '_foo-boo-test', create=True)
        cls.normal_db = CommCareCase.get_db()
        cls.normal_get_db = CommCareCase.get_db

    def setUp(self):
        self.assertEqual(self.normal_db.dbname, 'test_commcarehq')

    @classmethod
    def tearDownClass(cls):
        cls.other_db_1.server.delete_db(cls.other_db_1.dbname)
        cls.other_db_2.server.delete_db(cls.other_db_2.dbname)

    def test_nested(self):
        self.assertEqual(CommCareCase.get_db(), self.normal_db)
        self.assertEqual(CommCareCase.get_db, self.normal_get_db)

        with OverrideDB(CommCareCase, self.other_db_1):
            self.assertEqual(CommCareCase.get_db(), self.other_db_1)
            self.assertNotEqual(CommCareCase.get_db(), self.normal_db)
            self.assertNotEqual(CommCareCase.get_db(), self.normal_get_db)

            with OverrideDB(CommCareCase, self.other_db_2):
                self.assertEqual(CommCareCase.get_db(), self.other_db_2)
                self.assertNotEqual(CommCareCase.get_db(), self.normal_db)
                self.assertNotEqual(CommCareCase.get_db(), self.normal_get_db)

            self.assertEqual(CommCareCase.get_db(), self.other_db_1)
            self.assertNotEqual(CommCareCase.get_db(), self.normal_db)
            self.assertNotEqual(CommCareCase.get_db(), self.normal_get_db)

        self.assertEqual(CommCareCase.get_db(), self.normal_db)
        self.assertEqual(CommCareCase.get_db, self.normal_get_db)

    def test_series(self):
        self.assertEqual(CommCareCase.get_db(), self.normal_db)
        self.assertEqual(CommCareCase.get_db, self.normal_get_db)

        with OverrideDB(CommCareCase, self.other_db_1):
            self.assertEqual(CommCareCase.get_db(), self.other_db_1)
            self.assertNotEqual(CommCareCase.get_db(), self.normal_db)
            self.assertNotEqual(CommCareCase.get_db(), self.normal_get_db)

        self.assertEqual(CommCareCase.get_db(), self.normal_db)
        self.assertEqual(CommCareCase.get_db, self.normal_get_db)

        with OverrideDB(CommCareCase, self.other_db_2):
            self.assertEqual(CommCareCase.get_db(), self.other_db_2)
            self.assertNotEqual(CommCareCase.get_db(), self.normal_db)
            self.assertNotEqual(CommCareCase.get_db(), self.normal_get_db)

        self.assertEqual(CommCareCase.get_db(), self.normal_db)
        self.assertEqual(CommCareCase.get_db, self.normal_get_db)

    def test_threading(self):
        result_queue = Queue()

        with OverrideDB(CommCareCase, self.other_db_1):
            obj = _override_db.class_to_db

        def run():
            with OverrideDB(CommCareCase, self.other_db_2):
                result_queue.put(_override_db.class_to_db)

        t = threading.Thread(target=run)
        t.start()
        t.join()
        result = result_queue.get_nowait()
        self.assertNotEqual(id(obj), id(result))
