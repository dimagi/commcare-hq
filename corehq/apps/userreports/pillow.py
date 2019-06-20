from __future__ import absolute_import, division, unicode_literals

import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from django.conf import settings

import six

from pillowtop.checkpoints.manager import KafkaPillowCheckpoint
from pillowtop.const import DEFAULT_PROCESSOR_CHUNK_SIZE
from pillowtop.dao.exceptions import DocumentMismatchError
from pillowtop.exceptions import PillowConfigError
from pillowtop.logger import pillow_logging
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import BulkPillowProcessor
from pillowtop.utils import ensure_document_exists, ensure_matched_revisions

from corehq.apps.change_feed.consumer.feed import (
    KafkaChangeFeed,
    KafkaCheckpointEventHandler,
)
from corehq.apps.change_feed.topics import LOCATION as LOCATION_TOPIC
from corehq.apps.domain.dbaccessors import get_domain_ids_by_names
from corehq.apps.userreports.const import KAFKA_TOPICS
from corehq.apps.userreports.data_source_providers import (
    DynamicDataSourceProvider,
    StaticDataSourceProvider,
)
from corehq.apps.userreports.exceptions import (
    BadSpecError,
    StaleRebuildError,
    TableRebuildError,
    UserReportsWarning,
)
from corehq.apps.userreports.models import AsyncIndicator
from corehq.apps.userreports.rebuild import (
    get_table_diffs,
    get_tables_rebuild_migrate,
    migrate_tables,
)
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.userreports.sql import get_metadata
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.sql_db.connections import connection_manager
from corehq.util.datadog.gauges import datadog_bucket_timer, datadog_histogram
from corehq.util.soft_assert import soft_assert
from corehq.util.timer import TimingContext

REBUILD_CHECK_INTERVAL = 60 * 60  # in seconds
LONG_UCR_LOGGING_THRESHOLD = 0.5


def time_ucr_process_change(method):
    def timed(*args, **kw):
        ts = datetime.now()
        result = method(*args, **kw)
        te = datetime.now()
        seconds = (te - ts).total_seconds()
        if seconds > LONG_UCR_LOGGING_THRESHOLD:
            table = args[2]
            doc = args[3]
            log_message = "UCR data source {} on doc_id {} took {} seconds to process".format(
                table.config._id, doc['_id'], seconds
            )
            pillow_logging.warning(log_message)
        return result
    return timed


def _filter_by_hash(configs, ucr_division):
    ucr_start = ucr_division[0]
    ucr_end = ucr_division[-1]
    filtered_configs = []
    for config in configs:
        table_hash = hashlib.md5(config.table_id.encode('utf-8')).hexdigest()[0]
        if ucr_start <= table_hash <= ucr_end:
            filtered_configs.append(config)
    return filtered_configs


def _filter_missing_domains(configs):
    """Return a list of configs whose domain exists on this environment"""
    domain_names = [config.domain for config in configs if config.is_static]
    existing_domains = list(get_domain_ids_by_names(domain_names))
    return [
        config for config in configs
        if not config.is_static or config.domain in existing_domains
    ]


