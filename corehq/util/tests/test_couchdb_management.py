from django.conf import settings
from django.test import SimpleTestCase
from corehq.util.couchdb_management import CouchConfig, couch_config
from corehq.util.exceptions import DatabaseNotFound


class CouchConfigTest(SimpleTestCase):
    remote_db_uri = 'https://mycouch.com/cchq'

    def test_default_db_uri(self):
        config = CouchConfig()
        self.assertEqual(config.db_uri, settings.COUCH_DATABASE)

    def test_default_couch_config_db_uri(self):
        self.assertEqual(couch_config.db_uri, settings.COUCH_DATABASE)

    def test_remote_db_uri(self):
        config = CouchConfig(db_uri=self.remote_db_uri)
        self.assertEqual(config.db_uri, self.remote_db_uri)

    def test_all_db_uris_by_slug(self):
        config = CouchConfig(db_uri=self.remote_db_uri)
        self.assertDictContainsSubset(
            {
                None: self.remote_db_uri,
                'users': '{}__users'.format(self.remote_db_uri),
                'fixtures': '{}__fixtures'.format(self.remote_db_uri),
                'meta': '{}__meta'.format(self.remote_db_uri),
            },
            config.all_db_uris_by_slug
        )

    def test_get_db_for_doc_type(self):
        config = CouchConfig(db_uri=self.remote_db_uri)
        self.assertEqual(config.get_db_for_doc_type('CommCareCase').uri, self.remote_db_uri)
        self.assertEqual(config.get_db_for_doc_type('CommCareUser').uri,
                         '{}__users'.format(self.remote_db_uri))

    def test_get_db_for_db_name(self):
        config = CouchConfig(db_uri=self.remote_db_uri)
        self.assertEqual(self.remote_db_uri, config.get_db_for_db_name('cchq').uri)
        self.assertEqual('{}__users'.format(self.remote_db_uri), config.get_db_for_db_name('cchq__users').uri)

    def test_get_db_for_db_name_not_found(self):
        config = CouchConfig(db_uri=self.remote_db_uri)
        with self.assertRaises(DatabaseNotFound):
            config.get_db_for_db_name('missing')
