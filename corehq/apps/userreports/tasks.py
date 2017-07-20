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
from django.db.models import Count, F, Min
from django.utils.translation import ugettext as _
from elasticsearch.exceptions import ConnectionTimeout
from restkit import RequestError

from corehq import toggles
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
from corehq.util.quickcache import quickcache
from corehq.util.timer import TimingContext
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
def rebuild_indicators(indicator_config_id, initiated_by=None):
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
            config.save()

        adapter.rebuild_table()
        iteratively_build_table(config)


@task(queue=UCR_CELERY_QUEUE, ignore_result=True)
def rebuild_indicators_in_place(indicator_config_id, initiated_by=None):
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
        iteratively_build_table(config, in_place=True)


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
            iteratively_build_table(config, last_id, resume_helper)


def iteratively_build_table(config, last_id=None, resume_helper=None, in_place=False):
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


@periodic_task(
    run_every=crontab(minute="*/5"),
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def queue_async_indicators():
    start = datetime.utcnow()
    cutoff = start + ASYNC_INDICATOR_QUEUE_TIME
    time_for_crit_section = ASYNC_INDICATOR_QUEUE_TIME.seconds - 10

    oldest_indicator = AsyncIndicator.objects.order_by('date_queued').first()
    if oldest_indicator and oldest_indicator.date_queued:
        lag = (datetime.utcnow() - oldest_indicator.date_queued).total_seconds()
        datadog_gauge('commcare.async_indicator.oldest_queued_indicator', lag)

    with CriticalSection(['queue-async-indicators'], timeout=time_for_crit_section):
        day_ago = datetime.utcnow() - timedelta(days=1)
        indicators = AsyncIndicator.objects.all()[:settings.ASYNC_INDICATORS_TO_QUEUE]
        if indicators:
            lag = (datetime.utcnow() - indicators[0].date_created).total_seconds()
            datadog_gauge('commcare.async_indicator.oldest_created_indicator', lag)
        indicators_by_domain_doc_type = defaultdict(list)
        for indicator in indicators:
            # don't requeue anything htat's be queued in the past day
            if not indicator.date_queued or indicator.date_queued < day_ago:
                indicators_by_domain_doc_type[(indicator.domain, indicator.doc_type)].append(indicator)

        for k, indicators in indicators_by_domain_doc_type.items():
            now = datetime.utcnow()
            if now > cutoff:
                break
            _queue_indicators(indicators)


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
                successfully_processed = _save_document_helper(indicator, doc)
                if successfully_processed:
                    processed_indicators.append(indicator.pk)
                else:
                    failed_indicators.append(indicator.pk)

        AsyncIndicator.objects.filter(pk__in=processed_indicators).delete()
        AsyncIndicator.objects.filter(pk__in=failed_indicators).update(
            date_queued=None, unsuccessful_attempts=F('unsuccessful_attempts') + 1
        )

    datadog_histogram(
        'commcare.async_indicator.processing_time', timer.duration,
        tags=[
            u'config_ids:{}'.format(indicator_config_ids)
        ]
    )


def _save_document_helper(indicator, doc):
    eval_context = EvaluationContext(doc)
    something_failed = False
    for config_id in indicator.indicator_config_ids:
        adapter = None
        try:
            config = _get_config(config_id)
        except (ResourceNotFound, StaticDataSourceConfigurationNotFoundError):
            celery_task_logger.info("{} no longer exists, skipping".format(config_id))
            continue
        except ESError:
            celery_task_logger.info("ES errored when trying to retrieve config")
            something_failed = True
            return
        try:
            adapter = get_indicator_adapter(config, can_handle_laboratory=True)
            adapter.save(doc, eval_context)
            eval_context.reset_iteration()
        except (DatabaseError, ESError, InternalError, RequestError,
                ConnectionTimeout, ProtocolError, ReadTimeout):
            # a database had an issue so log it and go on to the next document
            celery_task_logger.info("DB error when saving config: {}".format(config_id))
            something_failed = True
            return
        except Exception as e:
            # getting the config could fail before the adapter is set
            if adapter:
                adapter.handle_exception(doc, e)
            something_failed = True
            return

    return not something_failed


@periodic_task(
    run_every=crontab(minute="*/15"),
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def async_indicators_metrics():
    for config_id, metrics in _indicator_metrics().iteritems():
        tags = ["config_id:{}".format(config_id)]
        datadog_gauge('commcare.async_indicator.indicator_count', metrics['count'], tags=tags)
        datadog_gauge('commcare.async_indicator.lag', metrics['lag'], tags=tags)


def _indicator_metrics(date_created=None):
    """
    returns {
        "config_id": {
            "count": number of indicators with that config,
            "lag": earliest created record
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
    if date_created:
        indicator_metrics = indicator_metrics.filter(date_created__lt=date_created)
    for ind in indicator_metrics:
        count = ind['indicator_config_ids__count']
        lag = ind['date_created__min']
        for config_id in ind['indicator_config_ids']:
            if ret.get(config_id):
                ret[config_id]['count'] += ind['indicator_config_ids__count']
                ret[config_id]['lag'] = min(lag, ret['config_id']['lag'])
            else:
                ret[config_id] = {
                    "count": count,
                    "lag": lag
                }

    return ret


@periodic_task(
    run_every=crontab(minute="*/15"),
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def icds_async_indicators_metrics():
    indicator_count_until_28 = _indicator_metrics(datetime(2017, 6, 28))

    for config_id, metrics in indicator_count_until_28.iteritems():
        tags = ["config_id:{}".format(config_id)]
        datadog_gauge('commcare.async_indicator.icds_rebuild', metrics['count'], tags=tags)
