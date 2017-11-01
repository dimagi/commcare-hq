from __future__ import absolute_import
from collections import defaultdict
from datetime import datetime, timedelta
import logging

from botocore.vendored.requests.exceptions import ReadTimeout
from botocore.vendored.requests.packages.urllib3.exceptions import ProtocolError
from celery.schedules import crontab
from celery.task import task, periodic_task
from couchdbkit import ResourceConflict, ResourceNotFound
from django.conf import settings
from django.db import InternalError, DatabaseError
from django.db import transaction
from django.db.models import Count, Min
from django.utils.translation import ugettext as _
from elasticsearch.exceptions import ConnectionTimeout
from restkit import RequestError

from couchexport.export import export_from_tables
from couchexport.models import Format
from soil.util import get_download_file_path, expose_download

from corehq import toggles
from corehq.apps.reports.util import send_report_download_email
from corehq.apps.userreports.const import (
    UCR_ES_BACKEND, UCR_SQL_BACKEND, UCR_CELERY_QUEUE, UCR_INDICATOR_CELERY_QUEUE,
    ASYNC_INDICATOR_QUEUE_TIME, ASYNC_INDICATOR_CHUNK_SIZE
)
from corehq.apps.userreports.document_stores import get_document_store
from corehq.apps.userreports.exceptions import StaticDataSourceConfigurationNotFoundError
from corehq.apps.userreports.rebuild import DataSourceResumeHelper
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.userreports.models import (
    AsyncIndicator,
    DataSourceConfiguration,
    StaticDataSourceConfiguration,
    id_is_static,
    get_report_config,
)
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.userreports.util import get_indicator_adapter, get_async_indicator_modify_lock_key
from corehq.elastic import ESError
from corehq.util.context_managers import notify_someone
from corehq.util.datadog.gauges import datadog_gauge, datadog_histogram
from corehq.util.decorators import serial_task
from corehq.util.quickcache import quickcache
from corehq.util.timer import TimingContext
from corehq.util.view_utils import reverse
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.pagination import DatatablesParams
from pillowtop.dao.couch import ID_CHUNK_SIZE

celery_task_logger = logging.getLogger('celery.task')


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
            config.meta.build.initiated = datetime.utcnow()
            config.meta.build.finished = False
            config.meta.build.rebuilt_asynchronously = False
            config.save()

        adapter.rebuild_table()
        _iteratively_build_table(config, limit=limit)


@task(queue=UCR_CELERY_QUEUE, ignore_result=True)
def rebuild_indicators_in_place(indicator_config_id, initiated_by=None, doc_id_provider=None):
    config = _get_config_by_id(indicator_config_id)
    success = _('Your UCR table {} has finished rebuilding').format(config.table_id)
    failure = _('There was an error rebuilding Your UCR table {}.').format(config.table_id)
    send = toggles.SEND_UCR_REBUILD_INFO.enabled(initiated_by)
    with notify_someone(initiated_by, success_message=success, error_message=failure, send=send):
        adapter = get_indicator_adapter(config, can_handle_laboratory=True)
        if not id_is_static(indicator_config_id):
            config.meta.build.initiated_in_place = datetime.utcnow()
            config.meta.build.finished_in_place = False
            config.save()

        adapter.build_table()
        _iteratively_build_table(config, in_place=True, doc_id_provider=doc_id_provider)


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


@task(queue=UCR_CELERY_QUEUE, ignore_result=True)
def recalculate_indicators(indicator_config_id, initiated_by=None):
    config = _get_config_by_id(indicator_config_id)
    adapter = get_indicator_adapter(config)
    doc_id_provider = adapter.get_distinct_values('doc_id', 10000)[0]
    rebuild_indicators_in_place(indicator_config_id, initiated_by, doc_id_provider)


def _iteratively_build_table(config, last_id=None, resume_helper=None,
                             in_place=False, doc_id_provider=None, limit=-1):
    resume_helper = resume_helper or DataSourceResumeHelper(config)
    indicator_config_id = config._id
    case_type_or_xmlns = config.get_case_type_or_xmlns_filter()

    relevant_ids = []
    document_store = get_document_store(
        config.domain, config.referenced_doc_type, case_type_or_xmlns=case_type_or_xmlns
    )

    if not doc_id_provider:
        doc_id_provider = document_store.iter_document_ids(last_id)

    for i, relevant_id in enumerate(doc_id_provider):
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
        if in_place:
            config.meta.build.finished_in_place = True
        else:
            config.meta.build.finished = True
        try:
            config.save()
        except ResourceConflict:
            current_config = DataSourceConfiguration.get(config._id)
            # check that a new build has not yet started
            if in_place:
                if config.meta.build.initiated_in_place == current_config.meta.build.initiated_in_place:
                    current_config.meta.build.finished_in_place = True
            else:
                if config.meta.build.initiated == current_config.meta.build.initiated:
                    current_config.meta.build.finished = True
            current_config.save()
        adapter = get_indicator_adapter(config, raise_errors=True, can_handle_laboratory=True)
        adapter.after_table_build()