class ConfigurableReportTableManagerMixin(object):

    def __init__(self, data_source_providers, ucr_division=None,
                 include_ucrs=None, exclude_ucrs=None, bootstrap_interval=REBUILD_CHECK_INTERVAL,
                 run_migrations=True):
        """Initializes the processor for UCRs

        Keyword Arguments:
        ucr_division -- two hexadecimal digits that are used to determine a subset of UCR
                        datasources to process. The second digit should be higher than the
                        first
        include_ucrs -- list of ucr 'table_ids' to be included in this processor
        exclude_ucrs -- list of ucr 'table_ids' to be excluded in this processor
        bootstrap_interval -- time in seconds when the pillow checks for any data source changes
        run_migrations -- If True, rebuild tables if the data source changes.
                          Otherwise, do not attempt to change database
        """
        self.bootstrapped = False
        self.last_bootstrapped = datetime.utcnow()
        self.data_source_providers = data_source_providers
        self.ucr_division = ucr_division
        self.include_ucrs = include_ucrs
        self.exclude_ucrs = exclude_ucrs
        self.bootstrap_interval = bootstrap_interval
        self.run_migrations = run_migrations
        if self.include_ucrs and self.ucr_division:
            raise PillowConfigError("You can't have include_ucrs and ucr_division")

    def get_all_configs(self):
        return [
            source
            for provider in self.data_source_providers
            for source in provider.get_data_sources()
        ]

    def get_filtered_configs(self, configs=None):
        configs = configs or self.get_all_configs()

        if self.exclude_ucrs:
            configs = [config for config in configs if config.table_id not in self.exclude_ucrs]

        if self.include_ucrs:
            configs = [config for config in configs if config.table_id in self.include_ucrs]
        elif self.ucr_division:
            configs = _filter_by_hash(configs, self.ucr_division)

        configs = _filter_missing_domains(configs)

        return configs

    def needs_bootstrap(self):
        return (
            not self.bootstrapped
            or datetime.utcnow() - self.last_bootstrapped > timedelta(seconds=self.bootstrap_interval)
        )

    def bootstrap_if_needed(self):
        if self.needs_bootstrap():
            self.bootstrap()

    def bootstrap(self, configs=None):
        configs = self.get_filtered_configs(configs)
        if not configs:
            pillow_logging.warning("UCR pillow has no configs to process")

        self.table_adapters_by_domain = defaultdict(list)

        for config in configs:
            self.table_adapters_by_domain[config.domain].append(
                get_indicator_adapter(config, raise_errors=True, load_source='change_feed')
            )

        if self.run_migrations:
            self.rebuild_tables_if_necessary()

        self.bootstrapped = True
        self.last_bootstrapped = datetime.utcnow()

    def rebuild_tables_if_necessary(self):
        self._rebuild_sql_tables([
            adapter
            for adapter_list in self.table_adapters_by_domain.values()
            for adapter in adapter_list
        ])

    def _rebuild_sql_tables(self, adapters):
        tables_by_engine = defaultdict(dict)
        all_adapters = []
        for adapter in adapters:
            if getattr(adapter, 'all_adapters', None):
                all_adapters.extend(adapter.all_adapters)
            else:
                all_adapters.append(adapter)
        for adapter in all_adapters:
            try:
                tables_by_engine[adapter.engine_id][adapter.get_table().name] = adapter
            except BadSpecError:
                _soft_assert = soft_assert(to='{}@{}'.format('jemord', 'dimagi.com'))
                _soft_assert(False, "Broken data source {}".format(adapter.config.get_id))

        _assert = soft_assert(notify_admins=True)
        _notify_rebuild = lambda msg, obj: _assert(False, msg, obj)

        for engine_id, table_map in tables_by_engine.items():
            table_names = list(table_map)
            engine = connection_manager.get_engine(engine_id)

            diffs = get_table_diffs(engine, table_names, get_metadata(engine_id))

            tables_to_act_on = get_tables_rebuild_migrate(diffs)
            for table_name in tables_to_act_on.rebuild:
                pillow_logging.debug("[rebuild] Rebuilding table: %s", table_name)
                sql_adapter = table_map[table_name]
                table_diffs = [diff for diff in diffs if diff.table_name == table_name]
                if not sql_adapter.config.is_static:
                    try:
                        self.rebuild_table(sql_adapter, table_diffs)
                    except TableRebuildError as e:
                        _notify_rebuild(six.text_type(e), sql_adapter.config.to_json())
                else:
                    self.rebuild_table(sql_adapter, table_diffs)

            self.migrate_tables(engine, diffs, tables_to_act_on.migrate, table_map)

    def migrate_tables(self, engine, diffs, table_names, adapters_by_table):
        pillow_logging.debug("[rebuild] Application migrations to tables: %s", table_names)
        migration_diffs = [diff for diff in diffs if diff.table_name in table_names]
        changes = migrate_tables(engine, migration_diffs)
        for table, diffs in changes.items():
            adapter = adapters_by_table[table]
            adapter.log_table_migrate(source='pillowtop', diffs=diffs)

    def rebuild_table(self, adapter, diffs=None):
        config = adapter.config
        if not config.is_static:
            latest_rev = config.get_db().get_rev(config._id)
            if config._rev != latest_rev:
                raise StaleRebuildError('Tried to rebuild a stale table ({})! Ignoring...'.format(config))

        if config.disable_destructive_rebuild and adapter.table_exists:
            diff_dicts = [diff.to_dict() for diff in diffs]
            adapter.log_table_rebuild_skipped(source='pillowtop', diffs=diff_dicts)
            return

        if config.is_static:
            rebuild_indicators.delay(adapter.config.get_id, source='pillowtop', engine_id=adapter.engine_id)
        else:
            adapter.rebuild_table(source='pillowtop')


