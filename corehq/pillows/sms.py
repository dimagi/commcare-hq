from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.sms.change_publishers import change_meta_from_sms
from corehq.elastic import get_es_new
from corehq.pillows.mappings.sms_mapping import SMS_INDEX_INFO
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.feed.interface import Change
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor
from pillowtop.reindexer.change_providers.django_model import DjangoModelChangeProvider
from pillowtop.reindexer.reindexer import ElasticPillowReindexer, ReindexerFactory

SMS_PILLOW_KAFKA_CONSUMER_GROUP_ID = 'sql-sms-to-es'


def get_sql_sms_pillow(pillow_id='SqlSMSPillow', num_processes=1, process_num=0, **kwargs):
    assert pillow_id == 'SqlSMSPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, SMS_INDEX_INFO, [topics.SMS])
    processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=SMS_INDEX_INFO,
        doc_prep_fn=lambda x: x
    )
    change_feed = KafkaChangeFeed(
        topics=[topics.SMS], group_id=SMS_PILLOW_KAFKA_CONSUMER_GROUP_ID,
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
    )


class SmsReindexerFactory(ReindexerFactory):
    slug = 'sms'
    arg_contributors = [
        ReindexerFactory.elastic_reindexer_args,
    ]

    def build(self):
        from corehq.apps.sms.models import SMS
        return ElasticPillowReindexer(
            pillow=get_sql_sms_pillow(),
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
