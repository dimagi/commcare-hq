import datetime

from celery.task import task
from couchdbkit import ResourceConflict
from django.utils.translation import ugettext as _
from corehq import toggles
from corehq.apps.userreports.const import UCR_ES_BACKEND, UCR_SQL_BACKEND, UCR_CELERY_QUEUE
from corehq.apps.userreports.document_stores import get_document_store
from corehq.apps.userreports.rebuild import DataSourceResumeHelper
from corehq.apps.userreports.models import (
    DataSourceConfiguration, StaticDataSourceConfiguration, id_is_static, ReportConfiguration
)
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.util.context_managers import notify_someone
from corehq.util.couch import get_document_or_not_found
from dimagi.utils.couch.pagination import DatatablesParams
from pillowtop.dao.couch import ID_CHUNK_SIZE


def _get_config_by_id(indicator_config_id):
    if id_is_static(indicator_config_id):
        return StaticDataSourceConfiguration.by_id(indicator_config_id)
    else:
        return DataSourceConfiguration.get(indicator_config_id)


def _build_indicators(config, document_store, relevant_ids, resume_helper):
    adapter = get_indicator_adapter(config, raise_errors=True, can_handle_laboratory=True)

    last_id = None
    for doc in document_store.iter_documents(relevant_ids):
        # save is a noop if the filter doesn't match
        adapter.best_effort_save(doc)
        last_id = doc.get('_id')
        resume_helper.remove_id(last_id)

    if last_id:
        resume_helper.add_id(last_id)


@task(queue=UCR_CELERY_QUEUE, ignore_result=True)
def rebuild_indicators(indicator_config_id, initiated_by=None, limit=-1):
    config = _get_config_by_id(indicator_config_id)
    success = _('Your UCR table {} has finished rebuilding').format(config.table_id)
    failure = _('There was an error rebuilding Your UCR table {}.').format(config.table_id)
    send = toggles.SEND_UCR_REBUILD_INFO.enabled(initiated_by)
    with notify_someone(initiated_by, success_message=success, error_message=failure, send=send):
        adapter = get_indicator_adapter(config, can_handle_laboratory=True)
        if not id_is_static(indicator_config_id):
            # Save the start time now in case anything goes wrong. This way we'll be
            # able to see if the rebuild started a long time ago without finishing.
            config.meta.build.initiated = datetime.datetime.utcnow()
            config.meta.build.finished = False
            config.save()

        adapter.rebuild_table()
        _iteratively_build_table(config, limit=limit)


@task(queue=UCR_CELERY_QUEUE, ignore_result=True)
def rebuild_indicators_in_place(indicator_config_id, initiated_by=None):
    config = _get_config_by_id(indicator_config_id)
    success = _('Your UCR table {} has finished rebuilding').format(config.table_id)
    failure = _('There was an error rebuilding Your UCR table {}.').format(config.table_id)
    send = toggles.SEND_UCR_REBUILD_INFO.enabled(initiated_by)
    with notify_someone(initiated_by, success_message=success, error_message=failure, send=send):
        adapter = get_indicator_adapter(config, can_handle_laboratory=True)
        if not id_is_static(indicator_config_id):
            # Save the start time now in case anything goes wrong. This way we'll be
            # able to see if the rebuild started a long time ago without finishing.
            config.meta.build.initiated = datetime.datetime.utcnow()
            config.meta.build.finished = False
            config.save()

        adapter.build_table()
        _iteratively_build_table(config)


@task(queue=UCR_CELERY_QUEUE, ignore_result=True, acks_late=True)
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


def _iteratively_build_table(config, last_id=None, resume_helper=None, limit=-1):
    resume_helper = resume_helper or DataSourceResumeHelper(config)
    indicator_config_id = config._id

    relevant_ids = []
    document_store = get_document_store(config.domain, config.referenced_doc_type)
    for i, relevant_id in enumerate(document_store.iter_document_ids(last_id)):
        if last_id is None and i >= limit > -1:
            break
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
        adapter = get_indicator_adapter(config, raise_errors=True, can_handle_laboratory=True)
        adapter.after_table_build()


@task(queue=UCR_CELERY_QUEUE)
def compare_ucr_dbs(domain, report_config_id, filter_values, sort_column, sort_order, params):
    from corehq.apps.userreports.laboratory.experiment import UCRExperiment

    def _run_report(backend_to_use):
        data_source = ReportFactory.from_spec(spec, include_prefilters=True, backend=backend_to_use)
        data_source.set_filter_values(filter_values)
        if sort_column:
            data_source.set_order_by(
                [(data_source.top_level_columns[int(sort_column)].column_id, sort_order.upper())]
            )

        datatables_params = DatatablesParams.from_request_dict(params)
        page = list(data_source.get_data(start=datatables_params.start, limit=datatables_params.count))
        total_records = data_source.get_total_records()
        json_response = {
            'aaData': page,
            "iTotalRecords": total_records,
        }
        total_row = data_source.get_total_row() if data_source.has_total_row else None
        if total_row is not None:
            json_response["total_row"] = total_row
        return json_response

    spec = get_document_or_not_found(ReportConfiguration, domain, report_config_id)
    experiment_context = {
        "domain": domain,
        "report_config_id": report_config_id,
        "filter_values": filter_values,
    }
    experiment = UCRExperiment(name="UCR DB Experiment", context=experiment_context)
    with experiment.control() as c:
        c.record(_run_report(UCR_SQL_BACKEND))

    with experiment.candidate() as c:
        c.record(_run_report(UCR_ES_BACKEND))

    objects = experiment.run()
    return objects


@task(queue=UCR_CELERY_QUEUE, ignore_result=True)
def delete_data_source_task(domain, config_id):
    from corehq.apps.userreports.views import delete_data_source_shared
    delete_data_source_shared(domain, config_id)
