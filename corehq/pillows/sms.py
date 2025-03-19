from pillowtop.checkpoints.manager import (
    get_checkpoint_for_elasticsearch_pillow,
)
from pillowtop.const import DEFAULT_PROCESSOR_CHUNK_SIZE
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import BulkElasticProcessor
from pillowtop.reindexer.reindexer import (
    ReindexerFactory,
    ResumableBulkElasticPillowReindexer,
)

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import (
    KafkaChangeFeed,
    KafkaCheckpointEventHandler,
)
from corehq.apps.sms.models import SMS
from corehq.apps.es.sms import sms_adapter
from corehq.form_processor.backends.sql.dbaccessors import ReindexAccessor
from corehq.util.doc_processor.sql import SqlDocumentProvider


def get_sql_sms_pillow(pillow_id='SqlSMSPillow', num_processes=1, process_num=0,
                       processor_chunk_size=DEFAULT_PROCESSOR_CHUNK_SIZE, **kwargs):
    """SMS Pillow

    Processors:
      - :py:class:`pillowtop.processors.elastic.BulkElasticProcessor`
    """
    assert pillow_id == 'SqlSMSPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, sms_adapter.index_name, [topics.SMS])
    processor = BulkElasticProcessor(adapter=sms_adapter)
    change_feed = KafkaChangeFeed(
        topics=[topics.SMS], client_id='sql-sms-to-es',
        num_processes=num_processes, process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed
        ),
        processor_chunk_size=processor_chunk_size
    )


class SMSReindexAccessor(ReindexAccessor):
    @property
    def model_class(self):
        return SMS

    @property
    def id_field(self):
        return 'id'

    def get_doc(self, doc_id):
        return SMS.objects.get(pk=doc_id)


class SmsReindexerFactory(ReindexerFactory):
    slug = 'sms'
    arg_contributors = [
        ReindexerFactory.resumable_reindexer_args,
        ReindexerFactory.elastic_reindexer_args,
    ]

    def build(self):
        iteration_key = f"SmsToElasticsearchPillow_{sms_adapter.index_name}_reindexer"
        reindex_accessor = SMSReindexAccessor()
        doc_provider = SqlDocumentProvider(iteration_key, reindex_accessor)
        return ResumableBulkElasticPillowReindexer(
            doc_provider,
            sms_adapter,
            pillow=get_sql_sms_pillow(),
            **self.options
        )