class ConfigurableReportPillowProcessor(ConfigurableReportTableManagerMixin, BulkPillowProcessor):

    domain_timing_context = Counter()

    @time_ucr_process_change
    def _save_doc_to_table(self, domain, table, doc, eval_context):
        # best effort will swallow errors in the table
        try:
            table.best_effort_save(doc, eval_context)
        except UserReportsWarning:
            # remove it until the next bootstrap call
            self.table_adapters_by_domain[domain].remove(table)

    def process_changes_chunk(self, changes):
        """
        Update UCR tables in bulk by breaking up changes per domain per UCR table.
            If an exception is raised in bulk operations of a set of changes,
            those changes are returned to pillow for serial reprocessing.
        """
        self.bootstrap_if_needed()
        # break up changes by domain
        changes_by_domain = defaultdict(list)
        for change in changes:
            # skip if no domain or no UCR tables in the domain
            if change.metadata.domain and change.metadata.domain in self.table_adapters_by_domain:
                changes_by_domain[change.metadata.domain].append(change)

        retry_changes = set()
        change_exceptions = []
        for domain, changes_chunk in six.iteritems(changes_by_domain):
            failed, exceptions = self._process_chunk_for_domain(domain, changes_chunk)
            retry_changes.update(failed)
            change_exceptions.extend(exceptions)

        return retry_changes, change_exceptions

    def _process_chunk_for_domain(self, domain, changes_chunk):
        adapters = list(self.table_adapters_by_domain[domain])
        changes_by_id = {change.id: change for change in changes_chunk}
        to_delete_by_adapter = defaultdict(list)
        rows_to_save_by_adapter = defaultdict(list)
        async_configs_by_doc_id = defaultdict(list)
        to_update = {change for change in changes_chunk if not change.deleted}
        with self._datadog_timing('extract'):
            retry_changes, docs = self.get_docs_for_changes(to_update, domain)
        change_exceptions = []

        with self._datadog_timing('single_batch_transform'):
            for doc in docs:
                change = changes_by_id[doc['_id']]
                eval_context = EvaluationContext(doc)
                with self._datadog_timing('single_doc_transform'):
                    for adapter in adapters:
                        with self._datadog_timing('transform', adapter.config._id):
                            if adapter.config.filter(doc, eval_context):
                                if adapter.run_asynchronous:
                                    async_configs_by_doc_id[doc['_id']].append(adapter.config._id)
                                else:
                                    try:
                                        rows_to_save_by_adapter[adapter].extend(adapter.get_all_values(doc, eval_context))
                                    except Exception as e:
                                        change_exceptions.append((change, e))
                                    eval_context.reset_iteration()
                            elif (change.document_subtype is None
                                    or change.document_subtype in adapter.get_case_type_or_xmlns_filter()):
                                # Delete if the subtype is unknown or if it does not exist in our filters
                                to_delete_by_adapter[adapter].append(doc['_id'])

        with self._datadog_timing('single_batch_delete'):
            # bulk delete by adapter
            to_delete = [c.id for c in changes_chunk if c.deleted]
            for adapter in adapters:
                delete_ids = to_delete_by_adapter[adapter] + to_delete
                if not delete_ids:
                    continue
                with self._datadog_timing('delete', adapter.config._id):
                    try:
                        adapter.bulk_delete(delete_ids)
                    except Exception:
                        retry_changes.update([c for c in changes_chunk if c.id in delete_ids])

        with self._datadog_timing('single_batch_load'):
            # bulk update by adapter
            for adapter, rows in six.iteritems(rows_to_save_by_adapter):
                with self._datadog_timing('load', adapter.config._id):
                    try:
                        adapter.save_rows(rows)
                    except Exception:
                        retry_changes.update(to_update)

        if async_configs_by_doc_id:
            with self._datadog_timing('async_config_load'):
                doc_type_by_id = {
                    _id: changes_by_id[_id].metadata.document_type
                    for _id in async_configs_by_doc_id.keys()
                }
                AsyncIndicator.bulk_update_records(async_configs_by_doc_id, domain, doc_type_by_id)

        return retry_changes, change_exceptions

    def _datadog_timing(self, step, config_id=None):
        tags = [
            'action:{}'.format(step),
            'index:ucr',
        ]
        if config_id and settings.ENTERPRISE_MODE:
            tags.append('config_id:{}'.format(config_id))
        return datadog_bucket_timer(
            'commcare.change_feed.processor.timing',
            tags=tags, timing_buckets=(.03, .1, .3, 1, 3, 10)
        )

    @staticmethod
    def get_docs_for_changes(changes, domain):
        # break up by doctype
        changes_by_doctype = defaultdict(list)
        for change in changes:
            assert change.metadata.domain == domain
            changes_by_doctype[change.metadata.data_source_name].append(change)

        # query
        docs = []
        for _, _changes in six.iteritems(changes_by_doctype):
            doc_store = _changes[0].document_store
            doc_ids_to_query = [change.id for change in _changes if change.should_fetch_document()]
            new_docs = list(doc_store.iter_documents(doc_ids_to_query))
            docs_queried_prior = [change.document for change in _changes if not change.should_fetch_document()]
            docs.extend(new_docs + docs_queried_prior)

        # catch missing docs
        retry_changes = set()
        docs_by_id = {doc['_id']: doc for doc in docs}
        for change in changes:
            if change.id not in docs_by_id:
                # we need to capture DocumentMissingError which is not possible in bulk
                #   so let pillow fall back to serial mode to capture the error for missing docs
                retry_changes.add(change)
                continue
            else:
                # set this, so that subsequent doc lookups are avoided
                change.set_document(docs_by_id[change.id])
            try:
                ensure_matched_revisions(change, docs_by_id.get(change.id))
            except DocumentMismatchError:
                retry_changes.add(change)
        return retry_changes, docs

    def process_change(self, change):
        self.bootstrap_if_needed()

        domain = change.metadata.domain
        if not domain or domain not in self.table_adapters_by_domain:
            # if no domain we won't save to any UCR table
            return

        if change.deleted:
            adapters = list(self.table_adapters_by_domain[domain])
            for table in adapters:
                table.delete({'_id': change.metadata.document_id})

        async_tables = []
        doc = change.get_document()
        ensure_document_exists(change)
        ensure_matched_revisions(change, doc)

        if doc is None:
            return

        with TimingContext() as timer:
            eval_context = EvaluationContext(doc)
            # make copy to avoid modifying list during iteration
            adapters = list(self.table_adapters_by_domain[domain])
            for table in adapters:
                if table.config.filter(doc, eval_context):
                    if table.run_asynchronous:
                        async_tables.append(table.config._id)
                    else:
                        self._save_doc_to_table(domain, table, doc, eval_context)
                        eval_context.reset_iteration()
                elif table.config.deleted_filter(doc) or table.doc_exists(doc):
                    table.delete(doc)

            if async_tables:
                AsyncIndicator.update_from_kafka_change(change, async_tables)

        self.domain_timing_context.update(**{
            domain: timer.duration
        })

    def checkpoint_updated(self):
        total_duration = sum(self.domain_timing_context.values())
        duration_seen = 0
        top_half_domains = {}
        for domain, duration in self.domain_timing_context.most_common():
            top_half_domains[domain] = duration
            duration_seen += duration
            if duration_seen >= total_duration // 2:
                break

        for domain, duration in top_half_domains.items():
            datadog_histogram('commcare.change_feed.ucr_slow_log', duration, tags=[
                'domain:{}'.format(domain)
            ])
        self.domain_timing_context.clear()


