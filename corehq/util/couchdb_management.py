from couchdbkit.client import Database
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings


class CouchConfig(object):
    def __init__(self, db_uri=None):
        if db_uri:
            self._settings_helper = (
                settings.COUCH_SETTINGS_HELPER._replace(couch_database_url=db_uri))
        else:
            self._settings_helper = settings.COUCH_SETTINGS_HELPER

    @property
    def db_uri(self):
        return self._settings_helper.couch_database_url

    def get_db(self, postfix):
        """
        Get the couch database.
        """
        if postfix:
            db_uri = settings.EXTRA_COUCHDB_DATABASES[postfix]
        else:
            db_uri = self.db_uri
        return Database(db_uri, create=True)

    @property
    @memoized
    def app_label_to_db_slug(self):
        return dict(self._settings_helper.make_couchdb_tuples())

    def get_db_for_class(self, klass):
        return self.app_label_to_db_slug[klass.Meta.app_label]


couch_config = CouchConfig()
