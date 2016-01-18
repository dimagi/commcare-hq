from django.conf import settings
from corehq.apps.change_feed.exceptions import UnknownDocumentStore
from corehq.util.couchdb_management import couch_config
from corehq.util.exceptions import DatabaseNotFound
from pillowtop.dao.couch import CouchDocumentStore

COUCH = 'couch'
POSTGRES = 'postgres'


def get_document_store(data_source_type, data_source_name=None):
    if data_source_type == COUCH:
        try:
            return CouchDocumentStore(couch_config.get_db_for_db_name(data_source_name))
        except DatabaseNotFound:
            # in debug mode we may be flipping around our databases so don't fail hard here
            if settings.DEBUG:
                return None
            raise
    elif data_source_type == POSTGRES:
        conn = psycopg2.connect(
            database='commcarehq',
            user='commcarehq',
            password='commcarehq',
        )
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        return conn
    else:
        raise UnknownDocumentStore(
            'getting document stores for backend {} is not supported!'.format(data_source_type)
        )
