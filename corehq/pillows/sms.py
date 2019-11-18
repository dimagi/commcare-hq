from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.sms.change_publishers import change_meta_from_sms
from corehq.elastic import get_es_new
from corehq.pillows.mappings.sms_mapping import SMS_INDEX_INFO
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.const import DEFAULT_PROCESSOR_CHUNK_SIZE
from pillowtop.feed.interface import Change
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import BulkElasticProcessor
from pillowtop.reindexer.change_providers.django_model import DjangoModelChangeProvider
from pillowtop.reindexer.reindexer import ElasticPillowReindexer, ReindexerFactory


def get_sql_sms_pillow(pillow_id='SqlSMSPillow', num_processes=1, process_num=0,
                       processor_chunk_size=DEFAULT_PROCESSOR_CHUNK_SIZE, **kwargs):
    assert pillow_id == 'SqlSMSPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, SMS_INDEX_INFO, [topics.SMS])
    processor = BulkElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=SMS_INDEX_INFO,
        doc_prep_fn=lambda x: x
    )
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


class SmsReindexerFactory(ReindexerFactory):
    slug = 'sms'
    arg_contributors = [
        ReindexerFactory.elastic_reindexer_args,
    ]

    def build(self):
        from corehq.apps.sms.models import SMS
        return ElasticPillowReindexer(
            pillow_or_processor=get_sql_sms_pillow(),
            change_provider=DjangoModelChangeProvider(SMS, _sql_sms_to_change),
            elasticsearch=get_es_new(),
            index_info=SMS_INDEX_INFO,
            **self.options
        )


def _sql_sms_to_change(sms):
    return Change(
        id=sms.couch_id,
        sequence_id=None,
        document=sms.to_json(),
        deleted=False,
        metadata=change_meta_from_sms(sms),
        document_store=None,
    )