@task(queue=UCR_CELERY_QUEUE)
def compare_ucr_dbs(domain, report_config_id, filter_values, sort_column=None, sort_order=None, params=None):
    from corehq.apps.userreports.laboratory.experiment import UCRExperiment

    def _run_report(backend_to_use):
        data_source = ReportFactory.from_spec(spec, include_prefilters=True, backend=backend_to_use)
        data_source.set_filter_values(filter_values)
        if sort_column:
            data_source.set_order_by(
                [(data_source.top_level_columns[int(sort_column)].column_id, sort_order.upper())]
            )

        if params:
            datatables_params = DatatablesParams.from_request_dict(params)
            start = datatables_params.start
            limit = datatables_params.count
        else:
            start, limit = None, None
        page = list(data_source.get_data(start=start, limit=limit))
        total_records = data_source.get_total_records()
        json_response = {
            'aaData': page,
            "iTotalRecords": total_records,
        }
        total_row = data_source.get_total_row() if data_source.has_total_row else None
        if total_row is not None:
            json_response["total_row"] = total_row
        return json_response

    spec, is_static = get_report_config(report_config_id, domain)
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


@periodic_task(
    run_every=settings.ASYNC_INDICATOR_QUEUE_CRONTAB, queue=settings.CELERY_PERIODIC_QUEUE
)
def run_queue_async_indicators_task():
    queue_async_indicators.delay()


@serial_task('queue-async-indicators', timeout=30 * 60, queue=settings.CELERY_PERIODIC_QUEUE, max_retries=0)
def queue_async_indicators():
    start = datetime.utcnow()
    cutoff = start + ASYNC_INDICATOR_QUEUE_TIME - timedelta(seconds=30)
    day_ago = start - timedelta(days=1)
    # don't requeue anything that has been retired more than 20 times
    indicators = AsyncIndicator.objects.filter(unsuccessful_attempts__lt=20)[:settings.ASYNC_INDICATORS_TO_QUEUE]
    indicators_by_domain_doc_type = defaultdict(list)
    for indicator in indicators:
        # don't requeue anything that's be queued in the past day
        if not indicator.date_queued or indicator.date_queued < day_ago:
            indicators_by_domain_doc_type[(indicator.domain, indicator.doc_type)].append(indicator)

    for k, indicators in indicators_by_domain_doc_type.items():
        _queue_indicators(indicators)
        if datetime.utcnow() > cutoff:
            break


def _queue_indicators(indicators):
    def _queue_chunk(indicators):
        now = datetime.utcnow()
        indicator_doc_ids = [i.doc_id for i in indicators]
        AsyncIndicator.objects.filter(doc_id__in=indicator_doc_ids).update(date_queued=now)
        save_document.delay(indicator_doc_ids)

    to_queue = []
    for indicator in indicators:
        to_queue.append(indicator)
        if len(to_queue) >= ASYNC_INDICATOR_CHUNK_SIZE:
            _queue_chunk(to_queue)
            to_queue = []

    if to_queue:
        _queue_chunk(to_queue)


@quickcache(['config_id'])
def _get_config(config_id):
    # performance optimization for save_document. don't use elsewhere
    return _get_config_by_id(config_id)


@task(queue=UCR_INDICATOR_CELERY_QUEUE, ignore_result=True, acks_late=True)
def save_document(doc_ids):
    lock_keys = []
    for doc_id in doc_ids:
        lock_keys.append(get_async_indicator_modify_lock_key(doc_id))

    indicator_config_ids = None
    timer = TimingContext()
    with CriticalSection(lock_keys):
        indicators = AsyncIndicator.objects.filter(doc_id__in=doc_ids)
        if not indicators:
            return

        first_indicator = indicators[0]
        processed_indicators = []
        failed_indicators = []

        for i in indicators:
            assert i.domain == first_indicator.domain
            assert i.doc_type == first_indicator.doc_type

        indicator_by_doc_id = {i.doc_id: i for i in indicators}
        doc_store = get_document_store(first_indicator.domain, first_indicator.doc_type)
        indicator_config_ids = first_indicator.indicator_config_ids

        with timer:
            for doc in doc_store.iter_documents(doc_ids):
                indicator = indicator_by_doc_id[doc['_id']]
                successfully_processed, to_remove = _save_document_helper(indicator, doc)
                if successfully_processed:
                    processed_indicators.append(indicator.pk)
                else:
                    failed_indicators.append((indicator, to_remove))

        AsyncIndicator.objects.filter(pk__in=processed_indicators).delete()
        with transaction.atomic():
            for indicator, to_remove in failed_indicators:
                indicator.update_failure(to_remove)
                indicator.save()

    datadog_histogram(
        'commcare.async_indicator.processing_time', timer.duration,
        tags=[
            u'config_ids:{}'.format(indicator_config_ids)
        ]
    )


