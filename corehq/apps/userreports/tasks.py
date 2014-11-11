import logging
from celery.task import task
from sqlalchemy.exc import DataError
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.utils import get_doc_ids
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.sql import IndicatorSqlAdapter, get_engine
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs


@task
def rebuild_indicators(indicator_config_id):
    config = DataSourceConfiguration.get(indicator_config_id)
    adapter = IndicatorSqlAdapter(get_engine(), config)
    adapter.rebuild_table()

    couchdb = _get_db(config.referenced_doc_type)
    relevant_ids = get_doc_ids(config.domain, config.referenced_doc_type,
                               database=couchdb)

    for doc in iter_docs(couchdb, relevant_ids, chunksize=500):
        if config.filter.filter(doc):
            try:
                adapter.save(doc)
            except DataError as e:
                logging.exception('problem saving document {} to table. {}'.format(doc['_id'], e))


def _get_db(doc_type):
    return _DOC_TYPE_MAPPING.get(doc_type, CommCareCase).get_db()


# This is intentionally not using magic to introspect the class from the name, though it could
_DOC_TYPE_MAPPING = {
    'XFormInstance': XFormInstance,
    'CommCareCase': CommCareCase,
}
