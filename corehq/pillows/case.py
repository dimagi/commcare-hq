import logging

from django.conf import settings

from pillowtop.checkpoints.manager import (
    KafkaPillowCheckpoint,
    get_checkpoint_for_elasticsearch_pillow,
)
from pillowtop.const import DEFAULT_PROCESSOR_CHUNK_SIZE
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import BulkElasticProcessor, ElasticProcessor
from pillowtop.reindexer.reindexer import (
    ReindexerFactory,
    ResumableBulkElasticPillowReindexer,
)

from corehq.apps.change_feed.consumer.feed import (
    KafkaChangeFeed,
    KafkaCheckpointEventHandler,
)
from corehq.apps.change_feed.topics import CASE_TOPICS
from corehq.apps.es.cases import case_adapter
from corehq.apps.userreports.data_source_providers import (
    DynamicDataSourceProvider,
    StaticDataSourceProvider,
)
from corehq.apps.userreports.pillow import (
    get_data_registry_ucr_processor,
    get_ucr_processor,
)
from corehq.form_processor.backends.sql.dbaccessors import CaseReindexAccessor
from corehq.apps.data_interfaces.pillow import CaseDeduplicationProcessor
from corehq.messaging.pillow import CaseMessagingSyncProcessor
from corehq.pillows.base import is_couch_change_for_sql_domain
from corehq.pillows.case_search import get_case_search_processor
from corehq.util.doc_processor.sql import SqlDocumentProvider

pillow_logging = logging.getLogger("pillowtop")
pillow_logging.setLevel(logging.INFO)


def get_case_to_elasticsearch_pillow(pillow_id='CaseToElasticsearchPillow', num_processes=1,
                                     process_num=0, **kwargs):
    """Return a pillow that processes cases to Elasticsearch.

    Processors:
      - :py:class:`pillowtop.processors.elastic.ElasticProcessor`
    """
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    assert pillow_id == 'CaseToElasticsearchPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, case_adapter.index_name, CASE_TOPICS)
    case_processor = ElasticProcessor(
        case_adapter,
        change_filter_fn=is_couch_change_for_sql_domain
    )
    kafka_change_feed = KafkaChangeFeed(
        topics=CASE_TOPICS, client_id='cases-to-es', num_processes=num_processes, process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=kafka_change_feed,
        processor=case_processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=kafka_change_feed
        ),
    )


def get_case_pillow(
        pillow_id='case-pillow', ucr_division=None,
        include_ucrs=None, exclude_ucrs=None,
        num_processes=1, process_num=0, ucr_configs=None, skip_ucr=False,
        processor_chunk_size=DEFAULT_PROCESSOR_CHUNK_SIZE, topics=None,
        dedicated_migration_process=False, **kwargs):
    """Return a pillow that processes cases. The processors include, UCR and elastic processors

    Processors:
      - :py:class:`corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor` (disabled when skip_ucr=True)
      - :py:class:`pillowtop.processors.elastic.BulkElasticProcessor`
      - :py:func:`corehq.pillows.case_search.get_case_search_processor`
      - :py:class:`corehq.messaging.pillow.CaseMessagingSyncProcessor`
    """
    if topics:
        assert set(topics).issubset(CASE_TOPICS), "This is a pillow to process cases only"
    topics = topics or CASE_TOPICS
    change_feed = KafkaChangeFeed(
        topics, client_id=pillow_id, num_processes=num_processes, process_num=process_num,
        dedicated_migration_process=dedicated_migration_process
    )
    run_migrations = (process_num == 0)  # only first process runs migrations
    ucr_processor = get_ucr_processor(
        data_source_providers=[
            DynamicDataSourceProvider('CommCareCase'),
            StaticDataSourceProvider('CommCareCase')
        ],
        ucr_division=ucr_division,
        include_ucrs=include_ucrs,
        exclude_ucrs=exclude_ucrs,
        run_migrations=run_migrations,
        ucr_configs=ucr_configs
    )
    ucr_dr_processor = get_data_registry_ucr_processor(
        run_migrations=run_migrations,
        ucr_configs=ucr_configs
    )
    case_to_es_processor = BulkElasticProcessor(
        adapter=case_adapter,
        change_filter_fn=is_couch_change_for_sql_domain
    )
    case_search_processor = get_case_search_processor()

    checkpoint_id = "{}-{}-{}-{}".format(
        pillow_id, case_adapter.index_name, case_search_processor.adapter.index_name, 'messaging-sync')
    checkpoint = KafkaPillowCheckpoint(checkpoint_id, topics)
    event_handler = KafkaCheckpointEventHandler(
        checkpoint=checkpoint, checkpoint_frequency=1000, change_feed=change_feed,
        checkpoint_callback=ucr_processor
    )
    processors = [case_to_es_processor, CaseMessagingSyncProcessor()]
    if settings.RUN_CASE_SEARCH_PILLOW:
        processors.append(case_search_processor)
    if settings.RUN_DEDUPLICATION_PILLOW:
        processors.append(CaseDeduplicationProcessor())
    if not skip_ucr:
        # this option is useful in tests to avoid extra UCR setup where unneccessary
        processors = [ucr_processor, ucr_dr_processor] + processors
    return ConstructedPillow(
        name=pillow_id,
        change_feed=change_feed,
        checkpoint=checkpoint,
        change_processed_event_handler=event_handler,
        processor=processors,
        processor_chunk_size=processor_chunk_size,
        process_num=process_num,
        is_dedicated_migration_process=dedicated_migration_process and run_migrations
    )


class SqlCaseReindexerFactory(ReindexerFactory):
    slug = 'sql-case'
    arg_contributors = [
        ReindexerFactory.resumable_reindexer_args,
        ReindexerFactory.elastic_reindexer_args,
        ReindexerFactory.limit_db_args,
        ReindexerFactory.domain_arg,
        ReindexerFactory.server_modified_on_arg,
    ]

    def build(self):
        limit_to_db = self.options.pop('limit_to_db', None)
        domain = self.options.pop('domain', None)
        start_date = self.options.pop('start_date', None)
        end_date = self.options.pop('end_date', None)
        iteration_key = "SqlCaseToElasticsearchPillow_{}_reindexer_{}_{}_from_{}_until_{}".format(
            case_adapter.index_name, limit_to_db or 'all', domain or 'all',
            start_date or 'beginning', end_date or 'current'
        )
        limit_db_aliases = [limit_to_db] if limit_to_db else None

        reindex_accessor = CaseReindexAccessor(
            domain=domain, limit_db_aliases=limit_db_aliases,
            start_date=start_date, end_date=end_date
        )
        doc_provider = SqlDocumentProvider(iteration_key, reindex_accessor)
        return ResumableBulkElasticPillowReindexer(
            doc_provider,
            adapter=case_adapter,
            **self.options
        )
