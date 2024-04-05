import itertools
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from django.conf import settings
from django.db import DatabaseError, InternalError, transaction
from django.db.models import Count, Min
from django.utils.translation import gettext as _

from botocore.vendored.requests.exceptions import ReadTimeout
from botocore.vendored.requests.packages.urllib3.exceptions import (
    ProtocolError,
)
from celery.schedules import crontab
from couchdbkit import ResourceConflict, ResourceNotFound

from couchexport.models import Format
from dimagi.utils.chunked import chunked
from dimagi.utils.couch import CriticalSection
from dimagi.utils.logging import notify_exception
from pillowtop.dao.couch import ID_CHUNK_SIZE
from soil.util import expose_download, get_download_file_path

from corehq.apps.celery import periodic_task, task
from corehq.apps.change_feed.data_sources import (
    get_document_store_for_doc_type,
)
from corehq.apps.reports.util import send_report_download_email
from corehq.apps.userreports.const import (
    ASYNC_INDICATOR_CHUNK_SIZE,
    ASYNC_INDICATOR_MAX_RETRIES,
    ASYNC_INDICATOR_QUEUE_TIME,
    UCR_CELERY_QUEUE,
    UCR_INDICATOR_CELERY_QUEUE,
)
from corehq.apps.userreports.exceptions import (
    DataSourceConfigurationNotFoundError,
)
from corehq.apps.userreports.models import (
    AsyncIndicator,
    id_is_static,
)
from corehq.apps.userreports.rebuild import DataSourceResumeHelper
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.userreports.util import (
    get_async_indicator_modify_lock_key,
    get_indicator_adapter,
    get_ucr_datasource_config_by_id,
)
from corehq.elastic import ESError
from corehq.util.context_managers import notify_someone
from corehq.util.decorators import serial_task
from corehq.util.es.elasticsearch import ConnectionTimeout
from corehq.util.metrics import (
    metrics_counter,
    metrics_gauge,
    metrics_histogram_timer,
)
from corehq.util.metrics.const import MPM_LIVESUM, MPM_MAX, MPM_MIN
from corehq.util.queries import paginated_queryset
from corehq.util.timer import TimingContext
from corehq.util.view_utils import reverse

celery_task_logger = logging.getLogger('celery.task')


def _build_indicators(config, document_store, relevant_ids):
    adapter = get_indicator_adapter(config, raise_errors=True, load_source='build_indicators')

    for doc in document_store.iter_documents(relevant_ids):
        if config.asynchronous:
            AsyncIndicator.update_record(
                doc.get('_id'), config.referenced_doc_type, config.domain, [config._id]
            )
        else:
            # save is a noop if the filter doesn't match
            adapter.best_effort_save(doc)


@serial_task('{indicator_config_id}', default_retry_delay=60 * 10, timeout=3 * 60 * 60, max_retries=20,
             queue=UCR_CELERY_QUEUE, ignore_result=True, serializer='pickle')
def rebuild_indicators(indicator_config_id, initiated_by=None, limit=-1, source=None,
                       engine_id=None, diffs=None, trigger_time=None, domain=None):
    config = get_ucr_datasource_config_by_id(indicator_config_id)
    if trigger_time is not None and trigger_time < config.last_modified:
        return

    success = _('Your UCR table {} has finished rebuilding in {}').format(config.table_id, config.domain)
    failure = _('There was an error rebuilding Your UCR table {} in {}.').format(config.table_id, config.domain)
    send = limit == -1
    with notify_someone(initiated_by, success_message=success, error_message=failure, send=send):
        adapter = get_indicator_adapter(config)

        if engine_id:
            if getattr(adapter, 'all_adapters', None):
                adapter = [
                    adapter_ for adapter_ in adapter.all_adapters
                    if adapter_.engine_id == engine_id
                ][0]
            elif adapter.engine_id != engine_id:
                raise AssertionError("Engine ID does not match adapter")

        if not id_is_static(indicator_config_id):
            # Save the start time now in case anything goes wrong. This way we'll be
            # able to see if the rebuild started a long time ago without finishing.
            config.meta.build.initiated = datetime.utcnow()
            config.meta.build.finished = False
            config.meta.build.rebuilt_asynchronously = False
            config.save()

        skip_log = bool(limit > 0)  # don't store log for temporary report builder UCRs
        adapter.rebuild_table(initiated_by=initiated_by, source=source, skip_log=skip_log, diffs=diffs)
        _iteratively_build_table(config, limit=limit)


