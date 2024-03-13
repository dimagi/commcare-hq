import collections

from dateutil import parser
from django.conf import settings

from corehq.apps.change_feed.topics import FORM_TOPICS
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.userreports.data_source_providers import DynamicDataSourceProvider, StaticDataSourceProvider
from corehq.apps.userreports.pillow import get_ucr_processor
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.users import user_adapter
from corehq.form_processor.backends.sql.dbaccessors import FormReindexAccessor
from corehq.pillows.base import is_couch_change_for_sql_domain
from corehq.pillows.user import UnknownUsersProcessor
from corehq.util.doc_processor.sql import SqlDocumentProvider
from couchforms.const import RESERVED_WORDS, DEVICE_LOG_XMLNS
from pillowtop.checkpoints.manager import KafkaPillowCheckpoint, get_checkpoint_for_elasticsearch_pillow
from pillowtop.const import DEFAULT_PROCESSOR_CHUNK_SIZE
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.form import FormSubmissionMetadataTrackerProcessor
from pillowtop.processors.elastic import BulkElasticProcessor, ElasticProcessor
from pillowtop.reindexer.reindexer import ResumableBulkElasticPillowReindexer, ReindexerFactory


def is_valid_date(txt):
    try:
        if txt and parser.parse(txt):
            return True
    except Exception:
        pass
    return False


# modified from: http://stackoverflow.com/questions/6027558/flatten-nested-python-dictionaries-compressing-keys
def flatten(d, parent_key='', delimiter='/'):
    items = []
    for k, v in d.items():
        if k in RESERVED_WORDS:
            continue
        new_key = parent_key + delimiter + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(list(flatten(v, new_key, delimiter).items()))
        elif not isinstance(v, list):
            items.append((new_key, v))
    return dict(items)


def xform_pillow_filter(doc_dict):
    """
    :return: True to filter out doc
    """
    return (
        doc_dict.get('xmlns', None) == DEVICE_LOG_XMLNS
        or doc_dict.get('domain', None) is None
        or doc_dict['form'] is None
    )


def get_xform_to_elasticsearch_pillow(pillow_id='XFormToElasticsearchPillow', num_processes=1,
                                      process_num=0, **kwargs):
    """XForm change processor that sends form data to Elasticsearch

    Processors:
      - :py:class:`pillowtop.processors.elastic.ElasticProcessor`
    """

    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, form_adapter.index_name, FORM_TOPICS)
    form_processor = ElasticProcessor(
        form_adapter,
        doc_filter_fn=xform_pillow_filter,
        change_filter_fn=is_couch_change_for_sql_domain
    )
    kafka_change_feed = KafkaChangeFeed(
        topics=FORM_TOPICS, client_id='forms-to-es', num_processes=num_processes, process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=kafka_change_feed,
        processor=form_processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=kafka_change_feed
        ),
    )


def get_xform_pillow(pillow_id='xform-pillow', ucr_division=None,
                     include_ucrs=None, exclude_ucrs=None,
                     num_processes=1, process_num=0, ucr_configs=None, skip_ucr=False,
                     processor_chunk_size=DEFAULT_PROCESSOR_CHUNK_SIZE,
                     topics=None, dedicated_migration_process=False, **kwargs):
    """Generic XForm change processor

    Processors:
      - :py:class:`corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor`
            - (disabled when skip_ucr=True)
      - :py:class:`pillowtop.processors.elastic.BulkElasticProcessor`
      - :py:class:`corehq.pillows.user.UnknownUsersProcessor`
            - (disabled when RUN_UNKNOWN_USER_PILLOW=False)
      - :py:class:`pillowtop.form.FormSubmissionMetadataTrackerProcessor`
            - (disabled when RUN_FORM_META_PILLOW=False)
      - :py:class:`corehq.apps.data_interfaces.pillow.CaseDeduplicationPillow``
    """
    if topics:
        assert set(topics).issubset(FORM_TOPICS), "This is a pillow to process forms only"
    topics = topics or FORM_TOPICS
    change_feed = KafkaChangeFeed(
        topics, client_id=pillow_id, num_processes=num_processes, process_num=process_num,
        dedicated_migration_process=dedicated_migration_process
    )

    ucr_processor = get_ucr_processor(
        data_source_providers=[
            DynamicDataSourceProvider('XFormInstance'),
            StaticDataSourceProvider('XFormInstance')
        ],
        ucr_division=ucr_division,
        include_ucrs=include_ucrs,
        exclude_ucrs=exclude_ucrs,
        run_migrations=(process_num == 0),  # only first process runs migrations
        ucr_configs=ucr_configs
    )

    xform_to_es_processor = BulkElasticProcessor(
        form_adapter,
        doc_filter_fn=xform_pillow_filter,
        change_filter_fn=is_couch_change_for_sql_domain
    )
    unknown_user_form_processor = UnknownUsersProcessor()
    form_meta_processor = FormSubmissionMetadataTrackerProcessor()
    checkpoint_id = "{}-{}-{}".format(
        pillow_id, form_adapter.index_name, user_adapter.index_name)
    checkpoint = KafkaPillowCheckpoint(checkpoint_id, topics)
    event_handler = KafkaCheckpointEventHandler(
        checkpoint=checkpoint, checkpoint_frequency=1000, change_feed=change_feed,
        checkpoint_callback=ucr_processor
    )
    processors = [xform_to_es_processor]
    if settings.RUN_UNKNOWN_USER_PILLOW:
        processors.append(unknown_user_form_processor)
    if settings.RUN_FORM_META_PILLOW:
        processors.append(form_meta_processor)
    if not skip_ucr:
        processors.append(ucr_processor)

    return ConstructedPillow(
        name=pillow_id,
        change_feed=change_feed,
        checkpoint=checkpoint,
        change_processed_event_handler=event_handler,
        processor=processors,
        processor_chunk_size=processor_chunk_size,
        process_num=process_num,
        is_dedicated_migration_process=dedicated_migration_process and (process_num == 0)
    )


class SqlFormReindexerFactory(ReindexerFactory):
    slug = 'sql-form'
    arg_contributors = [
        ReindexerFactory.resumable_reindexer_args,
        ReindexerFactory.elastic_reindexer_args,
        ReindexerFactory.limit_db_args,
        ReindexerFactory.domain_arg,
    ]

    def build(self):
        limit_to_db = self.options.pop('limit_to_db', None)
        domain = self.options.pop('domain', None)

        iteration_key = "SqlXFormToElasticsearchPillow_{}_reindexer_{}_{}".format(
            form_adapter.index_name, limit_to_db or 'all', domain or 'all'
        )
        limit_db_aliases = [limit_to_db] if limit_to_db else None

        reindex_accessor = FormReindexAccessor(domain=domain, limit_db_aliases=limit_db_aliases)
        doc_provider = SqlDocumentProvider(iteration_key, reindex_accessor)
        return ResumableBulkElasticPillowReindexer(
            doc_provider,
            form_adapter,
            doc_filter=xform_pillow_filter,
            **self.options
        )
