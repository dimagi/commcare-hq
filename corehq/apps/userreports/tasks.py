from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from collections import defaultdict
from datetime import datetime, timedelta
import logging
import time

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
    get_report_config)
from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
from corehq.apps.userreports.util import get_indicator_adapter, get_async_indicator_modify_lock_key
from corehq.elastic import ESError
from corehq.util.context_managers import notify_someone
from corehq.util.datadog.gauges import datadog_gauge, datadog_histogram, datadog_counter
from corehq.util.decorators import serial_task
from corehq.util.quickcache import quickcache
from corehq.util.timer import TimingContext
from corehq.util.view_utils import reverse
from dimagi.utils.chunked import chunked
from dimagi.utils.couch import CriticalSection
from dimagi.utils.logging import notify_exception
from pillowtop.dao.couch import ID_CHUNK_SIZE
import six

celery_task_logger = logging.getLogger('celery.task')


def _get_config_by_id(indicator_config_id):
    if id_is_static(indicator_config_id):
        return StaticDataSourceConfiguration.by_id(indicator_config_id)
    else:
        return DataSourceConfiguration.get(indicator_config_id)


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


@task(serializer='pickle', queue=UCR_CELERY_QUEUE, ignore_result=True)
def rebuild_indicators(indicator_config_id, initiated_by=None, limit=-1, source=None, engine_id=None):
    config = _get_config_by_id(indicator_config_id)
    success = _('Your UCR table {} has finished rebuilding in {}').format(config.table_id, config.domain)
    failure = _('There was an error rebuilding Your UCR table {} in {}.').format(config.table_id, config.domain)
    send = False
    if limit == -1:
        send = toggles.SEND_UCR_REBUILD_INFO.enabled(initiated_by)
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
        adapter.rebuild_table(initiated_by=initiated_by, source=source, skip_log=skip_log)
        _iteratively_build_table(config, limit=limit)


@task(serializer='pickle', queue=UCR_CELERY_QUEUE, ignore_result=True)
def rebuild_indicators_in_place(indicator_config_id, initiated_by=None, source=None):
    config = _get_config_by_id(indicator_config_id)
    success = _('Your UCR table {} has finished rebuilding in {}').format(config.table_id, config.domain)
    failure = _('There was an error rebuilding Your UCR table {} in {}.').format(config.table_id, config.domain)
    send = toggles.SEND_UCR_REBUILD_INFO.enabled(initiated_by)
    with notify_someone(initiated_by, success_message=success, error_message=failure, send=send):
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
    config = _get_config_by_id(indicator_config_id)
    success = _('Your UCR table {} has finished rebuilding in {}').format(config.table_id, config.domain)
    failure = _('There was an error rebuilding Your UCR table {} in {}.').format(config.table_id, config.domain)
    send = toggles.SEND_UCR_REBUILD_INFO.enabled(initiated_by)
    with notify_someone(initiated_by, success_message=success, error_message=failure, send=send):
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
            config.domain, config.referenced_doc_type,
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


@task(serializer='pickle', queue=UCR_CELERY_QUEUE)
def compare_ucr_dbs(domain, report_config_id, filter_values, sort_column=None, sort_order=None, params=None):
    if report_config_id not in settings.UCR_COMPARISONS:
        return

    control_report, unused = get_report_config(report_config_id, domain)
    candidate_report = None

    new_report_config_id = settings.UCR_COMPARISONS.get(report_config_id)
    if new_report_config_id is not None:
        # a report is configured to be compared against
        candidate_report, unused = get_report_config(new_report_config_id, domain)
        _compare_ucr_reports(
            domain, control_report, candidate_report, filter_values, sort_column, sort_order, params)
    else:
        # no report is configured. Assume we should try mirrored engine_ids
        # report_config.config is a DataSourceConfiguration
        for engine_id in control_report.config.mirrored_engine_ids:
            _compare_ucr_reports(
                domain, control_report, control_report, filter_values, sort_column,
                sort_order, params, candidate_engine_id=engine_id)


def _compare_ucr_reports(domain, control_report, candidate_report, filter_values, sort_column, sort_order, params,
                         candidate_engine_id=None):
    from corehq.apps.userreports.laboratory.experiment import UCRExperiment

    def _run_report(spec, engine_id=None):
        data_source = ConfigurableReportDataSource.from_spec(spec, include_prefilters=True)
        if engine_id:
            data_source.data_source.override_engine_id(engine_id)
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

    experiment_context = {
        "domain": domain,
        "report_config_id": control_report._id,
        "new_report_config_id": candidate_report._id,
        "filter_values": filter_values,
    }
    experiment = UCRExperiment(name="UCR DB Experiment", context=experiment_context)
    with experiment.control() as c:
        c.record(_run_report(control_report))

    with experiment.candidate() as c:
        c.record(_run_report(candidate_report, candidate_engine_id))

    objects = experiment.run()
    return objects


@task(serializer='pickle', queue=UCR_CELERY_QUEUE, ignore_result=True)
def delete_data_source_task(domain, config_id):
    from corehq.apps.userreports.views import delete_data_source_shared
    delete_data_source_shared(domain, config_id)