@serial_task(
    '{indicator_config_id}', default_retry_delay=60 * 10, timeout=3 * 60 * 60, max_retries=20,
    queue=UCR_CELERY_QUEUE, ignore_result=True, serializer='pickle'
)
def rebuild_indicators_in_place(indicator_config_id, initiated_by=None, source=None, domain=None):
    config = get_ucr_datasource_config_by_id(indicator_config_id)
    success = _('Your UCR table {} has finished rebuilding in {}').format(config.table_id, config.domain)
    failure = _('There was an error rebuilding Your UCR table {} in {}.').format(config.table_id, config.domain)
    with notify_someone(initiated_by, success_message=success, error_message=failure, send=True):
        adapter = get_indicator_adapter(config)
        if not id_is_static(indicator_config_id):
            config.meta.build.initiated_in_place = datetime.utcnow()
            config.meta.build.finished_in_place = False
            config.meta.build.rebuilt_asynchronously = False
            config.save()

        adapter.build_table(initiated_by=initiated_by, source=source)
        _iteratively_build_table(config, in_place=True)


@task(serializer='pickle', queue=UCR_CELERY_QUEUE, ignore_result=True, acks_late=True)
def resume_building_indicators(indicator_config_id, initiated_by=None):
    config = get_ucr_datasource_config_by_id(indicator_config_id)
    success = _('Your UCR table {} has finished rebuilding in {}').format(config.table_id, config.domain)
    failure = _('There was an error rebuilding Your UCR table {} in {}.').format(config.table_id, config.domain)
    with notify_someone(initiated_by, success_message=success, error_message=failure, send=True):
        resume_helper = DataSourceResumeHelper(config)
        adapter = get_indicator_adapter(config)
        adapter.log_table_build(
            initiated_by=initiated_by,
            source='resume_building_indicators',
        )
        _iteratively_build_table(config, resume_helper)