class ConfigurableReportKafkaPillow(ConstructedPillow):
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/

    def __init__(self, processor, pillow_name, topics, num_processes, process_num, retry_errors=False,
            processor_chunk_size=0):
        change_feed = KafkaChangeFeed(
            topics, client_id=pillow_name, num_processes=num_processes, process_num=process_num
        )
        checkpoint = KafkaPillowCheckpoint(pillow_name, topics)
        event_handler = KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=1000, change_feed=change_feed,
            checkpoint_callback=processor
        )
        super(ConfigurableReportKafkaPillow, self).__init__(
            name=pillow_name,
            change_feed=change_feed,
            processor=processor,
            checkpoint=checkpoint,
            change_processed_event_handler=event_handler,
            processor_chunk_size=processor_chunk_size
        )
        # set by the superclass constructor
        assert self.processors is not None
        assert len(self.processors) == 1
        self._processor = self.processors[0]
        assert self._processor.bootstrapped is not None

        # retry errors defaults to False because there is not a solution to
        # distinguish between doc save errors and data source config errors
        self.retry_errors = retry_errors

    def bootstrap(self, configs=None):
        self._processor.bootstrap(configs)

    def rebuild_table(self, sql_adapter):
        self._processor.rebuild_table(sql_adapter)


def get_kafka_ucr_pillow(pillow_id='kafka-ucr-main', ucr_division=None,
                         include_ucrs=None, exclude_ucrs=None, topics=None,
                         num_processes=1, process_num=0,
                         processor_chunk_size=DEFAULT_PROCESSOR_CHUNK_SIZE, **kwargs):
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    topics = topics or KAFKA_TOPICS
    topics = [t for t in topics]
    return ConfigurableReportKafkaPillow(
        processor=ConfigurableReportPillowProcessor(
            data_source_providers=[DynamicDataSourceProvider()],
            ucr_division=ucr_division,
            include_ucrs=include_ucrs,
            exclude_ucrs=exclude_ucrs,
            run_migrations=(process_num == 0)  # only first process runs migrations
        ),
        pillow_name=pillow_id,
        topics=topics,
        num_processes=num_processes,
        process_num=process_num,
        processor_chunk_size=processor_chunk_size,
    )