@periodic_task(run_every=crontab(minute='*/5'), queue=settings.CELERY_PERIODIC_QUEUE)
def reprocess_archive_stubs():
    # Check for archive stubs
    from corehq.form_processor.interfaces.dbaccessors import FormAccessors
    from couchforms.models import UnfinishedArchiveStub
    stubs = UnfinishedArchiveStub.objects.filter()
    datadog_gauge('commcare.unfinished_archive_stubs', len(stubs))
    start = time.time()
    cutoff = start + timedelta(minutes=4).total_seconds()
    for stub in stubs:
        # Exit this task after 4 minutes so that the same stub isn't ever processed in multiple queues.
        if time.time() - start > cutoff:
            return
        xform = FormAccessors(stub.domain).get_form(form_id=stub.xform_id)
        # If the history wasn't updated the first time around, run the whole thing again.
        if not stub.history_updated:
            if stub.archive:
                xform.archive(user_id=stub.user_id)
            else:
                xform.unarchive(user_id=stub.user_id)
        # If the history was updated the first time around, just send the update to kafka
        else:
            xform.publish_archive_action_to_kafka(user_id=stub.user_id, archive=stub.archive)


@periodic_task(run_every=crontab(minute='*/5'), queue=settings.CELERY_PERIODIC_QUEUE)
def run_queue_async_indicators_task():
    if time_in_range(datetime.utcnow(), settings.ASYNC_INDICATOR_QUEUE_TIMES):
        queue_async_indicators.delay()


@serial_task('queue-async-indicators', timeout=30 * 60, queue=settings.CELERY_PERIODIC_QUEUE, max_retries=0)
def queue_async_indicators():
    start = datetime.utcnow()
    cutoff = start + ASYNC_INDICATOR_QUEUE_TIME - timedelta(seconds=30)
    retry_threshold = start - timedelta(hours=4)
    # don't requeue anything that has been retried more than 20 times
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
        build_async_indicators.delay(indicator_doc_ids)
        datadog_counter('commcare.async_indicator.indicators_queued', len(indicator_doc_ids))

    to_queue = []
    for indicator in indicators:
        to_queue.append(indicator)
        if len(to_queue) >= ASYNC_INDICATOR_CHUNK_SIZE:
            _queue_chunk(to_queue)
            to_queue = []

    if to_queue:
        _queue_chunk(to_queue)


@task(serializer='pickle', queue=UCR_INDICATOR_CELERY_QUEUE, ignore_result=True, acks_late=True)
def build_async_indicators(indicator_doc_ids):
    # written to be used with _queue_indicators, indicator_doc_ids must
    #   be a chunk of 100
    for ids in chunked(indicator_doc_ids, 10):
        _build_async_indicators(ids)


def _build_async_indicators(indicator_doc_ids):
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
            datadog_counter(metric, 1,
                tags={'config_id': config_id, 'doc_id': doc['_id']})

    def doc_ids_from_rows(rows):
        formatted_rows = [
            {column.column.database_column_name.decode('utf-8'): column.value for column in row}
            for row in rows
        ]
        return set(row['doc_id'] for row in formatted_rows)

    # tracks processed/deleted configs to be removed from each indicator
    configs_to_remove_by_indicator_id = defaultdict(list)

    def _mark_config_to_remove(config_id, indicator_ids):
        for _id in indicator_ids:
            configs_to_remove_by_indicator_id[_id].append(config_id)

    timer = TimingContext()
    lock_keys = [
        get_async_indicator_modify_lock_key(indicator_id)
        for indicator_id in indicator_doc_ids
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
        indicator_by_doc_id = {i.doc_id: i for i in all_indicators}
        config_ids = set()
        with timer:
            for doc in doc_store.iter_documents(list(indicator_by_doc_id.keys())):
                indicator = indicator_by_doc_id[doc['_id']]
                eval_context = EvaluationContext(doc)
                for config_id in indicator.indicator_config_ids:
                    config_ids.add(config_id)
                    try:
                        config = _get_config_by_id(config_id)
                    except (ResourceNotFound, StaticDataSourceConfigurationNotFoundError):
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
                        adapter = get_indicator_adapter(config, load_source='build_async_indicators')
                        rows_to_save_by_adapter[adapter].extend(adapter.get_all_values(doc, eval_context))
                        eval_context.reset_iteration()
                    except Exception as e:
                        failed_indicators.add(indicator)
                        handle_exception(e, config_id, doc, adapter)

            for adapter, rows in six.iteritems(rows_to_save_by_adapter):
                doc_ids = doc_ids_from_rows(rows)
                indicators = [indicator_by_doc_id[doc_id] for doc_id in doc_ids]
                try:
                    adapter.save_rows(rows)
                except Exception as e:
                    failed_indicators.union(indicators)
                    message = six.text_type(e)
                    notify_exception(None,
                        "Exception bulk saving async indicators:{}".format(message))
                else:
                    # remove because it's sucessfully processed
                    _mark_config_to_remove(
                        config_id,
                        [i.pk for i in indicators]
                    )

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

        datadog_counter('commcare.async_indicator.processed_success', len(processed_indicators))
        datadog_counter('commcare.async_indicator.processed_fail', len(failed_indicators))
        datadog_histogram(
            'commcare.async_indicator.processing_time', timer.duration / len(indicator_doc_ids),
            tags=[
                'config_ids:{}'.format(config_ids),
            ]
        )


@periodic_task(run_every=crontab(minute="*/5"), queue=settings.CELERY_PERIODIC_QUEUE)
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


@task(serializer='pickle')
def export_ucr_async(report_export, download_id, user):
    use_transfer = settings.SHARED_DRIVE_CONF.transfer_enabled
    ascii_title = report_export.title.encode('ascii', 'replace').decode('utf-8')
    filename = '{}.xlsx'.format(ascii_title.replace('/', '?'))
    file_path = get_download_file_path(use_transfer, filename)

    report_export.create_export(file_path, Format.XLS_2007)

    expose_download(use_transfer, file_path, filename, download_id, 'xlsx')
    link = reverse("retrieve_download", args=[download_id], params={"get_file": '1'}, absolute=True)

    send_report_download_email(report_export.title, user.get_email(), link)
