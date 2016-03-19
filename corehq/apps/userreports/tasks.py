import datetime
import logging

from celery.task import task
from couchdbkit import ResourceConflict

from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq.apps.domain.dbaccessors import iterate_doc_ids_in_domain_by_type
from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration
from corehq.apps.userreports.sql import IndicatorSqlAdapter

CHUNK_SIZE = 10000


def is_static(config_id):
    return config_id.startswith(StaticDataSourceConfiguration._datasource_id_prefix)


def _get_config_by_id(indicator_config_id):
    if is_static(indicator_config_id):
        return StaticDataSourceConfiguration.by_id(indicator_config_id)
    else:
        return DataSourceConfiguration.get(indicator_config_id)


def _get_redis_key_for_config(config):
    if is_static(config._id):
        rev = 'static'
    else:
        rev = config._rev
    return 'ucr_queue-{}:{}'.format(config._id, rev)


def _build_indicators(indicator_config_id, relevant_ids):
    config = _get_config_by_id(indicator_config_id)
    adapter = IndicatorSqlAdapter(config)
    couchdb = _get_db(config.referenced_doc_type)
    redis_client = get_redis_client().client.get_client()
    redis_key = _get_redis_key_for_config(config)

    last_id = None
    for doc in iter_docs(couchdb, relevant_ids, chunksize=500):
        try:
            # save is a noop if the filter doesn't match
            adapter.save(doc)
            last_id = doc.get('_id')
            try:
                redis_client.lrem(redis_key, 1, last_id)
            except:
                redis_client.srem(redis_key, last_id)
        except Exception as e:
            logging.exception('problem saving document {} to table. {}'.format(doc['_id'], e))

    if last_id:
        redis_client.rpush(redis_key, last_id)


@task(queue='ucr_queue', ignore_result=True)
def rebuild_indicators(indicator_config_id):
    config = _get_config_by_id(indicator_config_id)
    adapter = IndicatorSqlAdapter(config)

    if not is_static(indicator_config_id):
        # Save the start time now in case anything goes wrong. This way we'll be
        # able to see if the rebuild started a long time ago without finishing.
        config.meta.build.initiated = datetime.datetime.utcnow()
        config.meta.build.finished = False
        config.save()

    adapter.rebuild_table()
    _iteratively_build_table(config)


@task(queue='ucr_queue', ignore_result=True, acks_late=True)
def resume_building_indicators(indicator_config_id):
    config = _get_config_by_id(indicator_config_id)
    redis_client = get_redis_client().client.get_client()
    redis_key = _get_redis_key_for_config(config)

    # maintaining support for existing sets in redis while the
    # transition to lists occurs
    try:
        relevant_ids = redis_client.lrange(redis_key, 0, -1)
    except:
        relevant_ids = tuple(redis_client.smembers(redis_key))
    if len(relevant_ids) > 0:
        _build_indicators(indicator_config_id, relevant_ids)
        last_id = relevant_ids[-1]

        _iteratively_build_table(config, last_id)


def _iteratively_build_table(config, last_id=None):
    couchdb = _get_db(config.referenced_doc_type)
    redis_client = get_redis_client().client.get_client()
    redis_key = _get_redis_key_for_config(config)
    indicator_config_id = config._id

    relevant_ids = []
    for relevant_id in iterate_doc_ids_in_domain_by_type(
            config.domain,
            config.referenced_doc_type,
            chunk_size=CHUNK_SIZE,
            database=couchdb,
            startkey_docid=last_id):
        relevant_ids.append(relevant_id)
        if len(relevant_ids) >= CHUNK_SIZE:
            redis_client.rpush(redis_key, *relevant_ids)
            _build_indicators(indicator_config_id, relevant_ids)
            relevant_ids = []

    if relevant_ids:
        redis_client.rpush(redis_key, *relevant_ids)
        _build_indicators(indicator_config_id, relevant_ids)

    if not is_static(indicator_config_id):
        redis_client.delete(redis_key)
        config.meta.build.finished = True
        try:
            config.save()
        except ResourceConflict:
            current_config = DataSourceConfiguration.get(config._id)
            # check that a new build has not yet started
            if config.meta.build.initiated == current_config.meta.build.initiated:
                current_config.meta.build.finished = True
                current_config.save()


def _get_db(doc_type):
    return _DOC_TYPE_MAPPING.get(doc_type, CommCareCase).get_db()


# This is intentionally not using magic to introspect the class from the name, though it could
from corehq.apps.locations.models import Location
_DOC_TYPE_MAPPING = {
    'XFormInstance': XFormInstance,
    'CommCareCase': CommCareCase,
    'Location': Location
}