def get_kafka_ucr_static_pillow(pillow_id='kafka-ucr-static', ucr_division=None,
                                include_ucrs=None, exclude_ucrs=None, topics=None,
                                num_processes=1, process_num=0,
                                processor_chunk_size=DEFAULT_PROCESSOR_CHUNK_SIZE, **kwargs):
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    topics = topics or KAFKA_TOPICS
    topics = [t for t in topics]
    return ConfigurableReportKafkaPillow(
        processor=ConfigurableReportPillowProcessor(
            data_source_providers=[StaticDataSourceProvider()],
            ucr_division=ucr_division,
            include_ucrs=include_ucrs,
            exclude_ucrs=exclude_ucrs,
            bootstrap_interval=7 * 24 * 60 * 60,  # 1 week
            run_migrations=(process_num == 0)  # only first process runs migrations
        ),
        pillow_name=pillow_id,
        topics=topics,
        num_processes=num_processes,
        process_num=process_num,
        retry_errors=True,
        processor_chunk_size=processor_chunk_size,
    )


def get_location_pillow(pillow_id='location-ucr-pillow', include_ucrs=None,
                        num_processes=1, process_num=0, ucr_configs=None, **kwargs):
    # Todo; is ucr_division needed?
    change_feed = KafkaChangeFeed(
        [LOCATION_TOPIC], client_id=pillow_id, num_processes=num_processes, process_num=process_num
    )
    ucr_processor = ConfigurableReportPillowProcessor(
        data_source_providers=[DynamicDataSourceProvider('Location'), StaticDataSourceProvider('Location')],
        include_ucrs=include_ucrs,
    )
    if ucr_configs:
        ucr_processor.bootstrap(ucr_configs)
    checkpoint = KafkaPillowCheckpoint(pillow_id, [LOCATION_TOPIC])
    event_handler = KafkaCheckpointEventHandler(
        checkpoint=checkpoint, checkpoint_frequency=1000, change_feed=change_feed,
        checkpoint_callback=ucr_processor
    )
    return ConstructedPillow(
        name=pillow_id,
        change_feed=change_feed,
        checkpoint=checkpoint,
        change_processed_event_handler=event_handler,
        processor=[ucr_processor]
    )