def _iteratively_build_table(config, resume_helper=None, in_place=False, limit=-1):
    resume_helper = resume_helper or DataSourceResumeHelper(config)
    indicator_config_id = config._id
    loop_iterations = get_loop_iterations_for_rebuild(config)
    completed_iterations = resume_helper.get_completed_iterations()
    if completed_iterations:
        loop_iterations = list(set(loop_iterations) - set(completed_iterations))

    for domain, case_type_or_xmlns in loop_iterations:
        relevant_ids = []
        document_store = get_document_store_for_doc_type(
            domain, config.referenced_doc_type,
            case_type_or_xmlns=case_type_or_xmlns,
            load_source="build_indicators",
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

        resume_helper.add_completed_iteration(domain, case_type_or_xmlns)

    resume_helper.clear_resume_info()
    if not id_is_static(indicator_config_id):
        if in_place:
            config.meta.build.finished_in_place = True
        else:
            config.meta.build.finished = True
        try:
            config.save()
        except ResourceConflict:
            current_config = get_ucr_datasource_config_by_id(config._id)
            # check that a new build has not yet started
            if in_place:
                if config.meta.build.initiated_in_place == current_config.meta.build.initiated_in_place:
                    current_config.meta.build.finished_in_place = True
            else:
                if config.meta.build.initiated == current_config.meta.build.initiated:
                    current_config.meta.build.finished = True
            current_config.save()


def get_loop_iterations_for_rebuild(config):
    case_type_or_xmlns_list = config.get_case_type_or_xmlns_filter()
    domains = config.data_domains

    return list(itertools.product(domains, case_type_or_xmlns_list))


@task(serializer='pickle', queue=UCR_CELERY_QUEUE, ignore_result=True)
def delete_data_source_task(domain, config_id):
    from corehq.apps.userreports.views import delete_data_source_shared
    delete_data_source_shared(domain, config_id)


@periodic_task(run_every=crontab(minute='*/5'), queue=settings.CELERY_PERIODIC_QUEUE)
def run_queue_async_indicators_task():
    """
        A periodic task that runs every few minutes, if ran within the permitted time slots,
        would queue a task to further queue few AsyncIndicators for processing
    """
    if time_in_range(datetime.utcnow(), settings.ASYNC_INDICATOR_QUEUE_TIMES):
        queue_async_indicators.delay()


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


@serial_task('queue-async-indicators', timeout=30 * 60, queue=settings.CELERY_PERIODIC_QUEUE, max_retries=0)
def queue_async_indicators():
    """
        Fetches AsyncIndicators that
        1. were not queued till now or were last queued more than 4 hours ago
        2. have failed less than ASYNC_INDICATOR_MAX_RETRIES times
        This task quits after it has run for more than
        ASYNC_INDICATOR_QUEUE_TIME - 30 seconds i.e 4 minutes 30 seconds.
        While it runs, it clubs fetched AsyncIndicators by domain and doc type and queue them for processing.
    """
    start = datetime.utcnow()
    cutoff = start + ASYNC_INDICATOR_QUEUE_TIME - timedelta(seconds=30)
    retry_threshold = start - timedelta(hours=4)
    # don't requeue anything that has been retried more than ASYNC_INDICATOR_MAX_RETRIES times
    indicators = AsyncIndicator.objects.filter(unsuccessful_attempts__lt=ASYNC_INDICATOR_MAX_RETRIES)[:settings.ASYNC_INDICATORS_TO_QUEUE]

    indicators_by_domain_doc_type = defaultdict(list)
    # page so that envs can have arbitarily large settings.ASYNC_INDICATORS_TO_QUEUE
    for indicator in paginated_queryset(indicators, 1000):
        # only requeue things that are not in queue or were last queued earlier than the threshold
        if not indicator.date_queued or indicator.date_queued < retry_threshold:
            indicators_by_domain_doc_type[(indicator.domain, indicator.doc_type)].append(indicator)

    for k, indicators in indicators_by_domain_doc_type.items():
        _queue_indicators(indicators)
        if datetime.utcnow() > cutoff:
            break


def _queue_indicators(async_indicators, use_agg_queue=False):
    """
        Extract doc ids for the passed AsyncIndicators and queue task to process indicators for them.
        Mark date_queued on all AsyncIndicator passed to utcnow.
    """
    for chunk in chunked(async_indicators, ASYNC_INDICATOR_CHUNK_SIZE):
        now = datetime.utcnow()
        indicator_doc_ids = [i.doc_id for i in chunk]
        # AsyncIndicator have doc_id as a unique column, so this update would only
        # update the passed AsyncIndicators
        AsyncIndicator.objects.filter(doc_id__in=indicator_doc_ids).update(date_queued=now)
        if use_agg_queue:
            build_indicators_with_agg_queue.delay(indicator_doc_ids)
        else:
            build_async_indicators.delay(indicator_doc_ids)


@task(queue='icds_aggregation_queue', ignore_result=True, acks_late=True)
def build_indicators_with_agg_queue(indicator_doc_ids):
    build_async_indicators(indicator_doc_ids)


@task(serializer='pickle', queue=UCR_INDICATOR_CELERY_QUEUE, ignore_result=True, acks_late=True)
def build_async_indicators(indicator_doc_ids):
    # written to be used with _queue_indicators, indicator_doc_ids must
    #   be a chunk of 100
    memoizers = {'configs': {}, 'adapters': {}}
    assert (len(indicator_doc_ids)) <= ASYNC_INDICATOR_CHUNK_SIZE

    def handle_exception(exception, config_id, doc, adapter):
        metric = None
        if isinstance(exception, (ProtocolError, ReadTimeout)):
            metric = 'commcare.async_indicator.riak_error'
        elif isinstance(exception, (ESError, ConnectionTimeout)):
            # a database had an issue so log it and go on to the next document
            metric = 'commcare.async_indicator.es_error'
        elif isinstance(exception, (DatabaseError, InternalError)):
            # a database had an issue so log it and go on to the next document
            metric = 'commcare.async_indicator.psql_error'
        else:
            # getting the config could fail before the adapter is set
            if adapter:
                adapter.handle_exception(doc, exception)
        if metric:
            metrics_counter(metric, tags={'config_id': config_id})

    def doc_ids_from_rows(rows):
        formatted_rows = [
            {column.column.database_column_name.decode('utf-8'): column.value for column in row}
            for row in rows
        ]
        return set(row['doc_id'] for row in formatted_rows)

    def _get_config(config_id):
        config_by_id = memoizers['configs']
        if config_id in config_by_id:
            return config_by_id[config_id]
        else:
            config = get_ucr_datasource_config_by_id(config_id)
            config_by_id[config_id] = config
            return config

    def _get_adapter(config):
        adapter_by_config = memoizers['adapters']
        if config._id in adapter_by_config:
            return adapter_by_config[config._id]
        else:
            adapter = get_indicator_adapter(config, load_source='build_async_indicators')
            adapter_by_config[config._id] = adapter
            return adapter

    def _metrics_timer(step, config_id=None):
        tags = {
            'action': step,
        }
        if config_id and settings.ENTERPRISE_MODE:
            tags['config_id'] = config_id
        else:
            # Prometheus requires consistent tags even if not available
            tags['config_id'] = None
        return metrics_histogram_timer(
            'commcare.async_indicator.timing',
            timing_buckets=(.03, .1, .3, 1, 3, 10), tags=tags
        )

    # tracks processed/deleted configs to be removed from each indicator
    configs_to_remove_by_indicator_id = defaultdict(list)

    def _mark_config_to_remove(config_id, indicator_ids):
        for _id in indicator_ids:
            configs_to_remove_by_indicator_id[_id].append(config_id)

    timer = TimingContext()
    lock_keys = [
        get_async_indicator_modify_lock_key(indicator_doc_id)
        for indicator_doc_id in indicator_doc_ids
    ]
    with CriticalSection(lock_keys):
        all_indicators = AsyncIndicator.objects.filter(
            doc_id__in=indicator_doc_ids
        )
        if not all_indicators:
            return

        doc_store = get_document_store_for_doc_type(
            all_indicators[0].domain, all_indicators[0].doc_type,
            load_source="build_async_indicators",
        )
        failed_indicators = set()

        rows_to_save_by_adapter = defaultdict(list)
        docs_to_delete_by_adapter = defaultdict(list)
        # there will always be one AsyncIndicator per doc id
        indicator_by_doc_id = {i.doc_id: i for i in all_indicators}
        config_ids = set()
        with timer:
            for doc in doc_store.iter_documents(list(indicator_by_doc_id.keys())):
                indicator = indicator_by_doc_id[doc['_id']]
                eval_context = EvaluationContext(doc)
                for config_id in indicator.indicator_config_ids:
                    with _metrics_timer('transform', config_id):
                        config_ids.add(config_id)
                        try:
                            config = _get_config(config_id)
                        except (ResourceNotFound, DataSourceConfigurationNotFoundError):
                            celery_task_logger.info("{} no longer exists, skipping".format(config_id))
                            # remove because the config no longer exists
                            _mark_config_to_remove(config_id, [indicator.pk])
                            continue
                        except ESError:
                            celery_task_logger.info("ES errored when trying to retrieve config")
                            failed_indicators.add(indicator)
                            continue
                        adapter = None
                        try:
                            adapter = _get_adapter(config)
                            rows_to_save = adapter.get_all_values(doc, eval_context)
                            if rows_to_save:
                                rows_to_save_by_adapter[adapter].extend(rows_to_save)
                            else:
                                docs_to_delete_by_adapter[adapter].append(doc)
                            eval_context.reset_iteration()
                        except Exception as e:
                            failed_indicators.add(indicator)
                            handle_exception(e, config_id, doc, adapter)

            with _metrics_timer('single_batch_update'):
                for adapter, rows in rows_to_save_by_adapter.items():
                    doc_ids = doc_ids_from_rows(rows)
                    indicators = [indicator_by_doc_id[doc_id] for doc_id in doc_ids]
                    try:
                        with _metrics_timer('update', adapter.config._id):
                            adapter.save_rows(rows, use_shard_col=True)
                    except Exception as e:
                        failed_indicators.union(indicators)
                        message = str(e)
                        notify_exception(None, "Exception bulk saving async indicators:{}".format(message))
                    else:
                        # remove because it's successfully processed
                        _mark_config_to_remove(
                            config_id,
                            [i.pk for i in indicators]
                        )

            with _metrics_timer('single_batch_delete'):
                for adapter, docs in docs_to_delete_by_adapter.items():
                    with _metrics_timer('delete', adapter.config._id):
                        adapter.bulk_delete(docs)

        # delete fully processed indicators
        processed_indicators = set(all_indicators) - failed_indicators
        AsyncIndicator.objects.filter(pk__in=[i.pk for i in processed_indicators]).delete()

        # update failure for failed indicators
        with transaction.atomic():
            for indicator in failed_indicators:
                indicator.update_failure(
                    configs_to_remove_by_indicator_id.get(indicator.pk, [])
                )
                indicator.save()

        metrics_counter('commcare.async_indicator.processed_success', len(processed_indicators))
        metrics_counter('commcare.async_indicator.processed_fail', len(failed_indicators))
        metrics_counter(
            'commcare.async_indicator.processing_time', timer.duration,
            tags={'config_ids': config_ids}
        )
        metrics_counter(
            'commcare.async_indicator.processed_total', len(indicator_doc_ids),
            tags={'config_ids': config_ids}
        )


@periodic_task(run_every=crontab(minute="*/5"), queue=settings.CELERY_PERIODIC_QUEUE)
def async_indicators_metrics():
    now = datetime.utcnow()
    oldest_indicator = AsyncIndicator.objects.order_by('date_queued').first()
    if oldest_indicator and oldest_indicator.date_queued:
        lag = (now - oldest_indicator.date_queued).total_seconds()
        metrics_gauge('commcare.async_indicator.oldest_queued_indicator', lag,
            multiprocess_mode=MPM_MIN)

    oldest_100_indicators = AsyncIndicator.objects.all()[:100]
    if oldest_100_indicators.exists():
        oldest_indicator = oldest_100_indicators[0]
        lag = (now - oldest_indicator.date_created).total_seconds()
        metrics_gauge('commcare.async_indicator.oldest_created_indicator', lag,
            multiprocess_mode=MPM_MIN)

        lags = [
            (now - indicator.date_created).total_seconds()
            for indicator in oldest_100_indicators
        ]
        avg_lag = sum(lags) / len(lags)
        metrics_gauge('commcare.async_indicator.oldest_created_indicator_avg', avg_lag,
            multiprocess_mode=MPM_MAX)

    for config_id, metrics in _indicator_metrics().items():
        tags = {"config_id": config_id}
        metrics_gauge('commcare.async_indicator.indicator_count', metrics['count'], tags=tags,
            multiprocess_mode=MPM_MAX)
        metrics_gauge('commcare.async_indicator.lag', metrics['lag'], tags=tags,
            documentation="Lag of oldest created indicator including failed indicators",
            multiprocess_mode=MPM_MAX)

    # Don't use ORM summing because it would attempt to get every value in DB
    unsuccessful_attempts = sum(AsyncIndicator.objects.values_list('unsuccessful_attempts', flat=True).all()[:100])
    metrics_gauge('commcare.async_indicator.unsuccessful_attempts', unsuccessful_attempts,
                  multiprocess_mode='livesum')

    oldest_unprocessed = AsyncIndicator.objects.filter(unsuccessful_attempts=0).first()
    if oldest_unprocessed:
        lag = (now - oldest_unprocessed.date_created).total_seconds()
    else:
        lag = 0
    metrics_gauge(
        'commcare.async_indicator.true_lag',
        lag,
        documentation="Lag of oldest created indicator that didn't get ever queued",
        multiprocess_mode=MPM_MAX
    )
    metrics_gauge(
        'commcare.async_indicator.fully_failed_count',
        AsyncIndicator.objects.filter(unsuccessful_attempts=ASYNC_INDICATOR_MAX_RETRIES).count(),
        documentation="Number of indicators that failed max-retry number of times",
        multiprocess_mode=MPM_LIVESUM
    )


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
        .order_by()  # needed to get rid of implicit ordering by date_created
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


@task(serializer='pickle')
def export_ucr_async(report_export, download_id, user):
    use_transfer = settings.SHARED_DRIVE_CONF.transfer_enabled
    ascii_title = report_export.title.encode('ascii', 'replace').decode('utf-8')
    filename = '{}.xlsx'.format(ascii_title.replace('/', '?'))
    file_path = get_download_file_path(use_transfer, filename)

    report_export.create_export(file_path, Format.XLS_2007)
    expose_download(use_transfer, file_path, filename, download_id, 'xlsx', owner_ids=[user.get_id])
    link = reverse("retrieve_download", args=[download_id], params={"get_file": '1'}, absolute=True)

    send_report_download_email(report_export.title, user.get_email(), link, domain=report_export.domain)
