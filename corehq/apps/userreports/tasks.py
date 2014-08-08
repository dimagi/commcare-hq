from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.utils import get_doc_ids
from corehq.apps.userreports.models import IndicatorConfiguration
from corehq.apps.userreports.sql import IndicatorSqlAdapter, get_engine
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs


def rebuild_indicators(indicator_config_id):
    config = IndicatorConfiguration.get(indicator_config_id)
    adapter = IndicatorSqlAdapter(get_engine(), config)
    adapter.rebuild_table()

    couchdb = _get_db(config.referenced_doc_type)
    relevant_ids = get_doc_ids(config.domain, config.referenced_doc_type,
                               database=couchdb)

    for doc in iter_docs(couchdb, relevant_ids, chunksize=500):
        if config.filter.filter(doc):
            adapter.save(doc)


def _get_db(doc_type):
    # This is intentionally not using magic to introspect the class from the name, though it could
    doc_type_mapping = {
        'XFormInstance': XFormInstance,
        'CommCareCase': CommCareCase,
    }
    return doc_type_mapping.get(doc_type, CommCareCase).get_db()
