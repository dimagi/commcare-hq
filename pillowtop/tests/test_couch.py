from django.test import SimpleTestCase
from pillowtop.listener import BasicPillow


class TestCouchPillow(BasicPillow):
    pass


class CouchPillowTest(SimpleTestCase):

    def test_initialize_no_couch_fails(self):
        with self.assertRaises(ValueError):
            TestCouchPillow().couch_db
