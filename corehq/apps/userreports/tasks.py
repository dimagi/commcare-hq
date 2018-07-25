from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
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

from couchexport.models import Format
from soil.util import get_download_file_path, expose_download

from corehq import toggles
from corehq.apps.reports.util import send_report_download_email, DatatablesParams
from corehq.apps.userreports.const import (
    UCR_CELERY_QUEUE, UCR_INDICATOR_CELERY_QUEUE,
    ASYNC_INDICATOR_QUEUE_TIME, ASYNC_INDICATOR_CHUNK_SIZE
)
from corehq.apps.change_feed.data_sources import get_document_store_for_doc_type
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
from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
from corehq.apps.userreports.util import get_indicator_adapter, get_async_indicator_modify_lock_key
from corehq.elastic import ESError
from corehq.util.context_managers import notify_someone
from corehq.util.datadog.gauges import datadog_gauge, datadog_histogram, datadog_counter
from corehq.util.decorators import serial_task
from corehq.util.quickcache import quickcache
from corehq.util.timer import TimingContext
from corehq.util.view_utils import reverse
from custom.icds_reports.ucr.expressions import icds_get_related_docs_ids
from dimagi.utils.couch import CriticalSection
from pillowtop.dao.couch import ID_CHUNK_SIZE
import six

celery_task_logger = logging.getLogger('celery.task')


def _get_config_by_id(indicator_config_id):
    if id_is_static(indicator_config_id):
        return StaticDataSourceConfiguration.by_id(indicator_config_id)
    else:
        return DataSourceConfiguration.get(indicator_config_id)


def _build_indicators(config, document_store, relevant_ids):
    adapter = get_indicator_adapter(config, raise_errors=True, can_handle_laboratory=True)

    for doc in document_store.iter_documents(relevant_ids):
        if config.asynchronous:
            AsyncIndicator.update_record(
                doc.get('_id'), config.referenced_doc_type, config.domain, [config._id]
            )
        else:
            # save is a noop if the filter doesn't match
            adapter.best_effort_save(doc)


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
            config.meta.build.rebuilt_asynchronously = False
            config.save()

        adapter.build_table()
        _iteratively_build_table(config, in_place=True)


@task(queue=UCR_CELERY_QUEUE, ignore_result=True, acks_late=True)
def resume_building_indicators(indicator_config_id, initiated_by=None):
    config = _get_config_by_id(indicator_config_id)
    success = _('Your UCR table {} has finished rebuilding').format(config.table_id)
    failure = _('There was an error rebuilding Your UCR table {}.').format(config.table_id)
    send = toggles.SEND_UCR_REBUILD_INFO.enabled(initiated_by)
    with notify_someone(initiated_by, success_message=success, error_message=failure, send=send):
        resume_helper = DataSourceResumeHelper(config)

        _iteratively_build_table(config, resume_helper)


def _iteratively_build_table(config, resume_helper=None, in_place=False, limit=-1):
    resume_helper = resume_helper or DataSourceResumeHelper(config)
    indicator_config_id = config._id
    case_type_or_xmlns_list = config.get_case_type_or_xmlns_filter()
    completed_ct_xmlns = resume_helper.get_completed_case_type_or_xmlns()
    if completed_ct_xmlns:
        case_type_or_xmlns_list = [
            case_type_or_xmlns
            for case_type_or_xmlns in case_type_or_xmlns_list
            if case_type_or_xmlns not in completed_ct_xmlns
        ]

    for case_type_or_xmlns in case_type_or_xmlns_list:
        relevant_ids = []
        document_store = get_document_store_for_doc_type(
            config.domain, config.referenced_doc_type, case_type_or_xmlns=case_type_or_xmlns
        )

        for i, relevant_id in enumerate(document_store.iter_document_ids()):
            if i >= limit > -1:
                break
            relevant_ids.append(relevant_id)
            if len(relevant_ids) >= ID_CHUNK_SIZE:
                _build_indicators(config, document_store, relevant_ids)
                relevant_ids = []

        if relevant_ids:
            _build_indicators(config, document_store, relevant_ids)

        resume_helper.add_completed_case_type_or_xmlns(case_type_or_xmlns)

    resume_helper.clear_resume_info()
    if not id_is_static(indicator_config_id):
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

    new_report_config_id = settings.UCR_COMPARISONS.get(report_config_id)
    if new_report_config_id is None:
        return

    def _run_report(spec):
        data_source = ConfigurableReportDataSource.from_spec(spec, include_prefilters=True)
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

    old_spec, unused = get_report_config(report_config_id, domain)
    new_spec, unused = get_report_config(new_report_config_id, domain)
    experiment_context = {
        "domain": domain,
        "report_config_id": report_config_id,
        "new_report_config_id": new_report_config_id,
        "filter_values": filter_values,
    }
    experiment = UCRExperiment(name="UCR DB Experiment", context=experiment_context)
    with experiment.control() as c:
        c.record(_run_report(old_spec))

    with experiment.candidate() as c:
        c.record(_run_report(new_spec))

    objects = experiment.run()
    return objects


