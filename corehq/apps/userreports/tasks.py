import datetime

from couchdbkit import ResourceConflict
from django.utils.translation import ugettext as _
from corehq import toggles
from corehq.apps.userreports.document_stores import get_document_store
from corehq.apps.userreports.rebuild import DataSourceResumeHelper
from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration, id_is_static
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.util.celery_utils import hqtask
from corehq.util.context_managers import notify_someone
from pillowtop.dao.couch import ID_CHUNK_SIZE


def _get_config_by_id(indicator_config_id):
    if id_is_static(indicator_config_id):
        return StaticDataSourceConfiguration.by_id(indicator_config_id)
    else:
        return DataSourceConfiguration.get(indicator_config_id)


def _build_indicators(config, document_store, relevant_ids, resume_helper):
    adapter = get_indicator_adapter(config, raise_errors=True)

    last_id = None
    for doc in document_store.iter_documents(relevant_ids):
        # save is a noop if the filter doesn't match
        adapter.best_effort_save(doc)
        last_id = doc.get('_id')
        resume_helper.remove_id(last_id)

    if last_id:
        resume_helper.add_id(last_id)


@hqtask(queue='ucr_queue', ignore_result=True)
def rebuild_indicators(indicator_config_id, initiated_by=None):
    config = _get_config_by_id(indicator_config_id)
    success = _('Your UCR table {} has finished rebuilding').format(config.table_id)
    failure = _('There was an error rebuilding Your UCR table {}.').format(config.table_id)
    send = toggles.SEND_UCR_REBUILD_INFO.enabled(initiated_by)
    with notify_someone(initiated_by, success_message=success, error_message=failure, send=send):
        adapter = get_indicator_adapter(config)
        if not id_is_static(indicator_config_id):
            # Save the start time now in case anything goes wrong. This way we'll be
            # able to see if the rebuild started a long time ago without finishing.
            config.meta.build.initiated = datetime.datetime.utcnow()
            config.meta.build.finished = False
            config.save()

        adapter.rebuild_table()
        _iteratively_build_table(config)


@hqtask(queue='ucr_queue', ignore_result=True, acks_late=True)
def resume_building_indicators(indicator_config_id, initiated_by=None):
    config = _get_config_by_id(indicator_config_id)
    success = _('Your UCR table {} has finished rebuilding').format(config.table_id)
    failure = _('There was an error rebuilding Your UCR table {}.').format(config.table_id)
    send = toggles.SEND_UCR_REBUILD_INFO.enabled(initiated_by)
    with notify_someone(initiated_by, success_message=success, error_message=failure, send=send):
        resume_helper = DataSourceResumeHelper(config)

        relevant_ids = resume_helper.get_ids_to_resume_from()
        if len(relevant_ids) > 0:
            _build_indicators(config, get_document_store(config.domain, config.referenced_doc_type), relevant_ids,
                              resume_helper)
            last_id = relevant_ids[-1]
            _iteratively_build_table(config, last_id, resume_helper)


def _iteratively_build_table(config, last_id=None, resume_helper=None):
    resume_helper = resume_helper or DataSourceResumeHelper(config)
    indicator_config_id = config._id

    relevant_ids = []
    document_store = get_document_store(config.domain, config.referenced_doc_type)
    for relevant_id in document_store.iter_document_ids(last_id):
        relevant_ids.append(relevant_id)
        if len(relevant_ids) >= ID_CHUNK_SIZE:
            resume_helper.set_ids_to_resume_from(relevant_ids)
            _build_indicators(config, document_store, relevant_ids, resume_helper)
            relevant_ids = []

    if relevant_ids:
        resume_helper.set_ids_to_resume_from(relevant_ids)
        _build_indicators(config, document_store, relevant_ids, resume_helper)

    if not id_is_static(indicator_config_id):
        resume_helper.clear_ids()
        config.meta.build.finished = True
        try:
            config.save()
        except ResourceConflict:
            current_config = DataSourceConfiguration.get(config._id)
            # check that a new build has not yet started
            if config.meta.build.initiated == current_config.meta.build.initiated:
                current_config.meta.build.finished = True
                current_config.save()
