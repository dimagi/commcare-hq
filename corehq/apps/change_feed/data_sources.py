from django.conf import settings
from corehq.apps.change_feed.exceptions import UnknownDocumentStore
from corehq.util.couchdb_management import couch_config
from corehq.util.exceptions import DatabaseNotFound
from pillowtop.dao.couch import CouchDocumentStore

COUCH = 'couch'
FORM_SQL = 'form-sql'

def get_document_store(data_source_type, data_source_name):
    if data_source_type == COUCH:
        try:
            return CouchDocumentStore(couch_config.get_db_for_db_name(data_source_name))
        except DatabaseNotFound:
            # in debug mode we may be flipping around our databases so don't fail hard here
            if settings.DEBUG:
                return None
            raise
    else:
        raise UnknownDocumentStore(
            'getting document stores for backend {} is not supported!'.format(data_source_type)
        )
