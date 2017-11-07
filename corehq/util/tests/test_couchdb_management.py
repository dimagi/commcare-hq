from __future__ import absolute_import
from django.conf import settings
from django.test import SimpleTestCase
from corehq.util.couchdb_management import CouchConfig, couch_config
from corehq.util.exceptions import DatabaseNotFound


class CouchConfigTest(SimpleTestCase):
    remote_db_uri = 'https://mycouch.com/test_cchq'

    @property
    def _config(self):
        return {
            key: {
                "COUCH_HTTPS": True,
                'COUCH_SERVER_ROOT': 'mycouch.com',
                'COUCH_USERNAME': '',
                'COUCH_PASSWORD': '',
                'COUCH_DATABASE_NAME': 'cchq{}'.format('__' + key if key else '')

            }
            for key in ['users', 'fixtures', 'meta', None]
        }

    def test_default_db_uri(self):
        config = CouchConfig()
        self.assertEqual(config.db_uri, settings.COUCH_DATABASE)

    def test_default_couch_config_db_uri(self):
        self.assertEqual(couch_config.db_uri, settings.COUCH_DATABASE)

    def test_remote_db_uri(self):
        config = CouchConfig(config=self._config)
        self.assertEqual(config.db_uri, self.remote_db_uri)

    def test_all_db_uris_by_slug(self):
        config = CouchConfig(config=self._config)
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
        config = CouchConfig(config=self._config)
        self.assertEqual(config.get_db_for_doc_type('CommCareCase').uri, self.remote_db_uri)
        self.assertEqual(config.get_db_for_doc_type('CommCareUser').uri,
                         '{}__users'.format(self.remote_db_uri))

    def test_get_db_for_db_name(self):
        config = CouchConfig(config=self._config)
        self.assertEqual(self.remote_db_uri, config.get_db_for_db_name('test_cchq').uri)
        self.assertEqual('{}__users'.format(self.remote_db_uri), config.get_db_for_db_name('test_cchq__users').uri)

    def test_get_db_for_db_name_not_found(self):
        config = CouchConfig(config=self._config)
        with self.assertRaises(DatabaseNotFound):
            config.get_db_for_db_name('missing')
