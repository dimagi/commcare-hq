from couchdbkit import Database
from django.conf import settings
from django.test import TestCase
from pillowtop.couchdb import CachedCouchDB


class CachedCouchDbTest(TestCase):

    @classmethod
    def setUpClass(cls):
        # this will ensure the database is created
        Database(settings.COUCH_DATABASE, create=True)

    def test_bulk_load_missing(self):
        db = CachedCouchDB(settings.COUCH_DATABASE, readonly=False)
        # before this test was patched this used to fail
        db.bulk_load(['missing1', 'missing2'])