@task(queue=UCR_CELERY_QUEUE, ignore_result=True)
def delete_data_source_task(domain, config_id):
    from corehq.apps.userreports.views import delete_data_source_shared
    delete_data_source_shared(domain, config_id)


@periodic_task(
    run_every=crontab(minute='*/5'), queue=settings.CELERY_PERIODIC_QUEUE
)
def run_queue_async_indicators_task():
    if time_in_range(datetime.utcnow(), settings.ASYNC_INDICATOR_QUEUE_TIMES):
        queue_async_indicators.delay()


@serial_task('queue-async-indicators', timeout=30 * 60, queue=settings.CELERY_PERIODIC_QUEUE, max_retries=0)
def queue_async_indicators():
    start = datetime.utcnow()
    cutoff = start + ASYNC_INDICATOR_QUEUE_TIME - timedelta(seconds=30)
    retry_threshold = start - timedelta(hours=4)
    # don't requeue anything that has been retired more than 20 times
    indicators = AsyncIndicator.objects.filter(unsuccessful_attempts__lt=20)[:settings.ASYNC_INDICATORS_TO_QUEUE]
    indicators_by_domain_doc_type = defaultdict(list)
    for indicator in indicators:
        # only requeue things that have were last queued earlier than the threshold
        if not indicator.date_queued or indicator.date_queued < retry_threshold:
            indicators_by_domain_doc_type[(indicator.domain, indicator.doc_type)].append(indicator)

    for k, indicators in indicators_by_domain_doc_type.items():
        _queue_indicators(indicators)
        if datetime.utcnow() > cutoff:
            break


def time_in_range(time, time_dictionary):
    """time_dictionary will be of the format:
    {
        '*': [(begin_hour, end_hour), (begin_hour, end_hour), ...] catch all for days
        1: [(begin_hour, end_hour), ...] hours for Monday (Monday 1, Sunday 7)
    }
    All times UTC
    """

    if not time_dictionary:
        return True

    hours_for_today = time_dictionary.get(time.isoweekday())
    if not hours_for_today:
        hours_for_today = time_dictionary.get('*')

    for valid_hours in hours_for_today:
        if valid_hours[0] <= time.hour <= valid_hours[1]:
            return True

    return False


def _queue_indicators(indicators):
    def _queue_chunk(indicators):
        now = datetime.utcnow()
        indicator_doc_ids = [i.doc_id for i in indicators]
        AsyncIndicator.objects.filter(doc_id__in=indicator_doc_ids).update(date_queued=now)
        save_document.delay(indicator_doc_ids)
        datadog_counter('commcare.async_indicator.indicators_queued', len(indicator_doc_ids))

    to_queue = []
    for indicator in indicators:
        to_queue.append(indicator)
        if len(to_queue) >= ASYNC_INDICATOR_CHUNK_SIZE:
            _queue_chunk(to_queue)
            to_queue = []

    if to_queue:
        _queue_chunk(to_queue)


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
        doc_store = get_document_store_for_doc_type(first_indicator.domain, first_indicator.doc_type)
        indicator_config_ids = first_indicator.indicator_config_ids
        related_docs_to_rebuild = set()

        with timer:
            for doc in doc_store.iter_documents(list(indicator_by_doc_id.keys())):
                indicator = indicator_by_doc_id[doc['_id']]
                successfully_processed, to_remove, rebuild_related_docs = _save_document_helper(indicator, doc)
                if rebuild_related_docs:
                    related_docs_to_rebuild = related_docs_to_rebuild.union(icds_get_related_docs_ids(doc['_id']))
                if successfully_processed:
                    processed_indicators.append(indicator.pk)
                else:
                    failed_indicators.append((indicator, to_remove))

        num_processed = len(processed_indicators)
        num_failed = len(failed_indicators)
        AsyncIndicator.objects.filter(pk__in=processed_indicators).delete()
        with transaction.atomic():
            for indicator, to_remove in failed_indicators:
                indicator.update_failure(to_remove)
                indicator.save()

    # remove any related docs that were just rebuilt
    related_docs_to_rebuild = related_docs_to_rebuild - set(doc_ids)
    # queue the docs that aren't already queued
    _queue_indicators(AsyncIndicator.objects.filter(
        doc_id__in=related_docs_to_rebuild, date_queued=None
    ))

    datadog_counter('commcare.async_indicator.processed_success', num_processed)
    datadog_counter('commcare.async_indicator.processed_fail', num_failed)
    datadog_histogram(
        'commcare.async_indicator.processing_time', timer.duration,
        tags=[
            'config_ids:{}'.format(indicator_config_ids)
        ]
    )


