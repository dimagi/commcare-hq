import datetime
import logging
from celery.task import task
from sqlalchemy.exc import DataError
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.utils import get_doc_ids
from corehq.apps.userreports.models import DataSourceConfiguration, CustomDataSourceConfiguration
from corehq.apps.userreports.sql import IndicatorSqlAdapter, get_engine
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs


@task(queue='background_queue')
def rebuild_indicators(indicator_config_id):
    is_static = indicator_config_id.startswith(CustomDataSourceConfiguration._datasource_id_prefix)
    if is_static:
        config = CustomDataSourceConfiguration.by_id(indicator_config_id)
    else:
        config = DataSourceConfiguration.get(indicator_config_id)
        # Save the start time now in case anything goes wrong. This way we'll be
        # able to see if the rebuild started a long time ago without finishing.
        config.meta.build.initiated = datetime.datetime.now()
        config.save()

    adapter = IndicatorSqlAdapter(get_engine(), config)
    adapter.rebuild_table()

    couchdb = _get_db(config.referenced_doc_type)
    relevant_ids = get_doc_ids(config.domain, config.referenced_doc_type,
                               database=couchdb)

    for doc in iter_docs(couchdb, relevant_ids, chunksize=500):
        try:
            # save is a noop if the filter doesn't match
            adapter.save(doc)
        except DataError as e:
            logging.exception('problem saving document {} to table. {}'.format(doc['_id'], e))
    adapter.engine.dispose()

    if not is_static:
        config.meta.build.finished = True
        config.save()


def _get_db(doc_type):
    return _DOC_TYPE_MAPPING.get(doc_type, CommCareCase).get_db()


# This is intentionally not using magic to introspect the class from the name, though it could
_DOC_TYPE_MAPPING = {
    'XFormInstance': XFormInstance,
    'CommCareCase': CommCareCase,
}
