from couchdbkit.client import Database
from corehq.util.couch import get_document_class_by_doc_type
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings
from corehq.util.exceptions import DatabaseNotFound


class CouchConfig(object):
    """
    Interface for accessing the couch-related settings

    You can use db_uri pass in a different couch instance
    from the one specified by COUCH_DATABASE

    """
    def __init__(self, db_uri=None):
        if db_uri:
            self._settings_helper = (
                settings.COUCH_SETTINGS_HELPER._replace(couch_database_url=db_uri))
        else:
            self._settings_helper = settings.COUCH_SETTINGS_HELPER

    @property
    def db_uri(self):
        return self._settings_helper.couch_database_url

    @property
    @memoized
    def all_db_uris_by_slug(self):
        dbs = self._settings_helper.get_extra_couchdbs()
        dbs[None] = self.db_uri
        return dbs

    @property
    @memoized
    def all_dbs_by_slug(self):
        return {slug: Database(db_uri)
                for slug, db_uri in self.all_db_uris_by_slug.items()}

    @property
    @memoized
    def all_dbs_by_db_name(self):
        return {Database(db_uri).dbname: Database(db_uri)
                for db_uri in self.all_db_uris_by_slug.values()}

    def get_db(self, postfix):
        """
        Get the couch database by slug
        """
        return Database(self.all_db_uris_by_slug[postfix], create=True)

    @property
    @memoized
    def app_label_to_db_uri(self):
        return dict(self._settings_helper.make_couchdb_tuples())

    def get_db_uri_for_app_label(self, app_label):
        return self.app_label_to_db_uri[app_label]

    def get_db_uri_for_class(self, klass):
        return self.app_label_to_db_uri[getattr(klass._meta, "app_label")]

    def get_db_uri_for_doc_type(self, doc_type):
        return self.get_db_uri_for_class(get_document_class_by_doc_type(doc_type))

    def get_db_for_app_label(self, app_label):
        return Database(self.get_db_uri_for_app_label(app_label))

    def get_db_for_class(self, klass):
        return Database(self.get_db_uri_for_class(klass))

    def get_db_for_doc_type(self, doc_type):
        return Database(self.get_db_uri_for_doc_type(doc_type))

    def get_db_for_db_name(self, db_name):
        try:
            return self.all_dbs_by_db_name[db_name]
        except KeyError:
            raise DatabaseNotFound('no database with name {} in settings!'.format(db_name))


couch_config = CouchConfig()