def _save_document_helper(indicator, doc):
    eval_context = EvaluationContext(doc)
    something_failed = False
    configs_to_remove = []
    configs = dict()
    for config_id in indicator.indicator_config_ids:
        try:
            configs[config_id] = _get_config_by_id(config_id)
        except (ResourceNotFound, StaticDataSourceConfigurationNotFoundError):
            celery_task_logger.info("{} no longer exists, skipping".format(config_id))
            configs_to_remove.append(config_id)
            continue
        except ESError:
            celery_task_logger.info("ES errored when trying to retrieve config")
            something_failed = True
            continue

    for config_id, config in six.iteritems(configs):
        adapter = None
        try:
            adapter = get_indicator_adapter(config, can_handle_laboratory=True)
            adapter.save(doc, eval_context)
            eval_context.reset_iteration()
        except (ProtocolError, ReadTimeout):
            celery_task_logger.info("Riak error when saving config: {}".format(config_id))
            something_failed = True
        except (ESError, ConnectionTimeout):
            # a database had an issue so log it and go on to the next document
            celery_task_logger.info("ES error when saving config: {}".format(config_id))
            something_failed = True
        except (DatabaseError, InternalError):
            # a database had an issue so log it and go on to the next document
            celery_task_logger.info("psql error when saving config: {}".format(config_id))
            something_failed = True
        except Exception as e:
            # getting the config could fail before the adapter is set
            if adapter:
                adapter.handle_exception(doc, e)
            something_failed = True
        else:
            configs_to_remove.append(config_id)

    rebuild_related_docs = any(config.icds_rebuild_related_docs for config in six.itervalues(configs) if config)
    return (not something_failed, configs_to_remove, rebuild_related_docs)


@periodic_task(
    run_every=crontab(minute="*/5"),
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def async_indicators_metrics():
    now = datetime.utcnow()
    oldest_indicator = AsyncIndicator.objects.order_by('date_queued').first()
    if oldest_indicator and oldest_indicator.date_queued:
        lag = (now - oldest_indicator.date_queued).total_seconds()
        datadog_gauge('commcare.async_indicator.oldest_queued_indicator', lag)

    oldest_100_indicators = AsyncIndicator.objects.all()[:100]
    if oldest_100_indicators.exists():
        oldest_indicator = oldest_100_indicators[0]
        lag = (now - oldest_indicator.date_created).total_seconds()
        datadog_gauge('commcare.async_indicator.oldest_created_indicator', lag)

        lags = [
            (now - indicator.date_created).total_seconds()
            for indicator in oldest_100_indicators
        ]
        avg_lag = sum(lags) / len(lags)
        datadog_gauge('commcare.async_indicator.oldest_created_indicator_avg', avg_lag)

    for config_id, metrics in six.iteritems(_indicator_metrics()):
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
def export_ucr_async(report_export, download_id, user):
    use_transfer = settings.SHARED_DRIVE_CONF.transfer_enabled
    ascii_title = report_export.title.encode('ascii', 'replace')
    filename = '{}.xlsx'.format(ascii_title.replace('/', '?'))
    file_path = get_download_file_path(use_transfer, filename)

    report_export.create_export(file_path, Format.XLS_2007)

    expose_download(use_transfer, file_path, filename, download_id, 'xlsx')
    link = reverse("retrieve_download", args=[download_id], params={"get_file": '1'}, absolute=True)

    send_report_download_email(report_export.title, user, link)