def _save_document_helper(indicator, doc):
    eval_context = EvaluationContext(doc)
    something_failed = False
    configs_to_remove = []
    for config_id in indicator.indicator_config_ids:
        adapter = None
        try:
            config = _get_config(config_id)
        except (ResourceNotFound, StaticDataSourceConfigurationNotFoundError):
            celery_task_logger.info("{} no longer exists, skipping".format(config_id))
            configs_to_remove.append(config_id)
            continue
        except ESError:
            celery_task_logger.info("ES errored when trying to retrieve config")
            something_failed = True
            continue
        try:
            adapter = get_indicator_adapter(config, can_handle_laboratory=True)
            adapter.save(doc, eval_context)
            eval_context.reset_iteration()
        except (DatabaseError, ESError, InternalError, RequestError,
                ConnectionTimeout, ProtocolError, ReadTimeout):
            # a database had an issue so log it and go on to the next document
            celery_task_logger.info("DB error when saving config: {}".format(config_id))
            something_failed = True
        except Exception as e:
            # getting the config could fail before the adapter is set
            if adapter:
                adapter.handle_exception(doc, e)
            something_failed = True
        else:
            configs_to_remove.append(config_id)

    return (not something_failed, configs_to_remove)


@periodic_task(
    run_every=crontab(minute="*/15"),
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def async_indicators_metrics():
    oldest_indicator = AsyncIndicator.objects.order_by('date_queued').first()
    if oldest_indicator and oldest_indicator.date_queued:
        lag = (datetime.utcnow() - oldest_indicator.date_queued).total_seconds()
        datadog_gauge('commcare.async_indicator.oldest_queued_indicator', lag)

    indicator = AsyncIndicator.objects.first()
    if indicator:
        lag = (datetime.utcnow() - indicator.date_created).total_seconds()
        datadog_gauge('commcare.async_indicator.oldest_created_indicator', lag)

    for config_id, metrics in _indicator_metrics().iteritems():
        tags = ["config_id:{}".format(config_id)]
        datadog_gauge('commcare.async_indicator.indicator_count', metrics['count'], tags=tags)
        datadog_gauge('commcare.async_indicator.lag', metrics['lag'], tags=tags)

    # Don't use ORM summing because it would attempt to get every value in DB
    unsuccessful_attempts = sum(AsyncIndicator.objects.values_list('unsuccessful_attempts', flat=True).all()[:100])
    datadog_gauge('commcare.async_indicator.unsuccessful_attempts', unsuccessful_attempts)


def _indicator_metrics(date_created=None):
    """
    returns {
        "config_id": {
            "count": number of indicators with that config,
            "lag": number of seconds ago that the row was created
        }
    }
    """
    ret = {}
    indicator_metrics = (
        AsyncIndicator.objects
        .values('indicator_config_ids')
        .annotate(Count('indicator_config_ids'), Min('date_created'))
        .order_by()  # needed to get rid of implict ordering by date_created
    )
    now = datetime.utcnow()
    if date_created:
        indicator_metrics = indicator_metrics.filter(date_created__lt=date_created)
    for ind in indicator_metrics:
        count = ind['indicator_config_ids__count']
        lag = (now - ind['date_created__min']).total_seconds()
        for config_id in ind['indicator_config_ids']:
            if ret.get(config_id):
                ret[config_id]['count'] += ind['indicator_config_ids__count']
                ret[config_id]['lag'] = max(lag, ret[config_id]['lag'])
            else:
                ret[config_id] = {
                    "count": count,
                    "lag": lag
                }

    return ret


@task
def export_ucr_async(export_table, download_id, title, user):
    use_transfer = settings.SHARED_DRIVE_CONF.transfer_enabled
    filename = u'{}.xlsx'.format(title)
    file_path = get_download_file_path(use_transfer, filename)
    export_from_tables(export_table, file_path, Format.XLS_2007)
    expose_download(use_transfer, file_path, filename, download_id, 'xlsx')
    link = reverse("retrieve_download", args=[download_id], params={"get_file": '1'}, absolute=True)

    send_report_download_email(title, user, link)
