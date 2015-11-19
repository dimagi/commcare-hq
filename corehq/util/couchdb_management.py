from couchdbkit.client import Database
from dimagi.ext.couchdbkit import Document
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

    @property
    @memoized
    def all_dbs_by_slug(self):
        dbs = self._settings_helper.get_extra_couchdbs()
        dbs[None] = self.db_uri
        return dbs

    def get_db(self, postfix):
        """
        Get the couch database by slug
        """
        return Database(self.all_dbs_by_slug[postfix], create=True)

    @property
    @memoized
    def app_label_to_db_slug(self):
        return dict(self._settings_helper.make_couchdb_tuples())

    def get_db_for_class(self, klass):
        return self.app_label_to_db_slug[getattr(klass._meta, "app_label")]

    def get_db_for_doc_type(self, doc_type):
        return self.get_db_for_class(class_by_doc_type()[doc_type])


@memoized
def class_by_doc_type():
    queue = [Document]
    m = {}
    while queue:
        klass = queue.pop()
        app_label = getattr(klass._meta, "app_label", None)
        if app_label:
            m[klass._doc_type] = klass
        queue.extend(klass.__subclasses__())
    return m


couch_config = CouchConfig()
