from django.conf import settings
from django.test import TestCase
from pillowtop.couchdb import CachedCouchDB


class CachedCouchDbTest(TestCase):

    def test_bulk_load_missing(self):
        db = CachedCouchDB(settings.COUCH_DATABASE, readonly=False)
        # before this test was patched this used to fail
        db.bulk_load(['missing1', 'missing2'])
