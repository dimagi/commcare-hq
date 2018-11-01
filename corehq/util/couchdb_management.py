from __future__ import absolute_import
from __future__ import unicode_literals
from couchdbkit.client import Database
from corehq.util.couch import get_document_class_by_doc_type
from memoized import memoized
from django.conf import settings
from corehq.util.exceptions import DatabaseNotFound


class CouchConfig(object):
    """
    Interface for accessing the couch-related settings

    You can use db_uri pass in a different couch instance
    from the one specified by COUCH_DATABASE

    """

    def __init__(self, config=None):
        if config:
            self._settings_helper = (
                settings.COUCH_SETTINGS_HELPER._replace(couch_database_configs=config)
            )
        else:
            self._settings_helper = settings.COUCH_SETTINGS_HELPER

    @property
    def db_uri(self):
        return self._settings_helper.main_db_url

    @property
    @memoized
    def all_db_uris_by_slug(self):
        dbs = self._settings_helper.get_extra_couchdbs()
        dbs[None] = self.db_uri
        return dbs

    @property
    @memoized
    def all_dbs_by_slug(self):
        return {slug: Database(**db_uri.params)
                for slug, db_uri in self.all_db_uris_by_slug.items()}

    @property
    @memoized
    def all_dbs_by_db_name(self):
        return {db.dbname: db for db in self.all_dbs_by_slug.values()}

    def get_db(self, postfix):
        """
        Get the couch database by slug
        """
        return Database(create=True, **self.all_db_uris_by_slug[postfix].params)

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

    def get_db_for_class(self, klass):
        return Database(**self.get_db_uri_for_class(klass).params)

    def get_db_for_doc_type(self, doc_type):
        return Database(**self.get_db_uri_for_doc_type(doc_type).params)

    def get_db_for_db_name(self, db_name):
        try:
            return self.all_dbs_by_db_name[db_name]
        except KeyError:
            raise DatabaseNotFound('no database with name {} in settings! Options are: {}'.format(
                db_name, ', '.join(self.all_dbs_by_db_name)
            ))


couch_config = CouchConfig()
