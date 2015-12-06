from corehq.apps.change_feed.exceptions import UnknownDocumentStore
from corehq.util.couchdb_management import couch_config
from pillowtop.dao.couch import CouchDocumentStore

COUCH = 'couch'


def get_document_store(data_source_type, data_source_name):
    if data_source_type == COUCH:
        return CouchDocumentStore(couch_config.get_db_for_db_name(data_source_name))
    else:
        raise UnknownDocumentStore(
            'getting document stores for backend {} is not supported!'.format(data_source_type)
        )
